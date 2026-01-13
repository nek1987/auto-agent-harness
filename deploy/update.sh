#!/bin/bash
#
# Auto Agent Harness - Update Script
# ===================================
#
# Updates the application from git, rebuilds frontend, and restarts service.
#
# Usage:
#   cd /path/to/auto-agent-harness
#   ./deploy/update.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "========================================"
echo "  Auto Agent Harness Update"
echo "========================================"
echo ""

# Check if running from project root
if [ ! -f "server/main.py" ]; then
    echo -e "${RED}ERROR: Please run this script from the project root directory${NC}"
    echo "  cd /path/to/auto-agent-harness"
    echo "  ./deploy/update.sh"
    exit 1
fi

PROJECT_DIR=$(pwd)
SERVICE_NAME="auto-agent"

# Check if service exists
SERVICE_EXISTS=$(systemctl list-units --full -all | grep -F "${SERVICE_NAME}.service" || true)

echo "Project directory: $PROJECT_DIR"
echo ""

# Step 1: Stop service (if running)
echo "[1/5] Stopping service..."
if [ -n "$SERVICE_EXISTS" ]; then
    sudo systemctl stop $SERVICE_NAME 2>/dev/null || true
    echo -e "${GREEN}Service stopped${NC}"
else
    echo -e "${YELLOW}Service not installed, skipping stop${NC}"
fi

# Step 2: Pull latest code
echo ""
echo "[2/5] Pulling latest code..."
git fetch origin
CHANGES=$(git log HEAD..origin/main --oneline)
if [ -z "$CHANGES" ]; then
    echo -e "${YELLOW}Already up to date${NC}"
else
    echo "Changes to be applied:"
    echo "$CHANGES"
    echo ""
    git pull origin main
    echo -e "${GREEN}Code updated${NC}"
fi

# Step 3: Update Python dependencies
echo ""
echo "[3/5] Updating Python dependencies..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    pip install -r requirements.txt --quiet
    echo -e "${GREEN}Python dependencies updated${NC}"
else
    echo -e "${YELLOW}Virtual environment not found, creating...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt --quiet
    echo -e "${GREEN}Virtual environment created and dependencies installed${NC}"
fi

# Step 4: Rebuild frontend
echo ""
echo "[4/5] Rebuilding frontend..."
if [ -d "ui" ]; then
    cd ui

    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo "Installing npm dependencies (first time, may take a few minutes)..."
        npm install
    else
        # Only install if package.json changed
        if [ package.json -nt node_modules ]; then
            echo "package.json changed, updating dependencies..."
            npm install
        fi
    fi

    echo "Building frontend..."
    npm run build
    cd ..
    echo -e "${GREEN}Frontend rebuilt${NC}"
else
    echo -e "${YELLOW}UI directory not found, skipping frontend build${NC}"
fi

# Step 5: Start service
echo ""
echo "[5/5] Starting service..."
if [ -n "$SERVICE_EXISTS" ]; then
    sudo systemctl start $SERVICE_NAME
    sleep 2

    # Check if service started successfully
    if sudo systemctl is-active --quiet $SERVICE_NAME; then
        echo -e "${GREEN}Service started successfully${NC}"
    else
        echo -e "${RED}Service failed to start!${NC}"
        sudo journalctl -u $SERVICE_NAME -n 20 --no-pager
        exit 1
    fi
else
    echo -e "${YELLOW}Service not installed. Run ./deploy/install_service.sh to install.${NC}"
    echo "Starting manually..."
    source venv/bin/activate
    nohup python -m uvicorn server.main:app --host 0.0.0.0 --port 8888 > /tmp/auto-agent.log 2>&1 &
    echo "Started in background. Logs: /tmp/auto-agent.log"
fi

# Summary
echo ""
echo "========================================"
echo -e "  ${GREEN}Update Complete!${NC}"
echo "========================================"
echo ""

if [ -n "$SERVICE_EXISTS" ]; then
    echo "Service status:"
    sudo systemctl status $SERVICE_NAME --no-pager -l | head -15
    echo ""
    echo "View logs:"
    echo "  sudo journalctl -u $SERVICE_NAME -f"
    echo "  tail -f /var/log/auto-agent/server.log"
fi

echo ""
echo "Server URL: http://$(hostname -I | awk '{print $1}'):8888"
echo ""
