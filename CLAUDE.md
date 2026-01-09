# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an autonomous coding agent system with a React-based UI. It uses the Claude Agent SDK to build complete applications over multiple sessions using a two-agent pattern:

1. **Initializer Agent** - First session reads an app spec and creates features in a SQLite database
2. **Coding Agent** - Subsequent sessions implement features one by one, marking them as passing

## Commands

### Quick Start (Recommended)

```bash
# Windows - launches CLI menu
start.bat

# macOS/Linux
./start.sh

# Launch Web UI (serves pre-built React app)
start_ui.bat      # Windows
./start_ui.sh     # macOS/Linux
```

### Python Backend (Manual)

```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run the main CLI launcher
python start.py

# Run agent directly for a project (use absolute path or registered name)
python autonomous_agent_demo.py --project-dir C:/Projects/my-app
python autonomous_agent_demo.py --project-dir my-app  # if registered

# YOLO mode: rapid prototyping without browser testing
python autonomous_agent_demo.py --project-dir my-app --yolo
```

### YOLO Mode (Rapid Prototyping)

YOLO mode skips all testing for faster feature iteration:

```bash
# CLI
python autonomous_agent_demo.py --project-dir my-app --yolo

# UI: Toggle the lightning bolt button before starting the agent
```

**What's different in YOLO mode:**
- No regression testing (skips `feature_get_for_regression`)
- No Playwright MCP server (browser automation disabled)
- Features marked passing after lint/type-check succeeds
- Faster iteration for prototyping

**What's the same:**
- Lint and type-check still run to verify code compiles
- Feature MCP server for tracking progress
- All other development tools available

**When to use:** Early prototyping when you want to quickly scaffold features without verification overhead. Switch back to standard mode for production-quality development.

### React UI (in ui/ directory)

```bash
cd ui
npm install
npm run dev      # Development server (hot reload)
npm run build    # Production build (required for start_ui.bat)
npm run lint     # Run ESLint
```

**Note:** The `start_ui.bat` script serves the pre-built UI from `ui/dist/`. After making UI changes, run `npm run build` in the `ui/` directory.

## Architecture

### Core Python Modules

- `start.py` - CLI launcher with project creation/selection menu
- `autonomous_agent_demo.py` - Entry point for running the agent
- `agent.py` - Agent session loop using Claude Agent SDK
- `client.py` - ClaudeSDKClient configuration with security hooks and MCP servers
- `security.py` - Bash command allowlist validation (ALLOWED_COMMANDS whitelist)
- `prompts.py` - Prompt template loading with project-specific fallback
- `progress.py` - Progress tracking, database queries, webhook notifications
- `registry.py` - Project registry for mapping names to paths (cross-platform)

### Project Registry

Projects can be stored in any directory. The registry maps project names to paths using SQLite:
- **All platforms**: `~/.autocoder/registry.db`

The registry uses:
- SQLite database with SQLAlchemy ORM
- POSIX path format (forward slashes) for cross-platform compatibility
- SQLite's built-in transaction handling for concurrency safety

### Server API (server/)

The FastAPI server provides REST endpoints for the UI:

- `server/routers/auth.py` - Authentication (login/logout/refresh/user management)
- `server/routers/projects.py` - Project CRUD with registry integration
- `server/routers/features.py` - Feature management
- `server/routers/agent.py` - Agent control (start/stop/pause/resume)
- `server/routers/filesystem.py` - Filesystem browser API with security controls
- `server/routers/spec_creation.py` - WebSocket for interactive spec creation
- `server/lib/path_security.py` - Path validation and sandboxing
- `server/services/auth_service.py` - JWT + bcrypt authentication service

### Feature Management

Features are stored in SQLite (`features.db`) via SQLAlchemy. The agent interacts with features through an MCP server:

- `mcp_server/feature_mcp.py` - MCP server exposing feature management tools
- `api/database.py` - SQLAlchemy models (Feature table with priority, category, name, description, steps, passes)

