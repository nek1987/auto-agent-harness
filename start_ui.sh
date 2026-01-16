#!/bin/bash
cd "$(dirname "$0")"
# Auto Agent Harness UI Launcher for Unix/Linux/macOS
# This script launches the web UI for the autonomous coding agent.

echo ""
echo "===================================="
echo "  Auto Agent Harness UI"
echo "===================================="
echo ""

# Check if Node.js and npm are available (needed for agent-browser)
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js not found"
    echo "Please install Node.js from https://nodejs.org"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "ERROR: npm not found"
    echo "Please install Node.js from https://nodejs.org"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "ERROR: Python not found"
        echo "Please install Python from https://python.org"
        exit 1
    fi
    PYTHON_CMD="python"
else
    PYTHON_CMD="python3"
fi

# Check if venv exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv venv
fi

# Activate the virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Ensure agent-browser is installed
if ! command -v agent-browser &> /dev/null; then
    echo "Installing agent-browser CLI..."
    npm install -g agent-browser
fi

echo "Installing agent-browser Chromium..."
agent-browser install

# Run the Python launcher
python start_ui.py "$@"
