# Dokploy Commands Reference

Quick reference for managing Telecom-ai services on Dokploy.

## Container Management

### View Containers

```bash
# List running containers
docker ps

# List all containers (including stopped)
docker ps -a

# List containers with specific format
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Filter by name
docker ps --filter "name=rag-agent"
```

### Container Logs

```bash
# View last 100 lines
docker logs <container> --tail 100

# Follow logs in real-time
docker logs -f <container>

# Logs with timestamps
docker logs -t <container>

# Logs since specific time
docker logs --since "1h" <container>
docker logs --since "2024-01-01T00:00:00" <container>

# Filter errors
docker logs <container> 2>&1 | grep -i error

# Filter by pattern
docker logs <container> 2>&1 | grep -E "(ERROR|WARNING)"
```

### Start/Stop/Restart

```bash
# Start container
docker start <container>

# Stop container
docker stop <container>

# Restart container
docker restart <container>

# Force kill
docker kill <container>
```

### Resource Usage

```bash
# Real-time stats
docker stats

# One-time stats snapshot
docker stats --no-stream

# Stats for specific container
docker stats <container> --no-stream

# Detailed container info
docker inspect <container>
```

## Telecom-ai Services

### Service Names

| Service | Container Name | Port |
|---------|---------------|------|
| API Gateway | api-gateway | 8000 |
| RAG Agent | rag-agent | 8001 |
| Crawler Service | crawler-service | 8002 |
| Admin Dashboard | admin-dashboard | 3000 |

### Common Operations

```bash
# Check all services
docker ps --filter "name=api-gateway" --filter "name=rag-agent" --filter "name=crawler-service"

# Restart all services
docker restart api-gateway rag-agent crawler-service

# View all service logs
for svc in api-gateway rag-agent crawler-service; do
  echo "=== $svc ==="
  docker logs $svc --tail 20
done
```

## Troubleshooting

### Service Not Responding

```bash
# 1. Check if container is running
docker ps | grep <service>

# 2. Check container health
docker inspect <service> --format '{{.State.Health.Status}}'

# 3. View recent logs
docker logs <service> --tail 100

# 4. Check resource usage
docker stats <service> --no-stream

# 5. Restart if needed
docker restart <service>
```

### High Memory Usage

```bash
# Check memory stats
docker stats --no-stream --format "{{.Name}}: {{.MemUsage}} ({{.MemPerc}})"

# View container limits
docker inspect <service> --format '{{.HostConfig.Memory}}'

# Check for OOM kills
docker inspect <service> --format '{{.State.OOMKilled}}'
```

### Network Issues

```bash
# List networks
docker network ls

# Inspect network
docker network inspect <network>

# Check container network
docker inspect <service> --format '{{.NetworkSettings.Networks}}'

# Test connectivity from container
docker exec <service> ping <target>
docker exec <service> curl -v http://target:port
```

### Log Analysis Patterns

```bash
# Count errors by type
docker logs <service> 2>&1 | grep -i error | sort | uniq -c | sort -rn

# Find timeout errors
docker logs <service> 2>&1 | grep -i timeout

# Find connection errors
docker logs <service> 2>&1 | grep -iE "connection (refused|reset|error)"

# Find database errors
docker logs <service> 2>&1 | grep -iE "(postgres|database|sql)"

# Last N errors
docker logs <service> 2>&1 | grep -i error | tail -20
```

## Dokploy-Specific

### Dokploy Project Structure

```
/opt/dokploy/
├── docker-compose.yml
├── applications/
│   └── <project-id>/
│       ├── code/
│       └── docker-compose.yml
└── volumes/
```

### Dokploy Commands

```bash
# Check Dokploy status
systemctl status dokploy

# View Dokploy logs
journalctl -u dokploy -f

# Restart Dokploy
systemctl restart dokploy
```

## Backup & Recovery

### Export Container State

```bash
# Export container filesystem
docker export <container> > backup.tar

# Save image
docker save <image> > image.tar
```

### Database Backup (if applicable)

```bash
# PostgreSQL backup
docker exec postgres pg_dump -U user database > backup.sql

# Restore
docker exec -i postgres psql -U user database < backup.sql
```

## Quick Diagnostics Script

```bash
#!/bin/bash
echo "=== Telecom-ai Health Check ==="
echo ""
echo "1. Container Status:"
docker ps --format "{{.Names}}: {{.Status}}"
echo ""
echo "2. Resource Usage:"
docker stats --no-stream --format "{{.Name}}: CPU={{.CPUPerc}} MEM={{.MemPerc}}"
echo ""
echo "3. Recent Errors (last hour):"
for svc in api-gateway rag-agent crawler-service; do
  errors=$(docker logs $svc --since 1h 2>&1 | grep -ci error)
  echo "  $svc: $errors errors"
done
echo ""
echo "=== Done ==="
```
