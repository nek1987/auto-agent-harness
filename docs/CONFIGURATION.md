# Configuration Reference

Complete reference for all Auto-Agent-Harness environment variables.

## Quick Setup

Choose the configuration that matches your deployment:

| Scenario | Configuration File | Command |
|----------|-------------------|---------|
| Local development (OAuth) | [.env.native.example](../.env.native.example) | `cp .env.native.example .env` |
| Docker deployment (API Key) | [.env.docker.example](../.env.docker.example) | `cp .env.docker.example .env` |
| Production (hardened) | [.env.production.example](../.env.production.example) | `cp .env.production.example .env` |

---

## Environment Variables Overview

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| [AUTH_ENABLED](#auth_enabled) | `true` | No | Enable UI authentication |
| [JWT_SECRET_KEY](#jwt_secret_key) | auto | Production: Yes | JWT signing secret |
| [DEFAULT_ADMIN_PASSWORD](#default_admin_password) | `admin` | No | Initial admin password |
| [DATA_DIR](#data_dir) | `~/.autocoder` | No | Data storage directory |
| [ALLOWED_ROOT_DIRECTORY](#allowed_root_directory) | None | Docker: Yes | File operation sandbox |
| [REQUIRE_LOCALHOST](#require_localhost) | `true` | No | Localhost-only access |
| [HOST](#host) | `0.0.0.0` | No | Server bind address |
| [PORT](#port) | `8888` | No | Server port |
| [WORKSPACE_DIR](#workspace_dir) | `./workspace` | Docker: No | Host workspace path |
| [ANTHROPIC_API_KEY](#anthropic_api_key) | None | Docker API: Yes | Claude API key |
| [PROGRESS_N8N_WEBHOOK_URL](#progress_n8n_webhook_url) | None | No | Progress webhook |

---

## Mode Comparison

| Variable | Native | Docker + API Key | Docker + OAuth |
|----------|--------|------------------|----------------|
| AUTH_ENABLED | `true` | `true` | `true` |
| JWT_SECRET_KEY | optional | **required** | **required** |
| DEFAULT_ADMIN_PASSWORD | `admin` | **change it** | **change it** |
| DATA_DIR | ~/.autocoder | /app/data | /app/data |
| ALLOWED_ROOT_DIRECTORY | unset | /workspace | /workspace |
| REQUIRE_LOCALHOST | `true` | `false` | `false` |
| HOST | 127.0.0.1 | 0.0.0.0 | 0.0.0.0 |
| ANTHROPIC_API_KEY | not used | **required** | not used |

---

## Detailed Reference

### Authentication

#### AUTH_ENABLED

| Property | Value |
|----------|-------|
| **Type** | Boolean string (`"true"` / `"false"`) |
| **Default** | `"true"` |
| **Modes** | All |
| **Required** | No |

Enables JWT-based authentication for the web UI. When `false`, the UI is accessible without login.

```bash
AUTH_ENABLED=true   # Require login (recommended)
AUTH_ENABLED=false  # No login required (local dev only)
```

**Security Note**: Always keep enabled when exposing to network or in production.

**Source**: `server/main.py:46`

---

#### JWT_SECRET_KEY

| Property | Value |
|----------|-------|
| **Type** | Hex string (64 characters) |
| **Default** | Auto-generated on startup |
| **Modes** | All |
| **Required** | Production: Yes |

Secret key for signing JWT authentication tokens.

**If not set**:
- A random key is generated on each startup
- User sessions won't persist across restarts
- Users will need to re-login after every restart

**Generate a secure key**:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

```bash
# Example (generate your own!)
JWT_SECRET_KEY=a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456
```

**Security Note**: Keep this secret! Anyone with this key can forge authentication tokens.

**Source**: `server/services/auth_service.py:21`

---

#### DEFAULT_ADMIN_PASSWORD

| Property | Value |
|----------|-------|
| **Type** | String |
| **Default** | `"admin"` |
| **Modes** | All |
| **Required** | No |

Password for the default `admin` user, created automatically on first startup when no users exist.

```bash
DEFAULT_ADMIN_PASSWORD=admin              # Default (development)
DEFAULT_ADMIN_PASSWORD=MyStr0ng!Pass#123  # Production (16+ chars)
```

**Security Note**: Change immediately in production! Use 16+ characters with mixed case, numbers, and symbols.

**Source**: `server/services/auth_service.py:209`

---

### Path Configuration

#### DATA_DIR

| Property | Value |
|----------|-------|
| **Type** | Absolute path |
| **Default** | `~/.autocoder` (expands to home directory) |
| **Modes** | All |
| **Required** | No |

Storage directory for persistent application data:
- `users.json` - User accounts and passwords
- `settings.json` - Application settings
- `registry.db` - Project registry database
- `credentials.json` - API credentials

```bash
DATA_DIR=~/.autocoder        # Native mode default
DATA_DIR=/app/data           # Docker mode
DATA_DIR=/var/lib/autocoder  # Custom location
```

**Note**: This path is always allowed for file access regardless of `ALLOWED_ROOT_DIRECTORY`.

**Source**: `server/services/auth_service.py:27`, `server/lib/path_security.py:34`, `registry.py:90`

---

#### ALLOWED_ROOT_DIRECTORY

| Property | Value |
|----------|-------|
| **Type** | Absolute path |
| **Default** | None (all paths allowed) |
| **Modes** | Docker: Required, Native: Optional |
| **Required** | Docker: Yes |

Restricts all file system operations to this directory. Prevents the agent from accessing files outside the workspace.

```bash
# Docker mode (required)
ALLOWED_ROOT_DIRECTORY=/workspace

# Native mode - sandbox to specific folder
ALLOWED_ROOT_DIRECTORY=/Users/me/projects

# Native mode - no restriction (default)
# ALLOWED_ROOT_DIRECTORY=
```

**Security Note**: Always set in Docker to prevent container escape attacks.

**Source**: `server/lib/path_security.py:30`

---

#### WORKSPACE_DIR

| Property | Value |
|----------|-------|
| **Type** | Host path (relative or absolute) |
| **Default** | `./workspace` |
| **Modes** | Docker only |
| **Required** | No |

Host directory mounted as `/workspace` inside the Docker container. This is where your projects are stored.

```bash
WORKSPACE_DIR=./workspace              # Relative to docker-compose.yml
WORKSPACE_DIR=/opt/autocoder/projects  # Absolute path
```

**Note**: Ensure the directory exists and has proper permissions:
```bash
mkdir -p ./workspace
# For Docker: chown -R 1000:1000 ./workspace
```

**Source**: `docker-compose.yml:66`

---

### Server Configuration

#### HOST

| Property | Value |
|----------|-------|
| **Type** | IP address |
| **Default** | `"0.0.0.0"` |
| **Modes** | All |
| **Required** | No |

Network interface to bind the HTTP server to.

```bash
HOST=127.0.0.1  # Localhost only (native mode)
HOST=0.0.0.0    # All interfaces (Docker mode)
```

**Source**: `docker-compose.yml:55`

---

#### PORT

| Property | Value |
|----------|-------|
| **Type** | Integer (1-65535) |
| **Default** | `8888` |
| **Modes** | All |
| **Required** | No |

Port for the HTTP server. Access the UI at `http://localhost:{PORT}`.

```bash
PORT=8888  # Default
PORT=3000  # Custom port
```

**Source**: `docker-compose.yml:36,56`

---

#### REQUIRE_LOCALHOST

| Property | Value |
|----------|-------|
| **Type** | Boolean string (`"true"` / `"false"`) |
| **Default** | `"true"` |
| **Modes** | All |
| **Required** | No |

When `true`, only accepts connections from localhost (127.0.0.1).

```bash
REQUIRE_LOCALHOST=true   # Native mode (security)
REQUIRE_LOCALHOST=false  # Docker mode (required for networking)
```

**Note**:
- Native mode: Keep `true` for security
- Docker mode: Set `false` (container networking requires it)
- Production: Set `false` and use reverse proxy for security

**Source**: `server/lib/path_security.py:40`

---

### Claude API

#### ANTHROPIC_API_KEY

| Property | Value |
|----------|-------|
| **Type** | String (API key format) |
| **Default** | None |
| **Modes** | Docker + API Key mode only |
| **Required** | Docker API mode: Yes |

Your Anthropic API key for Claude API access. Required when not using OAuth subscription.

**Get a key**: https://console.anthropic.com/

```bash
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Authentication Modes**:
- **Native mode**: Not needed (uses `claude login` OAuth)
- **Docker + API Key**: Required (pay-per-token)
- **Docker + OAuth**: Not needed (uses mounted credentials)

**Security Note**:
- Never commit to version control
- Use environment-specific keys (dev/staging/prod)
- Automatically redacted from logs

**Source**: `docker-compose.yml:46`, `client.py`

---

### Integrations

#### PROGRESS_N8N_WEBHOOK_URL

| Property | Value |
|----------|-------|
| **Type** | URL |
| **Default** | None (webhook disabled) |
| **Modes** | All |
| **Required** | No |

Webhook URL for sending progress notifications. Useful for monitoring dashboards.

**Sends POST request when**:
- Test pass count increases
- Agent completes a feature

```bash
PROGRESS_N8N_WEBHOOK_URL=https://n8n.example.com/webhook/autocoder
```

**Payload format**:
```json
{
  "project": "project-name",
  "passing": 5,
  "total": 10,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Source**: `progress.py:16`

---

### Internal Variables

#### PROJECT_DIR

| Property | Value |
|----------|-------|
| **Type** | Path |
| **Default** | Current directory |
| **Modes** | Internal |
| **Required** | Never set manually |

Set internally by the agent process when starting MCP servers. **Do not configure manually**.

**Source**: `mcp_server/feature_mcp.py:38`, `client.py:240`

---

## Security Best Practices

### Development

```bash
# .env for local development
AUTH_ENABLED=true
JWT_SECRET_KEY=            # Auto-generated is fine
DEFAULT_ADMIN_PASSWORD=admin
REQUIRE_LOCALHOST=true
```

### Production

```bash
# .env for production
AUTH_ENABLED=true
JWT_SECRET_KEY=<64-char-hex>           # REQUIRED: unique, secure
DEFAULT_ADMIN_PASSWORD=<16+chars>      # REQUIRED: strong password
ALLOWED_ROOT_DIRECTORY=/workspace      # REQUIRED: sandbox
REQUIRE_LOCALHOST=false                # Use reverse proxy
```

### Secrets Management

1. **Never commit `.env` files** - They're in `.gitignore`
2. **Use different keys per environment** - Dev, staging, production
3. **Rotate JWT_SECRET_KEY periodically** - Invalidates all sessions
4. **Use secrets manager in production** - HashiCorp Vault, AWS Secrets Manager

---

## Troubleshooting

### "No Claude credentials found"

**Native mode**: Run `claude login` to authenticate via browser.

**Docker mode**: Check `ANTHROPIC_API_KEY` is set in `.env`.

### "JWT token invalid" or sessions not persisting

Generate a persistent `JWT_SECRET_KEY`:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Add to `.env` and restart.

### "Permission denied" on workspace

```bash
# Docker uses UID 1000
sudo chown -R 1000:1000 ./workspace
```

### Environment variable not taking effect

1. Check `.env` file is in the project root (same directory as `docker-compose.yml`)
2. Restart the application after changes
3. For Docker: `docker-compose down && docker-compose up -d`

---

## Related Documentation

- [Deployment Guide](DEPLOYMENT.md) - Server deployment instructions
- [README](../README.md) - Quick start and overview
- [CLAUDE.md](../CLAUDE.md) - Claude Code integration
