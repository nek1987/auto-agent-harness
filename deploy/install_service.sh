#!/bin/bash
#
# Auto Agent Harness - Systemd Service Installer
# ==============================================
#
# This script installs the Auto Agent Harness as a systemd service.
# Run from the project root directory.
#
# Usage:
#   cd /path/to/auto-agent-harness
#   ./deploy/install_service.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "========================================"
echo "  Auto Agent Harness Service Installer"
echo "========================================"
echo ""

# Check if running from project root
if [ ! -f "server/main.py" ]; then
    echo -e "${RED}ERROR: Please run this script from the project root directory${NC}"
    echo "  cd /path/to/auto-agent-harness"
    echo "  ./deploy/install_service.sh"
    exit 1
fi

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${YELLOW}WARNING: Running as root. Service will run as root user.${NC}"
    echo "Consider running as a regular user with sudo access."
    echo ""
fi

PROJECT_DIR=$(pwd)
SERVICE_FILE="deploy/auto-agent.service"
TARGET_SERVICE="/etc/systemd/system/auto-agent.service"
LOG_DIR="/var/log/auto-agent"

echo "Project directory: $PROJECT_DIR"
echo "Current user: $USER"
echo ""

# Step 1: Check prerequisites
echo "[1/5] Checking prerequisites..."

if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

if [ ! -f "venv/bin/python" ]; then
    echo -e "${RED}ERROR: venv/bin/python not found${NC}"
    exit 1
fi

echo -e "${GREEN}Prerequisites OK${NC}"

# Step 2: Create log directory
echo ""
echo "[2/5] Creating log directory..."

sudo mkdir -p "$LOG_DIR"
sudo chown $USER:$(id -gn) "$LOG_DIR"
sudo chmod 755 "$LOG_DIR"

echo -e "${GREEN}Log directory created: $LOG_DIR${NC}"

# Step 3: Copy and configure service file
echo ""
echo "[3/5] Installing systemd service..."

# Create a temporary file with substitutions
TMP_SERVICE=$(mktemp)
cat "$SERVICE_FILE" > "$TMP_SERVICE"

# Replace placeholders
sed -i "s|/path/to/auto-agent-harness|$PROJECT_DIR|g" "$TMP_SERVICE"
sed -i "s|<username>|$USER|g" "$TMP_SERVICE"
sed -i "s|<group>|$(id -gn)|g" "$TMP_SERVICE"

# Copy to systemd
sudo cp "$TMP_SERVICE" "$TARGET_SERVICE"
rm "$TMP_SERVICE"

echo -e "${GREEN}Service file installed: $TARGET_SERVICE${NC}"

# Step 4: Install logrotate config
echo ""
echo "[4/5] Installing logrotate config..."

if [ -f "deploy/auto-agent-logrotate" ]; then
    TMP_LOGROTATE=$(mktemp)
    cat "deploy/auto-agent-logrotate" > "$TMP_LOGROTATE"
    sed -i "s|<user>|$USER|g" "$TMP_LOGROTATE"
    sed -i "s|<group>|$(id -gn)|g" "$TMP_LOGROTATE"
    sudo cp "$TMP_LOGROTATE" "/etc/logrotate.d/auto-agent"
    rm "$TMP_LOGROTATE"
    echo -e "${GREEN}Logrotate config installed${NC}"
else
    echo -e "${YELLOW}Logrotate config not found, skipping${NC}"
fi

# Step 5: Enable and start service
echo ""
echo "[5/5] Enabling and starting service..."

sudo systemctl daemon-reload
sudo systemctl enable auto-agent
sudo systemctl start auto-agent

echo ""
echo "========================================"
echo -e "  ${GREEN}Installation Complete!${NC}"
echo "========================================"
echo ""
echo "Service commands:"
echo "  sudo systemctl status auto-agent    # Check status"
echo "  sudo systemctl restart auto-agent   # Restart"
echo "  sudo systemctl stop auto-agent      # Stop"
echo "  sudo systemctl disable auto-agent   # Disable autostart"
echo ""
echo "View logs:"
echo "  sudo journalctl -u auto-agent -f    # System journal"
echo "  tail -f $LOG_DIR/server.log         # Server log"
echo "  tail -f $LOG_DIR/error.log          # Error log"
echo ""
echo "Server URL: http://$(hostname -I | awk '{print $1}'):8888"
echo ""

# Show current status
sudo systemctl status auto-agent --no-pager || true
