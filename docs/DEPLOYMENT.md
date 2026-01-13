# Server Deployment Guide

Guide for deploying Auto-Agent-Harness on a server.

---

## Table of Contents

1. [Server Requirements](#server-requirements)
2. [Claude Authentication Modes](#claude-authentication-modes)
3. [Mode 1: Native (OAuth Subscription)](#mode-1-native-oauth-subscription)
4. [Mode 2: Docker + API Key](#mode-2-docker--api-key)
5. [Mode 3: Docker + OAuth (Hybrid)](#mode-3-docker--oauth-hybrid)
6. [Systemd Service (Production)](#systemd-service-production)
7. [Updating the Application](#updating-the-application)
8. [Logging](#logging)
9. [Importing Existing Projects](#importing-existing-projects)
10. [Configuration](#configuration)
11. [Nginx Reverse Proxy](#nginx-reverse-proxy)
12. [Troubleshooting](#troubleshooting)

---

## Server Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 2 GB | 4 GB |
| CPU | 2 cores | 4 cores |
| Disk | 20 GB | 50 GB |
| Python | 3.11+ | 3.12 |
| Docker | 20.10+ | 24.0+ |
| Docker Compose | 2.0+ | 2.20+ |

---

## Claude Authentication Modes

Auto-Agent-Harness supports **three authentication modes** with Claude API:

| Mode | Environment | Auth Method | Cost | Best For |
|------|-------------|-------------|------|----------|
| **Native** | Local machine | OAuth (subscription) | Claude Pro/Max subscription | Development |
| **Docker + API Key** | Server/cloud | API Key | Pay-per-token | Simple production |
| **Docker + OAuth** | Server/cloud | OAuth (mounted) | Subscription | Cost-effective production |

### Mode Comparison

```
┌─────────────────────────────────────────────────────────────────┐
│                     NATIVE MODE                                  │
│  ✅ Uses Claude Pro/Max subscription                            │
│  ✅ Simple setup (claude login)                                 │
│  ❌ Requires local machine with browser                         │
├─────────────────────────────────────────────────────────────────┤
│                  DOCKER + API KEY                                │
│  ✅ Works on any server                                         │
│  ✅ Simple deployment                                           │
│  ❌ Pay for each token                                          │
├─────────────────────────────────────────────────────────────────┤
│                  DOCKER + OAUTH                                  │
│  ✅ Works on server                                             │
│  ✅ Uses subscription (cost savings)                            │
│  ❌ Need to periodically refresh tokens                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Mode 1: Native (OAuth Subscription)

**Best for:** Local development, using Claude Pro/Max subscription.

### Requirements
- Local machine (Windows/macOS/Linux)
- Browser for OAuth
- Claude CLI (`npm install -g @anthropic-ai/claude-code`)

### Installation

```bash
# 1. Clone repository
git clone https://github.com/nek1987/auto-agent-harness.git
cd auto-agent-harness

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.native.example .env

# 5. Login to Claude (opens browser)
claude login

# 6. Start
./start.sh  # Linux/macOS
# or: start.bat  # Windows
```

### How It Works

```
┌─────────────────────────────────────────────────┐
│              Your Machine                        │
│  ┌─────────────┐     ┌──────────────────────┐  │
│  │ claude login│ ──► │ ~/.claude/           │  │
│  │  (browser)  │     │  .credentials.json   │  │
│  └─────────────┘     └──────────────────────┘  │
│         │                      │               │
│         ▼                      ▼               │
│  ┌─────────────────────────────────────────┐  │
│  │        auto-agent-harness               │  │
│  │  Python process (NOT Docker)            │  │
│  │  Uses Claude Pro/Max subscription       │  │
│  └─────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

---

## Mode 2: Docker + API Key

**Best for:** Simple server deployment, cloud platforms.

### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/nek1987/auto-agent-harness.git
cd auto-agent-harness

# 2. Interactive setup
./scripts/setup-docker-auth.sh --api-key
# Enter your ANTHROPIC_API_KEY

# 3. Start
docker-compose up -d --build
```

### Manual Installation

```bash
# 1. Clone
git clone https://github.com/nek1987/auto-agent-harness.git
cd auto-agent-harness

# 2. Create workspace
mkdir -p workspace

# 3. Configure environment
cp .env.docker.example .env

# 4. Edit .env - add your API key and generate JWT secret
# ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxx
# JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# 5. Start
docker-compose up -d --build

# 6. Verify
curl http://localhost:8888/api/health
```

### How It Works

```
┌─────────────────────────────────────────────────┐
│                   Server                         │
│  ┌─────────────────────────────────────────┐   │
│  │           Docker Container               │   │
│  │  ┌─────────────────────────────────┐    │   │
│  │  │  ANTHROPIC_API_KEY=sk-ant-xxx   │    │   │
│  │  │  auto-agent-harness             │    │   │
│  │  │  (pays per token)               │    │   │
│  │  └─────────────────────────────────┘    │   │
│  └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

---

## Mode 3: Docker + OAuth (Hybrid)

**Best for:** Server deployment using Claude Pro/Max subscription.

### How It Works

1. **Once** on local machine: `claude login` + extract tokens
2. Tokens are copied to server
3. Docker uses subscription via extracted tokens

```
┌─────────────────────────────────────────────────┐
│              Local Machine (once)               │
│  ┌─────────────┐     ┌──────────────────────┐  │
│  │ claude login│ ──► │ ~/.claude/           │  │
│  │  (browser)  │     │  .credentials.json   │  │
│  └─────────────┘     └──────────────────────┘  │
│                              │                  │
│         ┌────────────────────┘                  │
│         ▼                                       │
│  ┌──────────────────┐                          │
│  │ extract-token.sh │  ──────────────────┐     │
│  └──────────────────┘                    │     │
└──────────────────────────────────────────│─────┘
                                           │
                   (copy to server)        │
                                           ▼
┌─────────────────────────────────────────────────┐
│                   Server                         │
│  ┌─────────────────────────────────────────┐   │
│  │           Docker Container               │   │
│  │  ┌─────────────────────────────────┐    │   │
│  │  │  Volume: credentials (mounted)  │    │   │
│  │  │  auto-agent-harness             │    │   │
│  │  │  (uses subscription)            │    │   │
│  │  └─────────────────────────────────┘    │   │
│  └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

### Installation

#### On Local Machine:

```bash
# 1. Clone repository
git clone https://github.com/nek1987/auto-agent-harness.git
cd auto-agent-harness

# 2. Login to Claude (if not already done)
claude login

# 3. Extract credentials
./scripts/setup-docker-auth.sh --oauth-extract

# 4. Copy to server
rsync -avz . user@server:/opt/auto-agent-harness/auto-agent-harness/
```

#### On Server:

```bash
# 1. Navigate to directory
cd /opt/auto-agent-harness/auto-agent-harness

# 2. Start
docker-compose up -d --build

# 3. Verify
curl http://localhost:8888/api/health
```

### Refreshing Tokens

OAuth tokens expire periodically. To refresh:

```bash
# On local machine
cd auto-agent-harness
./scripts/setup-docker-auth.sh --oauth-extract

# Copy updated credentials to server
rsync -avz .docker-credentials/ user@server:/opt/auto-agent-harness/auto-agent-harness/.docker-credentials/

# On server: restart container
ssh user@server "cd /opt/auto-agent-harness/auto-agent-harness && docker-compose restart"
```

---

## Systemd Service (Production)

For **Native Mode** production deployments, use systemd for:
- Auto-start on boot
- Auto-restart on crash
- Background operation (survives SSH disconnect)
- Structured logging to `/var/log/`

### Quick Installation

```bash
cd /path/to/auto-agent-harness

# Make installer executable
chmod +x deploy/install_service.sh

# Run installer (creates logs dir, installs service)
./deploy/install_service.sh
```

### Manual Installation

```bash
# 1. Create log directory
sudo mkdir -p /var/log/auto-agent
sudo chown $USER:$USER /var/log/auto-agent

# 2. Copy service file
sudo cp deploy/auto-agent.service /etc/systemd/system/

# 3. Edit paths in service file
sudo nano /etc/systemd/system/auto-agent.service
# Replace /path/to/auto-agent-harness with actual path
# Replace <username> and <group> with your user

# 4. Enable and start
sudo systemctl daemon-reload
sudo systemctl enable auto-agent
sudo systemctl start auto-agent
```

### Service Commands

```bash
# Status
sudo systemctl status auto-agent

# Start/Stop/Restart
sudo systemctl start auto-agent
sudo systemctl stop auto-agent
sudo systemctl restart auto-agent

# Enable/Disable autostart
sudo systemctl enable auto-agent
sudo systemctl disable auto-agent

# View logs
sudo journalctl -u auto-agent -f
```

### Service Configuration

The service file is at `/etc/systemd/system/auto-agent.service`:

```ini
[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/auto-agent-harness
Environment="HOST=0.0.0.0"
Environment="PORT=8888"
ExecStart=/path/to/auto-agent-harness/venv/bin/python -m uvicorn server.main:app --host 0.0.0.0 --port 8888
Restart=always
RestartSec=5
```

---

## Updating the Application

### Native Mode (with Systemd)

```bash
cd /path/to/auto-agent-harness

# 1. Stop service
sudo systemctl stop auto-agent

# 2. Pull latest code
git pull origin main

# 3. Update Python dependencies
source venv/bin/activate
pip install -r requirements.txt

# 4. Rebuild frontend (if UI changed)
cd ui
npm install
npm run build
cd ..

# 5. Restart service
sudo systemctl start auto-agent

# 6. Verify
sudo systemctl status auto-agent
tail -f /var/log/auto-agent/server.log
```

### Quick Update Script

Create `update.sh` in project root:

```bash
#!/bin/bash
set -e

echo "Stopping service..."
sudo systemctl stop auto-agent

echo "Pulling latest code..."
git pull origin main

echo "Updating Python dependencies..."
source venv/bin/activate
pip install -r requirements.txt --quiet

echo "Rebuilding frontend..."
cd ui
npm install --silent
npm run build
cd ..

echo "Starting service..."
sudo systemctl start auto-agent

echo "Done! Checking status..."
sudo systemctl status auto-agent --no-pager
```

Usage:
```bash
chmod +x update.sh
./update.sh
```

### Docker Mode

```bash
cd /path/to/auto-agent-harness

# 1. Pull latest code
git pull origin main

# 2. Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 3. Verify
docker-compose logs -f
```

### Updating Without Downtime (Blue-Green)

For zero-downtime updates, use a reverse proxy with health checks:

```bash
# Build new container with different name
docker-compose -f docker-compose.yml -p auto-agent-new up -d --build

# Wait for health check
sleep 10
curl http://localhost:8889/api/health

# Switch traffic (update nginx upstream)
# Then stop old container
docker-compose -p auto-agent-old down
```

---

## Logging

### Log Locations

| Mode | Location | Description |
|------|----------|-------------|
| **Systemd** | `/var/log/auto-agent/server.log` | Application logs |
| **Systemd** | `/var/log/auto-agent/error.log` | Error logs |
| **Systemd** | `journalctl -u auto-agent` | System journal |
| **Docker** | `docker-compose logs` | Container logs |
| **Native (manual)** | stdout | Console output |

### Log Format

```
2025-01-13 12:34:56 [INFO] server.main: POST /api/projects/test/agent/start status=200 duration=0.123s client=192.168.1.10
2025-01-13 12:34:57 [INFO] server.main: GET /api/projects/test/features status=200 duration=0.045s client=192.168.1.10
2025-01-13 12:35:00 [ERROR] server.main: Agent crashed: Connection refused
```

### Viewing Logs

```bash
# Real-time (systemd)
sudo journalctl -u auto-agent -f

# Real-time (file)
tail -f /var/log/auto-agent/server.log

# Last 100 lines
tail -100 /var/log/auto-agent/server.log

# Errors only
tail -f /var/log/auto-agent/error.log

# Search logs
grep "ERROR" /var/log/auto-agent/server.log
grep "agent/start" /var/log/auto-agent/server.log
```

### Log Rotation

Logs are automatically rotated by logrotate:
- **Daily** rotation
- **14 days** retention
- **Compressed** old logs (gzip)

Configuration at `/etc/logrotate.d/auto-agent`:

```
/var/log/auto-agent/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
}
```

### Increasing Log Verbosity

For debugging, set log level in `.env`:

```bash
# Add to .env
LOG_LEVEL=DEBUG
```

Or via environment variable:

```bash
LOG_LEVEL=DEBUG python -m uvicorn server.main:app
```

---

## Importing Existing Projects

After installation (any mode), you can import existing projects.

### Via UI

1. Open UI: `http://server:8888`
2. Click **"Import Existing"**
3. Select project folder
4. Choose mode:
   - **Analysis Mode** - Agent analyzes code, creates features
   - **Skip Analysis** - Just registers the project

### Via CLI (Docker)

```bash
# 1. Copy project to workspace
cp -r /path/to/your-project /opt/auto-agent-harness/workspace/

# 2. Register via API
curl -X POST http://localhost:8888/api/projects/import \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"path": "/workspace/your-project", "name": "your-project"}'
```

### Via CLI (Native)

```bash
# 1. Start start.py
python start.py

# 2. Select "Import existing project"
# 3. Enter path to project
```

---

## Configuration

> **Full Reference**: See [CONFIGURATION.md](CONFIGURATION.md)

### Environment Variables

| Variable | Description | Default | Mode |
|----------|-------------|---------|------|
| `ANTHROPIC_API_KEY` | Anthropic API key | - | Docker + API Key |
| `AUTH_ENABLED` | Enable UI authentication | `true` | All |
| `JWT_SECRET_KEY` | JWT token secret | **Required** | All |
| `DEFAULT_ADMIN_PASSWORD` | Admin password | `admin` | All |
| `PORT` | Server port | `8888` | All |
| `WORKSPACE_DIR` | Projects directory | `./workspace` | Docker |
| `ALLOWED_ROOT_DIRECTORY` | Container root | `/workspace` | Docker |
| `DATA_DIR` | Data directory | `/app/data` | Docker |
| `REQUIRE_LOCALHOST` | Localhost only | `false` | Docker |

### Directory Structure

```
/opt/auto-agent-harness/
├── auto-agent-harness/     # Application repository
│   ├── docker-compose.yml
│   ├── Dockerfile
│   ├── .env                # Configuration
│   ├── .docker-credentials/# OAuth credentials (Mode 3)
│   └── scripts/
│       ├── extract-claude-credentials.sh
│       └── setup-docker-auth.sh
└── workspace/              # Projects directory
    ├── project-1/
    └── project-2/
```

---

## Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name auto-agent-harness.your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name auto-agent-harness.your-domain.com;

    ssl_certificate /etc/letsencrypt/live/auto-agent-harness.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/auto-agent-harness.your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8888;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;  # WebSocket timeout
    }
}
```

---

## Troubleshooting

### Problem: "No Claude credentials found"

**Cause:** OAuth credentials not found.

**Solution:**
```bash
# Native mode
claude login

# Docker mode - check volume mount
docker-compose exec auto-agent-harness ls -la /home/auto-agent/.claude/
```

### Problem: "API key invalid"

**Cause:** Invalid or expired API key.

**Solution:**
```bash
# Check .env
grep ANTHROPIC_API_KEY .env

# Check that key is passed to container
docker-compose exec auto-agent-harness env | grep ANTHROPIC
```

### Problem: "OAuth token expired"

**Cause:** OAuth tokens expired (typically after 7 days).

**Solution:**
```bash
# On local machine
claude login  # Refresh tokens
./scripts/setup-docker-auth.sh --oauth-extract

# Copy to server and restart
rsync -avz .docker-credentials/ user@server:/path/to/.docker-credentials/
ssh user@server "cd /path/to/harness && docker-compose restart"
```

### Problem: Container won't start

```bash
# Check logs
docker-compose logs auto-agent-harness

# Check .env
cat .env | grep -v "^#" | grep -v "^$"

# Common issues:
# 1. JWT_SECRET_KEY not set
# 2. Port already in use
# 3. Not enough memory
```

### Problem: Permission denied

```bash
# Check workspace permissions
ls -la workspace/

# Fix (Docker user has UID 1000)
sudo chown -R 1000:1000 workspace/
```

---

## Useful Commands

```bash
# Status
docker-compose ps

# Logs
docker-compose logs -f

# Restart
docker-compose restart

# Rebuild
docker-compose build --no-cache && docker-compose up -d

# Shell into container
docker-compose exec auto-agent-harness bash

# Backup data
docker run --rm -v auto-agent-harness-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/auto-agent-harness-backup.tar.gz /data

# Check credentials in container
docker-compose exec auto-agent-harness cat /home/auto-agent/.claude/.credentials.json | head -c 100
```

---

## Quick Reference

### Native Mode
```bash
git clone https://github.com/nek1987/auto-agent-harness.git
cd auto-agent-harness
pip install -r requirements.txt
cp .env.native.example .env
claude login
./start.sh
```

### Docker + API Key
```bash
git clone https://github.com/nek1987/auto-agent-harness.git
cd auto-agent-harness
cp .env.docker.example .env
# Edit .env: add ANTHROPIC_API_KEY, generate JWT_SECRET_KEY
docker-compose up -d --build
```

### Docker + OAuth
```bash
# Local machine
git clone https://github.com/nek1987/auto-agent-harness.git
cd auto-agent-harness
claude login
./scripts/setup-docker-auth.sh --oauth-extract
rsync -avz . user@server:/opt/auto-agent-harness/auto-agent-harness/

# Server
cd /opt/auto-agent-harness/auto-agent-harness
docker-compose up -d --build
```

---

## Related Documentation

- [Configuration Reference](CONFIGURATION.md) - All environment variables
- [README](../README.md) - Project overview and quick start
- [CLAUDE.md](../CLAUDE.md) - Claude Code integration
