---
name: dokploy-manager
description: Remote server management for Dokploy production environment. Use for viewing container logs, monitoring services status, checking deployments, restarting services, and troubleshooting production issues. Requires SSH access configured via DOKPLOY_SSH_* environment variables.
---

# Dokploy Server Manager

Remote management toolkit for Telecom-ai production services running on Dokploy.

## Quick Start

### Prerequisites

Set environment variables in `.env`:
```bash
DOKPLOY_SSH_HOST=your-server.com
DOKPLOY_SSH_PORT=22
DOKPLOY_SSH_USER=root
DOKPLOY_SSH_PASSWORD=your-password
```

### Main Capabilities

```bash
# View service logs
python scripts/log_analyzer.py --service api-gateway --tail 100

# Monitor all services
python scripts/service_monitor.py --all

# SSH connector for custom commands
python scripts/ssh_connector.py "docker ps"
```

## Core Capabilities

### 1. Log Analyzer

Fetch and analyze container logs from production.

**Features:**
- Filter by log level (ERROR, WARNING, INFO)
- Search by keywords
- Time-based filtering
- Pattern analysis for common errors

**Usage:**
```bash
python scripts/log_analyzer.py --service rag-agent --level ERROR --tail 200
python scripts/log_analyzer.py --service api-gateway --search "timeout"
```

### 2. Service Monitor

Check status of all Telecom-ai services.

**Features:**
- Container status (running, stopped, restarting)
- Resource usage (CPU, RAM)
- Health check status
- Uptime information

**Usage:**
```bash
python scripts/service_monitor.py --all
python scripts/service_monitor.py --service rag-agent --details
```

### 3. SSH Connector

Execute commands on remote server.

**Features:**
- Secure SSH connection via paramiko
- Environment-based credentials
- Command output capture
- Error handling

**Usage:**
```bash
python scripts/ssh_connector.py "docker ps -a"
python scripts/ssh_connector.py "docker logs rag-agent --tail 50"
```

## Reference Documentation

### Dokploy Commands

See `references/dokploy_commands.md` for:
- Common Docker commands
- Dokploy-specific operations
- Troubleshooting guides
- Service management

## Telecom-ai Services

| Service | Container | Port | Description |
|---------|-----------|------|-------------|
| API Gateway | api-gateway | 8000 | Main entry point |
| RAG Agent | rag-agent | 8001 | AI response generation |
| Crawler Service | crawler-service | 8002 | Website scraping |
| Admin Dashboard | admin-dashboard | 3000 | Management UI |

## Common Operations

### View Logs
```bash
# Last 100 lines
docker logs <container> --tail 100

# Follow logs in real-time
docker logs -f <container>

# Logs with timestamps
docker logs -t <container> --tail 50

# Filter errors
docker logs <container> 2>&1 | grep -i error
```

### Restart Services
```bash
# Restart single service
docker restart <container>

# Restart all project services
docker-compose -f /path/to/compose.yml restart
```

### Check Status
```bash
# All containers
docker ps -a

# Resource usage
docker stats --no-stream

# Container details
docker inspect <container>
```

## Troubleshooting

### Common Issues

1. **Service not responding**
   - Check container status: `docker ps`
   - View recent logs: `docker logs <container> --tail 100`
   - Restart service: `docker restart <container>`

2. **High memory usage**
   - Check stats: `docker stats --no-stream`
   - Review logs for memory leaks
   - Consider increasing limits

3. **Connection errors**
   - Verify network: `docker network ls`
   - Check container connectivity
   - Review firewall rules

### Getting Help

- Check reference documentation
- Review container logs
- Inspect container configuration
- Contact DevOps team
