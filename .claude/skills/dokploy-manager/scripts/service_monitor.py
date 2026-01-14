#!/usr/bin/env python3
"""
Service Monitor for Dokploy
Monitor status and health of Telecom-ai services.
"""

import os
import sys
import argparse
import json
from typing import Dict, List, Optional

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssh_connector import SSHConnector


class ServiceMonitor:
    """Monitor Dokploy services status and health."""

    # Known Telecom-ai services
    SERVICES = [
        'api-gateway',
        'rag-agent',
        'crawler-service',
        'admin-dashboard',
    ]

    def __init__(self):
        self.ssh = SSHConnector()

    def get_container_status(self) -> List[Dict]:
        """Get status of all containers."""
        cmd = 'docker ps -a --format "{{json .}}"'
        stdout, stderr, code = self.ssh.execute(cmd)

        if code != 0:
            print(f"Error getting container status: {stderr}")
            return []

        containers = []
        for line in stdout.strip().split('\n'):
            if line:
                try:
                    containers.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        return containers

    def get_container_stats(self) -> List[Dict]:
        """Get resource usage stats for containers."""
        cmd = 'docker stats --no-stream --format "{{json .}}"'
        stdout, stderr, code = self.ssh.execute(cmd, timeout=60)

        if code != 0:
            print(f"Error getting stats: {stderr}")
            return []

        stats = []
        for line in stdout.strip().split('\n'):
            if line:
                try:
                    stats.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        return stats

    def get_service_health(self, service: str) -> Dict:
        """Check health of specific service."""
        # Get container info
        cmd = f'docker inspect {service} --format "{{{{json .}}}}"'
        stdout, stderr, code = self.ssh.execute(cmd)

        if code != 0:
            return {'status': 'not_found', 'error': stderr}

        try:
            info = json.loads(stdout)
            state = info.get('State', {})

            return {
                'status': state.get('Status', 'unknown'),
                'running': state.get('Running', False),
                'health': state.get('Health', {}).get('Status', 'no healthcheck'),
                'started_at': state.get('StartedAt', ''),
                'restart_count': info.get('RestartCount', 0),
            }
        except json.JSONDecodeError:
            return {'status': 'error', 'error': 'Failed to parse response'}

    def print_status_table(self, containers: List[Dict]) -> None:
        """Print container status as table."""
        print("\n" + "=" * 80)
        print(f"{'CONTAINER':<25} {'STATUS':<15} {'PORTS':<25} {'CREATED':<15}")
        print("=" * 80)

        for c in containers:
            name = c.get('Names', 'unknown')[:24]
            status = c.get('Status', 'unknown')[:14]
            ports = c.get('Ports', '')[:24]
            created = c.get('CreatedAt', '')[:14]

            # Highlight our services
            if any(svc in name for svc in self.SERVICES):
                name = f"* {name}"

            print(f"{name:<25} {status:<15} {ports:<25} {created:<15}")

        print("=" * 80)
        print("* = Telecom-ai service\n")

    def print_stats_table(self, stats: List[Dict]) -> None:
        """Print resource stats as table."""
        print("\n" + "=" * 80)
        print(f"{'CONTAINER':<25} {'CPU %':<10} {'MEM USAGE':<20} {'MEM %':<10} {'NET I/O':<15}")
        print("=" * 80)

        for s in stats:
            name = s.get('Name', 'unknown')[:24]
            cpu = s.get('CPUPerc', '0%')[:9]
            mem = s.get('MemUsage', '0B / 0B')[:19]
            mem_perc = s.get('MemPerc', '0%')[:9]
            net = s.get('NetIO', '0B / 0B')[:14]

            print(f"{name:<25} {cpu:<10} {mem:<20} {mem_perc:<10} {net:<15}")

        print("=" * 80 + "\n")

    def print_service_details(self, service: str) -> None:
        """Print detailed info for specific service."""
        health = self.get_service_health(service)

        print(f"\n{'=' * 50}")
        print(f"Service: {service}")
        print(f"{'=' * 50}")

        for key, value in health.items():
            print(f"  {key}: {value}")

        # Get recent logs
        cmd = f'docker logs {service} --tail 10 2>&1'
        stdout, _, _ = self.ssh.execute(cmd)

        print(f"\nRecent logs:")
        print("-" * 50)
        for line in stdout.strip().split('\n')[-10:]:
            print(f"  {line[:80]}")

        print("=" * 50 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Monitor Dokploy services status'
    )
    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='Show all containers'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show resource usage stats'
    )
    parser.add_argument(
        '--service', '-s',
        help='Show details for specific service'
    )
    parser.add_argument(
        '--health',
        action='store_true',
        help='Check health of all Telecom-ai services'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output in JSON format'
    )

    args = parser.parse_args()

    monitor = ServiceMonitor()

    if args.service:
        if args.json:
            health = monitor.get_service_health(args.service)
            print(json.dumps(health, indent=2))
        else:
            monitor.print_service_details(args.service)
        return

    if args.health:
        print("\nTelecom-ai Services Health Check")
        print("=" * 50)

        results = {}
        for service in monitor.SERVICES:
            health = monitor.get_service_health(service)
            results[service] = health

            status_icon = "OK" if health.get('running') else "FAIL"
            print(f"  [{status_icon}] {service}: {health.get('status', 'unknown')}")

        if args.json:
            print(json.dumps(results, indent=2))

        print("=" * 50 + "\n")
        return

    # Default: show container status
    containers = monitor.get_container_status()

    if args.json:
        print(json.dumps(containers, indent=2))
    else:
        monitor.print_status_table(containers)

    if args.stats:
        stats = monitor.get_container_stats()
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            monitor.print_stats_table(stats)


if __name__ == '__main__':
    main()
