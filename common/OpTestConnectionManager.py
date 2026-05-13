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
OpTestConnectionManager
-----------------------

Connection pool manager for SSH connections.
Manages multiple SSH connections efficiently with connection pooling,
health monitoring, and automatic cleanup.
"""

import threading
import time
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta

from .OpTestSSHConnection import OpTestSSHConnection
from .OpTestCommandExecutor import OpTestCommandExecutor
from .Exceptions import SSHConnectionFailed

import logging
import OpTestLogger
log = OpTestLogger.optest_logger_glob.get_logger(__name__)


class ConnectionInfo:
    """
    Information about a managed connection.
    
    Attributes:
        connection: The SSH connection object
        executor: Command executor for this connection
        created_at: When the connection was created
        last_used: When the connection was last used
        use_count: Number of times connection has been used
        in_use: Whether connection is currently in use
    """
    
    def __init__(self, connection: OpTestSSHConnection, executor: OpTestCommandExecutor):
        self.connection = connection
        self.executor = executor
        self.created_at = datetime.now()
        self.last_used = datetime.now()
        self.use_count = 0
        self.in_use = False
        self.lock = threading.Lock()
    
    def acquire(self) -> bool:
        """Mark connection as in use."""
        with self.lock:
            if not self.in_use:
                self.in_use = True
                self.use_count += 1
                self.last_used = datetime.now()
                return True
            return False
    
    def release(self) -> None:
        """Mark connection as available."""
        with self.lock:
            self.in_use = False
            self.last_used = datetime.now()
    
    def is_healthy(self) -> bool:
        """Check if connection is healthy."""
        return self.connection.is_alive()
    
    def get_age(self) -> float:
        """Get connection age in seconds."""
        return (datetime.now() - self.created_at).total_seconds()
    
    def get_idle_time(self) -> float:
        """Get time since last use in seconds."""
        return (datetime.now() - self.last_used).total_seconds()


class OpTestConnectionManager:
    """
    Manage pool of SSH connections with health monitoring and cleanup.
    
    This class provides:
    - Connection pooling and reuse
    - Automatic health monitoring
    - Stale connection cleanup
    - Connection lifecycle management
    - Thread-safe operations
    - Connection statistics
    
    Example:
        >>> manager = OpTestConnectionManager(max_connections=10)
        >>> conn, executor = manager.get_connection('192.168.1.100', 'root', 'password')
        >>> result = executor.run_command('uname -a')
        >>> manager.release_connection(conn)
        >>> manager.cleanup_stale_connections()
    """
    
    def __init__(self, max_connections: int = 20, 
                 max_idle_time: int = 300,
                 max_connection_age: int = 3600,
                 health_check_interval: int = 60):
        """
        Initialize connection manager.
        
        Args:
            max_connections: Maximum number of connections to maintain
            max_idle_time: Maximum idle time before cleanup (seconds)
            max_connection_age: Maximum connection age before refresh (seconds)
            health_check_interval: Interval for health checks (seconds)
        """
        self.max_connections = max_connections
        self.max_idle_time = max_idle_time
        self.max_connection_age = max_connection_age
        self.health_check_interval = health_check_interval
        
        # Connection pool: key = "username@host:port"
        self.connections: Dict[str, ConnectionInfo] = {}
        self.lock = threading.RLock()
        
        # Statistics
        self.total_connections_created = 0
        self.total_connections_reused = 0
        self.total_connections_closed = 0
        
        # Health monitoring thread
        self.health_monitor_running = False
        self.health_monitor_thread: Optional[threading.Thread] = None
        
        log.info(f"OpTestConnectionManager initialized (max_connections={max_connections})")
    
    def _get_connection_key(self, host: str, username: str, port: int = 22) -> str:
        """Generate unique key for connection."""
        return f"{username}@{host}:{port}"
    
    def get_connection(self, host: str, username: str, password: str,
                      port: int = 22, timeout: int = 30) -> Tuple[OpTestSSHConnection, OpTestCommandExecutor]:
        """
        Get or create SSH connection and executor.
        
        Args:
            host: Hostname or IP address
            username: SSH username
            password: SSH password
            port: SSH port
            timeout: Connection timeout
            
        Returns:
            Tuple[OpTestSSHConnection, OpTestCommandExecutor]: Connection and executor
            
        Raises:
            SSHConnectionFailed: If connection cannot be established
        """
        key = self._get_connection_key(host, username, port)
        
        with self.lock:
            # Check if connection exists and is healthy
            if key in self.connections:
                conn_info = self.connections[key]
                
                # Check if connection is healthy and not too old
                if (conn_info.is_healthy() and 
                    conn_info.get_age() < self.max_connection_age):
                    
                    if conn_info.acquire():
                        self.total_connections_reused += 1
                        log.debug(f"Reusing existing connection: {key}")
                        return conn_info.connection, conn_info.executor
                    else:
                        log.debug(f"Connection {key} is in use, creating new one")
                else:
                    log.debug(f"Connection {key} is unhealthy or too old, recreating")
                    self._close_connection(key)
            
            # Check connection limit
            if len(self.connections) >= self.max_connections:
                log.warning(f"Connection limit reached ({self.max_connections}), "
                          "cleaning up stale connections")
                self._cleanup_stale_connections_internal()
            
            # Create new connection
            log.info(f"Creating new SSH connection: {key}")
            
            try:
                connection = OpTestSSHConnection(
                    host=host,
                    username=username,
                    password=password,
                    port=port,
                    timeout=timeout
                )
                connection.connect()
                
                executor = OpTestCommandExecutor(connection)
                
                conn_info = ConnectionInfo(connection, executor)
                conn_info.acquire()
                
                self.connections[key] = conn_info
                self.total_connections_created += 1
                
                log.info(f"Successfully created connection: {key}")
                return connection, executor
                
            except Exception as e:
                log.error(f"Failed to create connection {key}: {e}")
                raise SSHConnectionFailed(f"Failed to create connection to {key}", e)
    
    def release_connection(self, connection: OpTestSSHConnection) -> None:
        """
        Release connection back to pool.
        
        Args:
            connection: Connection to release
        """
        key = self._get_connection_key(connection.host, connection.username, connection.port)
        
        with self.lock:
            if key in self.connections:
                self.connections[key].release()
                log.debug(f"Released connection: {key}")
            else:
                log.warning(f"Attempted to release unknown connection: {key}")
    
    def _close_connection(self, key: str) -> None:
        """Internal method to close and remove connection."""
        if key in self.connections:
            conn_info = self.connections[key]
            try:
                conn_info.connection.disconnect()
            except Exception as e:
                log.debug(f"Error closing connection {key}: {e}")
            finally:
                del self.connections[key]
                self.total_connections_closed += 1
                log.debug(f"Closed connection: {key}")
    
    def close_connection(self, connection: OpTestSSHConnection) -> None:
        """
        Close and remove connection from pool.
        
        Args:
            connection: Connection to close
        """
        key = self._get_connection_key(connection.host, connection.username, connection.port)
        
        with self.lock:
            self._close_connection(key)
    
    def _cleanup_stale_connections_internal(self) -> int:
        """Internal method to cleanup stale connections (must be called with lock held)."""
        cleaned = 0
        keys_to_remove = []
        
        for key, conn_info in self.connections.items():
            # Skip connections currently in use
            if conn_info.in_use:
                continue
            
            # Check if connection is stale
            if (not conn_info.is_healthy() or
                conn_info.get_idle_time() > self.max_idle_time or
                conn_info.get_age() > self.max_connection_age):
                
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            self._close_connection(key)
            cleaned += 1
        
        if cleaned > 0:
            log.info(f"Cleaned up {cleaned} stale connections")
        
        return cleaned
    
    def cleanup_stale_connections(self) -> int:
        """
        Cleanup stale, idle, or unhealthy connections.
        
        Returns:
            int: Number of connections cleaned up
        """
        with self.lock:
            return self._cleanup_stale_connections_internal()
    
    def cleanup_all(self) -> None:
        """Close all connections and cleanup."""
        with self.lock:
            log.info(f"Closing all {len(self.connections)} connections")
            
            keys = list(self.connections.keys())
            for key in keys:
                self._close_connection(key)
            
            log.info("All connections closed")
    
    def start_health_monitor(self) -> None:
        """Start background health monitoring thread."""
        if self.health_monitor_running:
            log.warning("Health monitor already running")
            return
        
        self.health_monitor_running = True
        self.health_monitor_thread = threading.Thread(
            target=self._health_monitor_loop,
            daemon=True,
            name="OpTestConnectionHealthMonitor"
        )
        self.health_monitor_thread.start()
        log.info("Health monitor started")
    
    def stop_health_monitor(self) -> None:
        """Stop background health monitoring thread."""
        if not self.health_monitor_running:
            return
        
        self.health_monitor_running = False
        if self.health_monitor_thread:
            self.health_monitor_thread.join(timeout=5)
        log.info("Health monitor stopped")
    
    def _health_monitor_loop(self) -> None:
        """Background thread for health monitoring."""
        log.debug("Health monitor loop started")
        
        while self.health_monitor_running:
            try:
                time.sleep(self.health_check_interval)
                
                if not self.health_monitor_running:
                    break
                
                log.debug("Running health check...")
                self.cleanup_stale_connections()
                
            except Exception as e:
                log.error(f"Error in health monitor loop: {e}")
        
        log.debug("Health monitor loop stopped")
    
    def get_connection_stats(self) -> dict:
        """
        Get connection pool statistics.
        
        Returns:
            dict: Statistics about connection pool
        """
        with self.lock:
            active_connections = sum(1 for c in self.connections.values() if c.in_use)
            idle_connections = len(self.connections) - active_connections
            
            total_use_count = sum(c.use_count for c in self.connections.values())
            avg_use_count = total_use_count / len(self.connections) if self.connections else 0
            
            return {
                'total_connections': len(self.connections),
                'active_connections': active_connections,
                'idle_connections': idle_connections,
                'max_connections': self.max_connections,
                'total_created': self.total_connections_created,
                'total_reused': self.total_connections_reused,
                'total_closed': self.total_connections_closed,
                'reuse_rate': (self.total_connections_reused / 
                             (self.total_connections_created + self.total_connections_reused)
                             if (self.total_connections_created + self.total_connections_reused) > 0 
                             else 0),
                'average_use_count': avg_use_count,
                'health_monitor_running': self.health_monitor_running
            }
    
    def get_connection_list(self) -> List[dict]:
        """
        Get list of all connections with details.
        
        Returns:
            List[dict]: List of connection information
        """
        with self.lock:
            connections = []
            for key, conn_info in self.connections.items():
                connections.append({
                    'key': key,
                    'host': conn_info.connection.host,
                    'port': conn_info.connection.port,
                    'username': conn_info.connection.username,
                    'connected': conn_info.connection.connected,
                    'healthy': conn_info.is_healthy(),
                    'in_use': conn_info.in_use,
                    'use_count': conn_info.use_count,
                    'age_seconds': conn_info.get_age(),
                    'idle_seconds': conn_info.get_idle_time(),
                    'created_at': conn_info.created_at.isoformat(),
                    'last_used': conn_info.last_used.isoformat()
                })
            return connections
    
    def __enter__(self):
        """Context manager entry."""
        self.start_health_monitor()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_health_monitor()
        self.cleanup_all()
        return False
    
    def __str__(self):
        stats = self.get_connection_stats()
        return (f"OpTestConnectionManager(connections={stats['total_connections']}, "
                f"active={stats['active_connections']}, "
                f"reuse_rate={stats['reuse_rate']:.1%})")
    
    def __repr__(self):
        return self.__str__()

