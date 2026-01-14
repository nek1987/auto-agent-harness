#!/usr/bin/env python3
"""
SSH Connector for Dokploy Server Management
Executes commands on remote server via SSH.
Supports both key-based and password-based authentication.
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from typing import Optional, Tuple


class SSHConnector:
    """SSH connection manager supporting key and password authentication."""

    # Default SSH key locations
    DEFAULT_KEY_PATHS = [
        Path.home() / '.ssh' / 'id_ed25519',
        Path.home() / '.ssh' / 'id_rsa',
    ]

    def __init__(self, host: str = None, user: str = None, port: str = None):
        self.host = host or os.getenv('DOKPLOY_SSH_HOST', '198.163.206.80')
        self.port = port or os.getenv('DOKPLOY_SSH_PORT', '22')
        self.user = user or os.getenv('DOKPLOY_SSH_USER', 'root')
        self.key_path = self._find_ssh_key()

        self._validate_config()

    def _find_ssh_key(self) -> Optional[Path]:
        """Find available SSH key."""
        for key_path in self.DEFAULT_KEY_PATHS:
            if key_path.exists():
                return key_path
        return None

    def _validate_config(self) -> None:
        """Validate SSH configuration."""
        if not self.host:
            print("Error: DOKPLOY_SSH_HOST not set")
            sys.exit(1)

    def execute(self, command: str, timeout: int = 60) -> Tuple[str, str, int]:
        """
        Execute command on remote server via SSH key authentication.

        Args:
            command: Command to execute
            timeout: Command timeout in seconds

        Returns:
            Tuple of (stdout, stderr, return_code)
        """
        ssh_command = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'LogLevel=ERROR',
            '-o', 'ConnectTimeout=10',
            '-p', self.port,
        ]

        if self.key_path:
            ssh_command.extend(['-i', str(self.key_path)])

        ssh_command.append(f'{self.user}@{self.host}')
        ssh_command.append(command)

        try:
            result = subprocess.run(
                ssh_command,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return '', f'Command timed out after {timeout}s', 1
        except Exception as e:
            return '', str(e), 1

    def docker_logs(self, container: str, tail: int = 100) -> str:
        """Get Docker container logs."""
        stdout, stderr, code = self.execute(f'docker logs {container} --tail {tail} 2>&1')
        return stdout if code == 0 else stderr

    def docker_ps(self, all_containers: bool = False) -> str:
        """List Docker containers."""
        cmd = 'docker ps -a' if all_containers else 'docker ps'
        stdout, stderr, code = self.execute(cmd)
        return stdout if code == 0 else stderr

    def docker_stats(self) -> str:
        """Get Docker container stats."""
        stdout, stderr, code = self.execute('docker stats --no-stream')
        return stdout if code == 0 else stderr

    def docker_restart(self, container: str) -> str:
        """Restart Docker container."""
        stdout, stderr, code = self.execute(f'docker restart {container}')
        return stdout if code == 0 else stderr


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Execute commands on Dokploy server via SSH'
    )
    parser.add_argument(
        'command',
        nargs='?',
        help='Command to execute on remote server'
    )
    parser.add_argument(
        '--logs',
        metavar='CONTAINER',
        help='Get logs from container'
    )
    parser.add_argument(
        '--tail',
        type=int,
        default=100,
        help='Number of log lines (default: 100)'
    )
    parser.add_argument(
        '--ps',
        action='store_true',
        help='List running containers'
    )
    parser.add_argument(
        '--ps-all',
        action='store_true',
        help='List all containers'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show container resource usage'
    )
    parser.add_argument(
        '--restart',
        metavar='CONTAINER',
        help='Restart container'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='Command timeout in seconds (default: 30)'
    )

    args = parser.parse_args()

    connector = SSHConnector()

    if args.logs:
        print(connector.docker_logs(args.logs, args.tail))
    elif args.ps:
        print(connector.docker_ps(all_containers=False))
    elif args.ps_all:
        print(connector.docker_ps(all_containers=True))
    elif args.stats:
        print(connector.docker_stats())
    elif args.restart:
        print(connector.docker_restart(args.restart))
    elif args.command:
        stdout, stderr, code = connector.execute(args.command, args.timeout)
        if stdout:
            print(stdout)
        if stderr:
            print(stderr, file=sys.stderr)
        sys.exit(code)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