MCP tools available to the agent:
- `feature_get_stats` - Progress statistics
- `feature_get_next` - Get highest-priority pending feature (respects dependencies)
- `feature_get_for_regression` - Random passing features for regression testing
- `feature_mark_passing` - Mark feature complete
- `feature_skip` - Move feature to end of queue
- `feature_create_bulk` - Initialize all features (used by initializer)

### Feature Dependencies

Features can depend on other features using the `dependencies` field (list of feature IDs).
The `DependencyResolver` class in `lib/dependency_resolver.py` provides:
- Topological sorting with Kahn's algorithm
- Cycle detection with clear error messages
- `get_next_ready()` - Get next feature with all dependencies satisfied
- Priority-aware ordering (lower priority number = higher importance)

### Multi-Spec Support

Projects can have multiple app specs (e.g., main + frontend + mobile):

```
{project_dir}/prompts/
├── app_spec.txt              # Main spec
├── app_spec_frontend.txt     # Frontend spec (extends main)
├── app_spec_mobile.txt       # Mobile spec
└── .spec_manifest.json       # Tracks all specs
```

Key functions in `prompts.py`:
- `list_specs(project_dir)` - List all registered specs
- `add_spec_file(project_dir, name, content)` - Add a new spec
- `get_all_app_specs(project_dir)` - Get all spec contents
- `update_spec_feature_range()` - Track feature ID ranges per spec

Features are tagged with `source_spec` to track their origin.

### Context Files

Project-specific rules and conventions in `.context/` directory:

```
{project_dir}/.context/
├── CLAUDE.md              # Main project rules
├── CODE_QUALITY.md        # Code standards
└── context-metadata.json  # File priorities and conditions
```

Load context into prompts:
```python
from lib.context_loader import load_context_files
context = load_context_files(project_dir, mode="coding")
```

### Protection Layer

The agent includes multiple protection mechanisms:

**State Machine** (`lib/state_machine.py`):
- Manages agent lifecycle states: IDLE → INITIALIZING → PLANNING → CODING → TESTING → VERIFYING
- Validates state transitions
- Tracks iteration count with configurable limit
- Persists state to `.agent_state.json`

```python
from lib import AgentStateMachine, AgentState
sm = AgentStateMachine(project_dir, max_iterations=1000)
sm.transition(AgentState.CODING, feature_id=42)
```

**Loop Detection** (`lib/loop_detector.py`):
- Detects exact repetition (same action N times)
- Detects pattern repetition (same sequence repeating)
- Detects similar actions (semantic similarity)
- Detects error loops (same error repeated)

```python
from lib import LoopDetector, create_action_from_tool_call
detector = LoopDetector(exact_threshold=5)
action = create_action_from_tool_call("Edit", {"file_path": "foo.py"})
pattern = detector.record_action(action)  # Returns LoopPattern if detected
```

**Checkpoints** (`lib/checkpoint.py`):
- Creates git commits + database snapshots
- Supports rollback to any checkpoint
- Auto-cleanup of old checkpoints

```python
from lib import CheckpointManager
cm = CheckpointManager(project_dir, max_checkpoints=20)
cp = cm.create("before_refactor", feature_id=42)
cm.rollback(cp.id)  # Restore to checkpoint
```

### React UI (ui/)

- Tech stack: React 18, TypeScript, TanStack Query, Tailwind CSS v4, Radix UI, Zustand
- `src/App.tsx` - Main app with auth protection, project selection, kanban board, agent controls
- `src/hooks/useWebSocket.ts` - Real-time updates via WebSocket
- `src/hooks/useProjects.ts` - React Query hooks for API calls
- `src/lib/api.ts` - REST API client
- `src/lib/auth.ts` - Authentication store (Zustand) with httpOnly cookie support
- `src/lib/types.ts` - TypeScript type definitions
- `src/components/LoginForm.tsx` - Neobrutalism-styled login form
- `src/components/FolderBrowser.tsx` - Server-side filesystem browser for project folder selection
- `src/components/NewProjectModal.tsx` - Multi-step project creation wizard

