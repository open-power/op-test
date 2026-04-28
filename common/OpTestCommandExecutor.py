#!/usr/bin/env python3
# OpenPOWER Automated Test Project
#
# Contributors Listed Below - COPYRIGHT 2024
# [+] International Business Machines Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.

"""
OpTestCommandExecutor
---------------------

Robust command execution engine for SSH connections.
Provides reliable command execution with retry logic, timeout handling,
and comprehensive error management.
"""

import time
import threading
from typing import Optional, List, Callable
from concurrent.futures import ThreadPoolExecutor, Future, TimeoutError as FutureTimeoutError

from .OpTestSSHConnection import OpTestSSHConnection, OpTestCommandResult
from .Exceptions import SSHCommandFailed, SSHSessionDisconnected, CommandFailed

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestCommandExecutor:
    """
    Execute commands via SSH with robust error handling and retry logic.
    
    This class wraps OpTestSSHConnection to provide:
    - Automatic retry on transient failures
    - Exponential backoff for retries
    - Sudo command execution without expect patterns
    - Async command execution
    - Command history tracking
    - Comprehensive logging
    
    Example:
        >>> conn = OpTestSSHConnection('192.168.1.100', 'root', 'password')
        >>> conn.connect()
        >>> executor = OpTestCommandExecutor(conn)
        >>> result = executor.run_command('ls -la', timeout=30, retry=2)
        >>> print(result.stdout)
    """
    
    def __init__(self, connection: OpTestSSHConnection, 
                 default_timeout: int = 60, default_retry: int = 0):
        """
        Initialize command executor.
        
        Args:
            connection: OpTestSSHConnection instance
            default_timeout: Default command timeout in seconds
            default_retry: Default number of retries for failed commands
        """
        self.connection = connection
        self.default_timeout = default_timeout
        self.default_retry = default_retry
        self.command_history: List[OpTestCommandResult] = []
        self.lock = threading.RLock()
        
        log.debug(f"OpTestCommandExecutor initialized for {connection.host}")
    
    def run_command(self, command: str, timeout: Optional[int] = None, 
                   retry: Optional[int] = None) -> OpTestCommandResult:
        """
        Execute command with retry logic.
        
        Args:
            command: Command to execute
            timeout: Command timeout in seconds (uses default if None)
            retry: Number of retries (uses default if None)
            
        Returns:
            OpTestCommandResult: Command execution result
            
        Raises:
            SSHCommandFailed: If command fails after all retries
            SSHSessionDisconnected: If SSH connection is lost
        """
        timeout = timeout if timeout is not None else self.default_timeout
        retry = retry if retry is not None else self.default_retry
        
        attempts = 0
        last_error = None
        
        while attempts <= retry:
            try:
                log.debug(f"Executing command (attempt {attempts + 1}/{retry + 1}): {command}")
                
                # Execute command via connection
                result = self.connection.execute_command(
                    command=command,
                    timeout=timeout,
                    check_exit_code=True
                )
                
                # Store in history
                with self.lock:
                    self.command_history.append(result)
                
                log.debug(f"Command succeeded: {command}")
                return result
                
            except SSHCommandFailed as e:
                last_error = e
                attempts += 1
                
                if attempts <= retry:
                    wait_time = min(2 ** attempts, 30)  # Exponential backoff, max 30s
                    log.warning(f"Command failed (attempt {attempts}/{retry + 1}), "
                              f"retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    log.error(f"Command failed after {attempts} attempts: {command}")
                    raise
                    
            except SSHSessionDisconnected as e:
                log.error(f"SSH session disconnected during command execution: {e}")
                # Try to reconnect if we have retries left
                if attempts < retry:
                    log.info("Attempting to reconnect...")
                    try:
                        self.connection.reconnect()
                        attempts += 1
                        continue
                    except Exception as reconnect_error:
                        log.error(f"Reconnection failed: {reconnect_error}")
                        raise
                else:
                    raise
        
        # Should not reach here, but just in case
        if last_error:
            raise last_error
        raise SSHCommandFailed(command, "Unknown error", -1)
    
    def run_command_ignore_fail(self, command: str, 
                               timeout: Optional[int] = None,
                               retry: Optional[int] = None) -> OpTestCommandResult:
        """
        Execute command and return result regardless of exit code.
        
        Args:
            command: Command to execute
            timeout: Command timeout in seconds
            retry: Number of retries
            
        Returns:
            OpTestCommandResult: Command execution result
        """
        timeout = timeout if timeout is not None else self.default_timeout
        retry = retry if retry is not None else self.default_retry
        
        attempts = 0
        last_error = None
        
        while attempts <= retry:
            try:
                log.debug(f"Executing command (ignore fail, attempt {attempts + 1}): {command}")
                
                result = self.connection.execute_command_ignore_fail(
                    command=command,
                    timeout=timeout
                )
                
                with self.lock:
                    self.command_history.append(result)
                
                return result
                
            except SSHSessionDisconnected as e:
                last_error = e
                attempts += 1
                
                if attempts <= retry:
                    log.warning(f"Session disconnected, reconnecting (attempt {attempts})...")
                    try:
                        self.connection.reconnect()
                    except Exception as reconnect_error:
                        log.error(f"Reconnection failed: {reconnect_error}")
                        if attempts > retry:
                            raise
                else:
                    raise
        
        if last_error:
            raise last_error
        raise SSHSessionDisconnected("Failed to execute command after retries")
    
    def run_sudo_command(self, command: str, password: Optional[str] = None,
                        timeout: Optional[int] = None,
                        retry: Optional[int] = None) -> OpTestCommandResult:
        """
        Execute command with sudo without using expect patterns.
        
        This method uses 'sudo -S' to read password from stdin, avoiding
        the need for pexpect-style expect patterns.
        
        Args:
            command: Command to execute with sudo
            password: Sudo password (uses connection password if None)
            timeout: Command timeout in seconds
            retry: Number of retries
            
        Returns:
            OpTestCommandResult: Command execution result
            
        Raises:
            SSHCommandFailed: If sudo command fails
        """
        password = password if password is not None else self.connection.password
        
        # Use sudo -S to read password from stdin
        # The -p '' suppresses the password prompt
        sudo_command = f"echo '{password}' | sudo -S -p '' {command}"
        
        log.debug(f"Executing sudo command: sudo {command}")
        
        return self.run_command(sudo_command, timeout=timeout, retry=retry)
    
    def run_command_async(self, command: str, timeout: Optional[int] = None,
                         callback: Optional[Callable[[OpTestCommandResult], None]] = None) -> Future:
        """
        Execute command asynchronously.
        
        Args:
            command: Command to execute
            timeout: Command timeout in seconds
            callback: Optional callback function to call with result
            
        Returns:
            Future: Future object for async result
            
        Example:
            >>> future = executor.run_command_async('long_running_command')
            >>> # Do other work...
            >>> result = future.result(timeout=120)
        """
        timeout = timeout if timeout is not None else self.default_timeout
        
        def execute_with_callback():
            result = self.run_command(command, timeout=timeout)
            if callback:
                callback(result)
            return result
        
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(execute_with_callback)
        
        log.debug(f"Started async command execution: {command}")
        return future
    
    def run_commands_parallel(self, commands: List[str], 
                             timeout: Optional[int] = None,
                             max_workers: int = 5) -> List[OpTestCommandResult]:
        """
        Execute multiple commands in parallel.
        
        Args:
            commands: List of commands to execute
            timeout: Timeout for each command
            max_workers: Maximum number of parallel workers
            
        Returns:
            List[OpTestCommandResult]: List of command results
            
        Note:
            This requires multiple SSH connections. Use with OpTestConnectionManager.
        """
        timeout = timeout if timeout is not None else self.default_timeout
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self.run_command, cmd, timeout)
                for cmd in commands
            ]
            
            for future in futures:
                try:
                    result = future.result(timeout=timeout + 10)
                    results.append(result)
                except Exception as e:
                    log.error(f"Parallel command execution failed: {e}")
                    # Create error result
                    error_result = OpTestCommandResult(
                        command="<parallel command>",
                        exit_code=-1,
                        stdout="",
                        stderr=str(e),
                        duration=0.0,
                        host=self.connection.host
                    )
                    results.append(error_result)
        
        return results
    
    def run_command_with_output_callback(self, command: str,
                                        output_callback: Callable[[str], None],
                                        timeout: Optional[int] = None) -> OpTestCommandResult:
        """
        Execute command and stream output to callback function.
        
        Useful for long-running commands where you want to see output in real-time.
        
        Args:
            command: Command to execute
            output_callback: Function to call with each line of output
            timeout: Command timeout in seconds
            
        Returns:
            OpTestCommandResult: Command execution result
        """
        # For now, execute normally and call callback with full output
        # Future enhancement: implement true streaming
        result = self.run_command(command, timeout=timeout)
        
        for line in result.stdout.splitlines():
            output_callback(line)
        
        return result
    
    def get_command_history(self, limit: Optional[int] = None) -> List[OpTestCommandResult]:
        """
        Get command execution history.
        
        Args:
            limit: Maximum number of recent commands to return (None for all)
            
        Returns:
            List[OpTestCommandResult]: List of command results
        """
        with self.lock:
            if limit:
                return self.command_history[-limit:]
            return self.command_history.copy()
    
    def clear_command_history(self) -> None:
        """Clear command execution history."""
        with self.lock:
            self.command_history.clear()
            log.debug("Command history cleared")
    
    def get_statistics(self) -> dict:
        """
        Get executor statistics.
        
        Returns:
            dict: Statistics including command count, success rate, etc.
        """
        with self.lock:
            total_commands = len(self.command_history)
            successful_commands = sum(1 for r in self.command_history if r.success)
            failed_commands = total_commands - successful_commands
            
            total_duration = sum(r.duration for r in self.command_history)
            avg_duration = total_duration / total_commands if total_commands > 0 else 0
            
            return {
                'total_commands': total_commands,
                'successful_commands': successful_commands,
                'failed_commands': failed_commands,
                'success_rate': successful_commands / total_commands if total_commands > 0 else 0,
                'total_duration': total_duration,
                'average_duration': avg_duration,
                'connection_host': self.connection.host
            }
    
    def __str__(self):
        stats = self.get_statistics()
        return (f"OpTestCommandExecutor(host={self.connection.host}, "
                f"commands={stats['total_commands']}, "
                f"success_rate={stats['success_rate']:.1%})")
    
    def __repr__(self):
        return self.__str__()

