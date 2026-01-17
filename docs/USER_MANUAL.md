# Auto-Agent-Harness User Manual

This guide explains how to use Auto-Agent-Harness to create projects, import specs, run agents, and execute redesigns with visual references.

---

## Overview

Auto-Agent-Harness turns an application specification into a tracked backlog and then runs an autonomous agent to implement each feature. It includes a web UI, a FastAPI backend, and MCP tools for feature control, browser actions, and redesign planning.

What it solves:
- Turn a spec into a structured feature backlog.
- Run an agent to implement features with safety controls.
- Redesign an existing UI using visual references and design tokens.

Who this is for:
- Technical PMs: create/import specs, review progress, approve redesign plans.
- Developers: monitor execution, run the agent, validate outputs.
- DevOps: deploy and operate the server, manage auth and logs.

---

## Quickstart

### Option A: Native Mode (Local)

Prerequisites:
- Python 3.11+
- Node.js 18+
- Claude Code CLI: `npm install -g @anthropic-ai/claude-code`
- agent-browser (for redesign URL screenshots): `npm install -g agent-browser && agent-browser install`

Setup:
```bash
git clone https://github.com/nek1987/auto-agent-harness.git
cd auto-agent-harness
python -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.native.example .env

# Authenticate Claude CLI (opens browser)
claude login
```

Run the UI:
```bash
./start_ui.sh         # macOS/Linux
start_ui.bat          # Windows
# or: python start_ui.py --dev
```

Open `http://localhost:8888`.

### Option B: Docker Mode (Server)

Prerequisites:
- Docker + Docker Compose
- Anthropic API key

Setup:
```bash
git clone https://github.com/nek1987/auto-agent-harness.git
cd auto-agent-harness
cp .env.docker.example .env
# Edit .env and set ANTHROPIC_API_KEY + JWT_SECRET_KEY
docker-compose up -d --build
```

Open `http://localhost:8888`.

See `docs/CONFIGURATION.md` for environment variables and `docs/DEPLOYMENT.md` for production setups.

---

## Workflows

### 1) Create a Project and Spec

1. Open the UI and click **New Project**.
2. Choose a project name and a local workspace path.
3. Select a spec method:
   - **Claude (interactive)**: start a guided chat to generate `app_spec.txt`.
   - **Manual**: paste or edit a spec directly.
4. Finish the spec flow. The system generates a feature backlog automatically and starts the initializer agent.

Tip: In the Claude spec chat you can attach reference files or images to clarify requirements.
If you want to review before execution, pause or stop the agent after it starts.

Where the spec lives:
`<project>/prompts/app_spec.txt`

### 2) Import an Existing Spec

Use this when you already have an `app_spec.txt`.

1. Open the project and click **Import Spec**.
2. Upload `app_spec.txt` (drag and drop or file select).
3. The system validates structure and can auto-enhance missing sections.
4. Optionally run **Analyze** and **Refine** for deeper improvements.
5. Click **Import** to save the spec, register it, and auto-start the initializer agent.

### 3) Start the Agent

1. Open a project with pending features.
2. Click **Start Agent** in the UI.
3. Monitor status and logs in real time.
4. Use **Pause** or **Stop** if you need to intervene.

Agent modes:
- Standard: full checks and regression.
- YOLO: faster, skips heavy verification (good for prototypes).

### 4) Redesign with References

The redesign wizard creates a plan based on visual references and then applies it via the agent.

Start a redesign session:
1. Open a project and click **Redesign**.
2. Click **Start Redesign Session**.

Add references:
- Images: PNG/JPG/WebP up to 10MB each.
- URLs: the system captures screenshots via agent-browser.
- ZIP (components/pages): upload source code; select a page or enter a custom name.

Style brief (recommended):
Use the **Style Brief** field to avoid generic AI styles. Be explicit:
```
Bold neo-brutal, mono headers, warm neutrals, 8px radius, crisp shadows, no gradients.
```

Run the planner:
1. Click **Run Planner**.
2. Wait for **Design Tokens** extraction.
3. Click **Review Plan**.
4. Approve phases (globals, config, components, pages).

Implement:
1. Click **Start Agent** in the Implementation step.
2. Watch the activity feed and logs.
3. Use **Refresh** if the UI is waiting on new output.
4. Use **Cancel Session** if you need to reset the redesign.

---

## Troubleshooting

### UI shows blank or stuck in redesign
- Click **Refresh** in the redesign wizard.
- Verify the agent is running and `agent-browser` is installed.
- Check server logs (see `docs/DEPLOYMENT.md`).

### Cannot connect to backend server
- Ensure `start_ui.py` is running.
- Confirm port `8888` is free and accessible.

### Agent will not start
- Native mode: run `claude login` again.
- Docker mode: check `ANTHROPIC_API_KEY` and `JWT_SECRET_KEY`.

### Redesign references fail to upload
- Only PNG/JPG/WebP are supported for images.
- ZIP uploads must be a `.zip` file.
- File size limit: 10MB per image.

### Where to look for logs
- Systemd: `/var/log/auto-agent/server.log`
- Docker: `docker-compose logs -f auto-agent-harness`
- See `docs/DEPLOYMENT.md` for more detail.

---

## FAQ

### Can I use multiple references?
Yes. Add multiple images and URLs. ZIP uploads are handled per archive; repeat the upload for each reference set.

### Does redesign apply changes automatically?
Not until you approve the plan and click **Start Agent**. You control when changes are applied.

### Where are project files stored?
Projects are saved in the workspace you choose. The registry is stored at `~/.auto-agent-harness/registry.db`.

### How do I reset a project?
Delete the project from the UI and remove its directory from disk.