### Project Structure for Generated Apps

Projects can be stored in any directory (registered in `~/.autocoder/registry.db`). Each project contains:
- `prompts/app_spec.txt` - Application specification (XML format)
- `prompts/initializer_prompt.md` - First session prompt
- `prompts/coding_prompt.md` - Continuation session prompt
- `features.db` - SQLite database with feature test cases
- `.agent.lock` - Lock file to prevent multiple agent instances

### Security Model

Defense-in-depth approach with multiple layers:

1. **Authentication** (`server/services/auth_service.py`, `server/routers/auth.py`)
   - JWT tokens with httpOnly cookies (XSS protection)
   - Access token (15 min) + Refresh token (7 days) rotation
   - bcrypt password hashing (12 rounds)
   - Rate limiting on login endpoint (5 attempts/minute)

2. **Path Security** (`server/lib/path_security.py`)
   - `ALLOWED_ROOT_DIRECTORY` restricts file operations to workspace
   - `DATA_DIR` always allowed for settings/users (exception)
   - Symlink validation to prevent escape attacks
   - All filesystem operations go through validation

3. **Bash Security** (`security.py`)
   - Command allowlist validation (ALLOWED_COMMANDS whitelist)
   - Extra validation for dangerous commands (pkill, chmod)
   - OS-level sandbox for bash commands

4. **Network Security** (`server/main.py`)
   - `REQUIRE_LOCALHOST` option for local-only access
   - CORS restricted to known origins
   - Auth middleware for all API endpoints

### Environment Variables

```bash
# Authentication
AUTH_ENABLED=true                    # Enable/disable auth
JWT_SECRET_KEY=<random-hex-32>       # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
DEFAULT_ADMIN_PASSWORD=admin         # Initial admin password

# Path Security
ALLOWED_ROOT_DIRECTORY=/workspace    # Restrict file ops to this dir
DATA_DIR=/app/data                   # Settings/users storage
REQUIRE_LOCALHOST=false              # Local-only access

# Server
HOST=0.0.0.0
PORT=8888
```

### Docker Deployment

```bash
# Start with docker-compose
docker-compose up -d

# Custom workspace
WORKSPACE_DIR=/path/to/projects docker-compose up -d

# View logs
docker-compose logs -f
```

## Claude Code Integration

- `.claude/commands/create-spec.md` - `/create-spec` slash command for interactive spec creation
- `.claude/commands/add-spec.md` - `/add-spec` slash command to add specs to existing projects
- `.claude/skills/frontend-design/SKILL.md` - Skill for distinctive UI design
- `.claude/templates/` - Prompt templates copied to new projects

## Key Patterns

### Prompt Loading Fallback Chain

1. Project-specific: `{project_dir}/prompts/{name}.md`
2. Base template: `.claude/templates/{name}.template.md`

### Agent Session Flow

1. Check if `features.db` has features (determines initializer vs coding agent)
2. Create ClaudeSDKClient with security settings
3. Send prompt and stream response
4. Auto-continue with 3-second delay between sessions

### Real-time UI Updates

The UI receives updates via WebSocket (`/ws/projects/{project_name}`):
- `progress` - Test pass counts
- `agent_status` - Running/paused/stopped/crashed
- `log` - Agent output lines (streamed from subprocess stdout)
- `feature_update` - Feature status changes

### Design System

The UI uses a **neobrutalism** design with Tailwind CSS v4:
- CSS variables defined in `ui/src/styles/globals.css` via `@theme` directive
- Custom animations: `animate-slide-in`, `animate-pulse-neo`, `animate-shimmer`
- Color tokens: `--color-neo-pending` (yellow), `--color-neo-progress` (cyan), `--color-neo-done` (green)
