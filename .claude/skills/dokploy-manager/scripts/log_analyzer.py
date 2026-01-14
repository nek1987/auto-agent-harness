#!/usr/bin/env python3
"""
Log Analyzer for Dokploy Services
Fetches and analyzes container logs from production server.
"""

import os
import sys
import argparse
import re
from typing import List, Dict, Optional
from datetime import datetime

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssh_connector import SSHConnector


class LogAnalyzer:
    """Analyze Docker container logs from remote server."""

    # Known Telecom-ai services
    SERVICES = {
        'api-gateway': 'API Gateway - Main entry point',
        'rag-agent': 'RAG Agent - AI response generation',
        'crawler-service': 'Crawler Service - Website scraping',
        'admin-dashboard': 'Admin Dashboard - Management UI',
    }

    # Log level patterns
    LOG_PATTERNS = {
        'ERROR': r'\b(ERROR|Error|error|CRITICAL|FATAL)\b',
        'WARNING': r'\b(WARNING|Warning|warning|WARN|warn)\b',
        'INFO': r'\b(INFO|Info|info)\b',
        'DEBUG': r'\b(DEBUG|Debug|debug)\b',
    }

    def __init__(self):
        self.ssh = SSHConnector()

    def get_logs(
        self,
        service: str,
        tail: int = 100,
        since: Optional[str] = None
    ) -> str:
        """
        Fetch logs from service container.

        Args:
            service: Service/container name
            tail: Number of lines to fetch
            since: Time filter (e.g., "1h", "30m")
        """
        cmd = f'docker logs {service} --tail {tail}'
        if since:
            cmd += f' --since {since}'
        cmd += ' 2>&1'

        stdout, stderr, code = self.ssh.execute(cmd, timeout=60)
        return stdout if code == 0 else f"Error: {stderr}"

    def filter_by_level(self, logs: str, level: str) -> List[str]:
        """Filter log lines by level."""
        if level not in self.LOG_PATTERNS:
            return logs.split('\n')

        pattern = self.LOG_PATTERNS[level]
        filtered = []
        for line in logs.split('\n'):
            if re.search(pattern, line):
                filtered.append(line)
        return filtered

    def search_logs(self, logs: str, keyword: str) -> List[str]:
        """Search logs for keyword."""
        matches = []
        for line in logs.split('\n'):
            if keyword.lower() in line.lower():
                matches.append(line)
        return matches

    def analyze_errors(self, logs: str) -> Dict[str, int]:
        """Analyze error patterns in logs."""
        error_patterns = {
            'timeout': r'timeout|timed out',
            'connection': r'connection (refused|reset|error)',
            'memory': r'memory|oom|out of memory',
            'database': r'database|postgres|sql',
            'api': r'api (error|failed)|status (4\d{2}|5\d{2})',
            'auth': r'auth|unauthorized|forbidden|401|403',
        }

        results = {}
        for name, pattern in error_patterns.items():
            matches = re.findall(pattern, logs, re.IGNORECASE)
            if matches:
                results[name] = len(matches)

        return results

    def get_service_summary(self) -> str:
        """Get summary of all services."""
        output = []
        output.append("=" * 60)
        output.append("Telecom-ai Services Log Summary")
        output.append("=" * 60)

        for service, description in self.SERVICES.items():
            output.append(f"\n{service}: {description}")
            output.append("-" * 40)

            logs = self.get_logs(service, tail=50)
            errors = self.filter_by_level(logs, 'ERROR')
            warnings = self.filter_by_level(logs, 'WARNING')

            output.append(f"  Errors: {len(errors)}")
            output.append(f"  Warnings: {len(warnings)}")

            if errors:
                output.append("  Recent errors:")
                for err in errors[-3:]:
                    output.append(f"    - {err[:100]}...")

        return '\n'.join(output)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Analyze logs from Dokploy services'
    )
    parser.add_argument(
        '--service', '-s',
        help='Service name (api-gateway, rag-agent, crawler-service, admin-dashboard)'
    )
    parser.add_argument(
        '--tail', '-t',
        type=int,
        default=100,
        help='Number of log lines (default: 100)'
    )
    parser.add_argument(
        '--level', '-l',
        choices=['ERROR', 'WARNING', 'INFO', 'DEBUG'],
        help='Filter by log level'
    )
    parser.add_argument(
        '--search', '-q',
        help='Search for keyword in logs'
    )
    parser.add_argument(
        '--since',
        help='Show logs since time (e.g., "1h", "30m")'
    )
    parser.add_argument(
        '--analyze',
        action='store_true',
        help='Analyze error patterns'
    )
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Show summary of all services'
    )
    parser.add_argument(
        '--list-services',
        action='store_true',
        help='List available services'
    )

    args = parser.parse_args()

    analyzer = LogAnalyzer()

    if args.list_services:
        print("Available services:")
        for name, desc in analyzer.SERVICES.items():
            print(f"  {name}: {desc}")
        return

    if args.summary:
        print(analyzer.get_service_summary())
        return

    if not args.service:
        parser.print_help()
        print("\nError: --service is required (or use --summary for all services)")
        return

    # Get logs
    logs = analyzer.get_logs(args.service, args.tail, args.since)

    # Filter by level
    if args.level:
        lines = analyzer.filter_by_level(logs, args.level)
        logs = '\n'.join(lines)

    # Search
    if args.search:
        lines = analyzer.search_logs(logs, args.search)
        logs = '\n'.join(lines)

    # Analyze
    if args.analyze:
        print(f"Error Analysis for {args.service}:")
        print("-" * 40)
        errors = analyzer.analyze_errors(logs)
        if errors:
            for category, count in sorted(errors.items(), key=lambda x: -x[1]):
                print(f"  {category}: {count} occurrences")
        else:
            print("  No error patterns detected")
        print()

    print(logs)


if __name__ == '__main__':
    main()
