# Auto-Agent-Harness

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue.svg)](https://www.typescriptlang.org/)
[![React 18](https://img.shields.io/badge/React-18-61dafb.svg)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg)](https://www.docker.com/)

A production-ready autonomous coding agent system with a React-based UI. Built on the Claude Agent SDK, it implements a two-agent pattern with comprehensive protection mechanisms for safe, long-running autonomous code generation.

## Features

- **Two-Agent Pattern** - Initializer creates features, Coding agent implements them
- **Real-time Web UI** - Kanban board with live progress via WebSocket
- **JWT Authentication** - Secure httpOnly cookies with refresh token rotation
- **Path Isolation** - Sandbox file operations to allowed directories
- **Loop Detection** - Prevents infinite loops with 4 detection strategies
- **Checkpoints & Rollback** - Git + database snapshots for recovery
- **State Machine** - Validated agent lifecycle transitions
- **Multi-Spec Support** - Split specs for frontend/backend/mobile
- **Feature Dependencies** - Topological ordering with cycle detection
- **Docker Ready** - Multi-stage build for production deployment

---

## Quick Start

### Prerequisites

**Claude Code CLI** (required):
```bash
# macOS / Linux
curl -fsSL https://claude.ai/install.sh | bash

# Windows (PowerShell)
irm https://claude.ai/install.ps1 | iex
```

**Authentication**: Claude Pro/Max subscription or Anthropic API key.

### Option 1: Web UI (Recommended)

```bash
# Windows
start_ui.bat

# macOS / Linux
./start_ui.sh
```

Opens at `http://localhost:5173` with:
- Project management and creation
- Kanban board view of features
- Real-time agent output streaming
- Start/pause/stop controls

### Option 2: CLI Mode

```bash
# Windows
start.bat

# macOS / Linux
./start.sh
```

### Option 3: Docker

```bash
docker-compose up -d
```

Access at `http://localhost:8888`

---

## Architecture

```
                    +------------------+
                    |   React Web UI   |
                    |   (TypeScript)   |
                    +--------+---------+
                             |
                    WebSocket + REST API
                             |
                    +--------+---------+
                    |   FastAPI Server |
                    |   + Auth Layer   |
                    +--------+---------+
                             |
         +-------------------+-------------------+
         |                   |                   |
+--------v--------+ +--------v--------+ +--------v--------+
|  Feature MCP    | |  Protection     | |  Path Security  |
|  Server         | |  Layer          | |  Module         |
+-----------------+ +-----------------+ +-----------------+
         |                   |
         |           +-------+-------+
         |           |       |       |
         |      +----v-+ +---v---+ +-v--------+
         |      |State | |Loop   | |Checkpoint|
         |      |Machine| |Detector| |Manager  |
         |      +------+ +-------+ +----------+
         |
+--------v--------+
|  Claude Agent   |
|  SDK Client     |
+-----------------+
```

### Core Modules

| Module | Description |
|--------|-------------|
| `agent.py` | Agent session loop using Claude SDK |
| `client.py` | ClaudeSDKClient with security hooks |
| `security.py` | Bash command allowlist validation |
| `registry.py` | Cross-platform project registry (SQLite) |

### Protection Layer (`lib/`)

| Module | Description |
|--------|-------------|
| `state_machine.py` | Agent lifecycle: IDLE → CODING → TESTING → COMPLETED |
| `loop_detector.py` | Exact, pattern, similarity, error loop detection |
| `checkpoint.py` | Git commits + database snapshots, rollback support |
| `dependency_resolver.py` | Topological sort with Kahn's algorithm |
| `context_loader.py` | Priority-based context file loading |

### Server Components (`server/`)

| Module | Description |
|--------|-------------|
| `services/auth_service.py` | JWT + bcrypt authentication |
| `lib/path_security.py` | ALLOWED_ROOT_DIRECTORY enforcement |
| `routers/auth.py` | Login/logout/refresh endpoints |
| `routers/agent.py` | Agent start/stop/pause controls |

---

## How It Works

### Two-Agent Pattern

1. **Initializer Agent (First Session)**
   - Reads app specification from `prompts/app_spec.txt`
   - Creates features in SQLite database with priorities
   - Sets up project structure and initializes git

2. **Coding Agent (Subsequent Sessions)**
   - Gets next feature via MCP server
   - Implements and tests the feature
   - Marks as passing, repeats until all complete

### Feature Management (MCP Tools)

```python
feature_get_stats      # Progress statistics
feature_get_next       # Next pending feature (respects dependencies)
feature_get_for_regression  # Random passing features for testing
feature_mark_passing   # Mark feature complete
feature_skip           # Move to end of queue
feature_create_bulk    # Initialize all features
```

### Protection Mechanisms

**Loop Detection** detects:
- Exact repetition (same action N times)
- Pattern repetition (same sequence repeating)
- Semantic similarity (similar actions on same file)
- Error loops (same error repeated)

**State Machine** validates transitions:
```
IDLE → INITIALIZING → PLANNING → CODING → TESTING → VERIFYING → COMPLETED
                          ↓         ↓
                      WAITING_APPROVAL
```

**Checkpoints** enable rollback:
```python
from lib import CheckpointManager
cm = CheckpointManager(project_dir, max_checkpoints=20)
cp = cm.create("before_refactor", feature_id=42)
cm.rollback(cp.id)  # Restore git + database
```

---

## Configuration

### Environment Variables

```bash
# Authentication
AUTH_ENABLED=true
JWT_SECRET_KEY=<generate-with-secrets.token_hex(32)>
DEFAULT_ADMIN_PASSWORD=admin

# Path Security
ALLOWED_ROOT_DIRECTORY=/workspace
DATA_DIR=/app/data
REQUIRE_LOCALHOST=false

# Server
HOST=0.0.0.0
PORT=8888
```

### Multi-Spec Support

Projects can have multiple specs:

```
{project}/prompts/
├── app_spec.txt              # Main spec
├── app_spec_frontend.txt     # Frontend spec
├── app_spec_mobile.txt       # Mobile spec
└── .spec_manifest.json       # Tracks all specs
```

Use `/add-spec` command in Claude Code to add new specs.

---

## Project Structure

```
auto-agent-harness/
├── agent.py                  # Agent session logic
├── client.py                 # Claude SDK client
├── security.py               # Bash allowlist
├── registry.py               # Project registry
├── prompts.py                # Prompt loading with multi-spec
├── lib/
│   ├── state_machine.py      # Agent lifecycle
│   ├── loop_detector.py      # Loop detection
│   ├── checkpoint.py         # Snapshots & rollback
│   ├── dependency_resolver.py # Feature ordering
│   └── context_loader.py     # Context files
├── server/
│   ├── main.py               # FastAPI server + auth middleware
│   ├── lib/path_security.py  # Path validation
│   ├── services/auth_service.py # JWT + bcrypt
│   └── routers/              # API endpoints
├── mcp_server/
│   └── feature_mcp.py        # Feature management MCP
├── api/
│   └── database.py           # SQLAlchemy models
├── ui/                       # React frontend
│   ├── src/
│   │   ├── App.tsx           # Main app with auth
│   │   ├── components/       # UI components
│   │   └── lib/auth.ts       # Zustand auth store
│   └── package.json
├── .claude/
│   ├── commands/             # Slash commands
│   ├── skills/               # Claude Code skills
│   └── templates/            # Prompt templates
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Security Model

Defense-in-depth approach:

1. **Authentication**
   - JWT with httpOnly cookies (XSS protection)
   - Access (15 min) + Refresh (7 days) token rotation
   - bcrypt password hashing (12 rounds)
   - Rate limiting (5 attempts/minute)

2. **Path Security**
   - `ALLOWED_ROOT_DIRECTORY` restricts all file operations
   - Symlink validation prevents escape attacks
   - `DATA_DIR` exception for settings/users

3. **Bash Security**
   - Command allowlist (npm, git, ls, etc.)
   - Extra validation for dangerous commands
   - OS-level sandbox

4. **Network Security**
   - `REQUIRE_LOCALHOST` option
   - CORS restricted to known origins
   - Auth middleware on all API endpoints

---

## Development

### Backend

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python start.py
```

### Frontend

```bash
cd ui
npm install
npm run dev      # Development server
npm run build    # Production build
npm run lint     # ESLint
```

### Testing

```bash
# Security tests
python test_security.py

# Run with YOLO mode (skip browser tests)
python autonomous_agent_demo.py --project-dir my-app --yolo
```

---

## API Reference

### Authentication

```bash
# Login
curl -X POST http://localhost:8888/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'

# Protected endpoint (cookies set automatically)
curl http://localhost:8888/api/projects \
  --cookie-jar cookies.txt --cookie cookies.txt
```

### Projects

```bash
GET    /api/projects              # List all projects
POST   /api/projects              # Create project
GET    /api/projects/{name}       # Get project details
DELETE /api/projects/{name}       # Delete project
```

### Agent Control

```bash
POST   /api/agent/start           # Start agent
POST   /api/agent/stop            # Stop agent
POST   /api/agent/pause           # Pause agent
POST   /api/agent/resume          # Resume agent
GET    /api/agent/status          # Get agent status
```

### WebSocket

```javascript
ws://localhost:8888/ws/projects/{project_name}

// Events:
// - progress: { passing: number, total: number }
// - agent_status: "running" | "paused" | "stopped" | "crashed"
// - log: { message: string, timestamp: string }
// - feature_update: { id: number, status: string }
```

---

## License

This project is licensed under the **GNU Affero General Public License v3.0** - see [LICENSE.md](LICENSE.md).

Based on [AutoCoder](https://github.com/leonvanzyl/autocoder) by Leon van Zyl.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Acknowledgments

- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) by Anthropic
- Original [AutoCoder](https://github.com/leonvanzyl/autocoder) by Leon van Zyl
