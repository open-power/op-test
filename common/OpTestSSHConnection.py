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
OpTestSSHConnection
-------------------

Pure SSH connection implementation using paramiko - replaces pexpect-based connections.
This module provides reliable SSH connectivity without the issues of expect patterns.
"""

import paramiko
import time
import socket
import threading
from typing import Optional, Tuple, List
from datetime import datetime

from .Exceptions import SSHConnectionFailed, SSHCommandFailed, SSHSessionDisconnected
from .OpTestError import OpTestError

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class OpTestCommandResult:
    """
    Standardized command execution result.
    
    Attributes:
        command (str): The command that was executed
        exit_code (int): Exit code from command execution
        stdout (str): Standard output from command
        stderr (str): Standard error from command
        duration (float): Execution time in seconds
        timestamp (datetime): When the command was executed
        success (bool): True if exit_code == 0
        host (str): Host where command was executed
    """
    
    def __init__(self, command: str, exit_code: int, stdout: str, 
                 stderr: str, duration: float, host: str):
        self.command = command
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.duration = duration
        self.timestamp = datetime.now()
        self.success = (exit_code == 0)
        self.host = host
        
    def __str__(self):
        return (f"CommandResult(cmd='{self.command[:50]}...', "
                f"exit_code={self.exit_code}, success={self.success}, "
                f"duration={self.duration:.2f}s)")
    
    def __repr__(self):
        return self.__str__()
    
    def get_output_lines(self) -> List[str]:
        """Get stdout as list of lines (compatible with old interface)"""
        return self.stdout.splitlines()


class OpTestSSHConnection:
    """
    Pure SSH connection using paramiko - no pexpect dependency.
    
    This class provides reliable SSH connectivity with automatic reconnection,
    keep-alive, and comprehensive error handling. It replaces the pexpect-based
    SSH implementation to eliminate expect pattern issues.
    
    Features:
        - Persistent SSH connections with keep-alive
        - Automatic reconnection on failure
        - Connection health monitoring
        - Multiple channel support (exec, shell, sftp)
        - No expect patterns - direct command execution
        - Thread-safe operations
    
    Example:
        >>> conn = OpTestSSHConnection('192.168.1.100', 'root', 'password')
        >>> conn.connect()
        >>> result = conn.execute_command('uname -a', timeout=30)
        >>> print(result.stdout)
        >>> conn.disconnect()
    """
    
    def __init__(self, host: str, username: str, password: str, 
                 port: int = 22, timeout: int = 30, keepalive_interval: int = 30):
        """
        Initialize SSH connection parameters.
        
        Args:
            host: Hostname or IP address
            username: SSH username
            password: SSH password
            port: SSH port (default: 22)
            timeout: Connection timeout in seconds (default: 30)
            keepalive_interval: Keep-alive interval in seconds (default: 30)
        """
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self.keepalive_interval = keepalive_interval
        
        self.client: Optional[paramiko.SSHClient] = None
        self.transport: Optional[paramiko.Transport] = None
        self.connected = False
        self.connection_time: Optional[datetime] = None
        self.last_activity: Optional[datetime] = None
        self.command_count = 0
        
        # Thread safety
        self.lock = threading.RLock()
        
        log.debug(f"OpTestSSHConnection initialized for {username}@{host}:{port}")
    
    def connect(self, retry: int = 3) -> bool:
        """
        Establish SSH connection with retry logic.
        
        Args:
            retry: Number of connection attempts (default: 3)
            
        Returns:
            bool: True if connection successful
            
        Raises:
            SSHConnectionFailed: If connection fails after all retries
        """
        with self.lock:
            if self.connected and self.is_alive():
                log.debug(f"Already connected to {self.host}")
                return True
            
            attempts = 0
            last_error = None
            
            while attempts < retry:
                try:
                    log.info(f"Connecting to {self.username}@{self.host}:{self.port} "
                            f"(attempt {attempts + 1}/{retry})")
                    
                    # Create new SSH client
                    self.client = paramiko.SSHClient()
                    self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    
                    # Connect with timeout
                    self.client.connect(
                        hostname=self.host,
                        port=self.port,
                        username=self.username,
                        password=self.password,
                        timeout=self.timeout,
                        allow_agent=False,
                        look_for_keys=False,
                        banner_timeout=self.timeout
                    )
                    
                    # Get transport for keep-alive
                    self.transport = self.client.get_transport()
                    if self.transport:
                        self.transport.set_keepalive(self.keepalive_interval)
                    
                    self.connected = True
                    self.connection_time = datetime.now()
                    self.last_activity = datetime.now()
                    self.command_count = 0
                    
                    log.info(f"Successfully connected to {self.host}")
                    return True
                    
                except (paramiko.SSHException, socket.error, socket.timeout) as e:
                    last_error = e
                    attempts += 1
                    log.warning(f"Connection attempt {attempts} failed: {e}")
                    
                    if attempts < retry:
                        wait_time = 2 ** attempts  # Exponential backoff
                        log.debug(f"Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    
                    # Clean up failed connection
                    self._cleanup_connection()
            
            # All retries failed
            error_msg = (f"Failed to connect to {self.username}@{self.host}:{self.port} "
                        f"after {retry} attempts")
            log.error(error_msg)
            raise SSHConnectionFailed(error_msg, last_error)
    
    def disconnect(self) -> None:
        """
        Close SSH connection and cleanup resources.
        """
        with self.lock:
            if not self.connected:
                log.debug(f"Already disconnected from {self.host}")
                return
            
            log.info(f"Disconnecting from {self.host}")
            self._cleanup_connection()
            
            log.debug(f"Disconnected from {self.host}. "
                     f"Session stats: {self.command_count} commands executed, "
                     f"duration: {self._get_connection_duration():.1f}s")
    
    def _cleanup_connection(self) -> None:
        """Internal method to cleanup connection resources."""
        try:
            if self.client:
                self.client.close()
        except Exception as e:
            log.debug(f"Error closing client: {e}")
        finally:
            self.client = None
            self.transport = None
            self.connected = False
    
    def is_alive(self) -> bool:
        """
        Check if SSH connection is alive and healthy.
        
        Returns:
            bool: True if connection is active and responsive
        """
        with self.lock:
            if not self.connected or not self.client or not self.transport:
                return False
            
            try:
                # Check if transport is active
                if not self.transport.is_active():
                    log.debug(f"Transport to {self.host} is not active")
                    return False
                
                # Send keep-alive to verify connection
                self.transport.send_ignore()
                return True
                
            except Exception as e:
                log.debug(f"Connection health check failed for {self.host}: {e}")
                return False
    
    def reconnect(self, retry: int = 3) -> bool:
        """
        Reconnect to SSH host.
        
        Args:
            retry: Number of reconnection attempts
            
        Returns:
            bool: True if reconnection successful
        """
        log.info(f"Reconnecting to {self.host}")
        self.disconnect()
        return self.connect(retry=retry)
    
    def execute_command(self, command: str, timeout: int = 60, 
                       check_exit_code: bool = True) -> OpTestCommandResult:
        """
        Execute command via SSH and return result.
        
        Args:
            command: Command to execute
            timeout: Command timeout in seconds (default: 60)
            check_exit_code: Raise exception if exit code != 0 (default: True)
            
        Returns:
            OpTestCommandResult: Command execution result
            
        Raises:
            SSHSessionDisconnected: If connection is lost
            SSHCommandFailed: If command fails and check_exit_code is True
        """
        with self.lock:
            # Ensure connection is alive
            if not self.is_alive():
                log.warning(f"Connection to {self.host} is dead, reconnecting...")
                self.reconnect()
            
            start_time = time.time()
            
            try:
                log.debug(f"Executing on {self.host}: {command}")
                
                # Execute command
                stdin, stdout, stderr = self.client.exec_command(
                    command,
                    timeout=timeout,
                    get_pty=False  # Don't allocate PTY to avoid terminal issues
                )
                
                # Wait for command completion and get exit code
                exit_code = stdout.channel.recv_exit_status()
                
                # Read output
                stdout_data = stdout.read().decode('utf-8', errors='replace')
                stderr_data = stderr.read().decode('utf-8', errors='replace')
                
                duration = time.time() - start_time
                
                # Update stats
                self.last_activity = datetime.now()
                self.command_count += 1
                
                # Create result object
                result = OpTestCommandResult(
                    command=command,
                    exit_code=exit_code,
                    stdout=stdout_data,
                    stderr=stderr_data,
                    duration=duration,
                    host=self.host
                )
                
                log.debug(f"Command completed: {result}")
                
                # Check exit code if requested
                if check_exit_code and exit_code != 0:
                    error_msg = (f"Command failed on {self.host}: {command}\n"
                                f"Exit code: {exit_code}\n"
                                f"Stderr: {stderr_data}")
                    log.error(error_msg)
                    raise SSHCommandFailed(command, stderr_data, exit_code)
                
                return result
                
            except socket.timeout:
                duration = time.time() - start_time
                error_msg = f"Command timeout after {duration:.1f}s: {command}"
                log.error(error_msg)
                raise SSHCommandFailed(command, error_msg, -1)
                
            except paramiko.SSHException as e:
                error_msg = f"SSH error executing command: {e}"
                log.error(error_msg)
                self.connected = False
                raise SSHSessionDisconnected(error_msg, e)
                
            except Exception as e:
                error_msg = f"Unexpected error executing command: {e}"
                log.error(error_msg)
                raise SSHCommandFailed(command, str(e), -1)
    
    def execute_command_ignore_fail(self, command: str, 
                                   timeout: int = 60) -> OpTestCommandResult:
        """
        Execute command and return result regardless of exit code.
        
        Args:
            command: Command to execute
            timeout: Command timeout in seconds
            
        Returns:
            OpTestCommandResult: Command execution result
        """
        return self.execute_command(command, timeout, check_exit_code=False)
    
    def get_shell_channel(self) -> paramiko.Channel:
        """
        Get an interactive shell channel.
        
        Returns:
            paramiko.Channel: Interactive shell channel
            
        Raises:
            SSHSessionDisconnected: If connection is not available
        """
        with self.lock:
            if not self.is_alive():
                self.reconnect()
            
            try:
                channel = self.client.invoke_shell()
                channel.settimeout(self.timeout)
                return channel
            except Exception as e:
                error_msg = f"Failed to get shell channel: {e}"
                log.error(error_msg)
                raise SSHSessionDisconnected(error_msg, e)
    
    def get_sftp_client(self) -> paramiko.SFTPClient:
        """
        Get SFTP client for file operations.
        
        Returns:
            paramiko.SFTPClient: SFTP client
            
        Raises:
            SSHSessionDisconnected: If connection is not available
        """
        with self.lock:
            if not self.is_alive():
                self.reconnect()
            
            try:
                return self.client.open_sftp()
            except Exception as e:
                error_msg = f"Failed to get SFTP client: {e}"
                log.error(error_msg)
                raise SSHSessionDisconnected(error_msg, e)
    
    def _get_connection_duration(self) -> float:
        """Get connection duration in seconds."""
        if self.connection_time:
            return (datetime.now() - self.connection_time).total_seconds()
        return 0.0
    
    def get_connection_info(self) -> dict:
        """
        Get connection information and statistics.
        
        Returns:
            dict: Connection information
        """
        return {
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'connected': self.connected,
            'alive': self.is_alive(),
            'connection_time': self.connection_time,
            'last_activity': self.last_activity,
            'command_count': self.command_count,
            'duration': self._get_connection_duration()
        }
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False
    
    def __str__(self):
        status = "connected" if self.connected else "disconnected"
        return f"OpTestSSHConnection({self.username}@{self.host}:{self.port}, {status})"
    
    def __repr__(self):
        return self.__str__()

