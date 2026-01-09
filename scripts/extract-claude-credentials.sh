#!/bin/bash
# ============================================================================
# Extract Claude OAuth Credentials for Docker Deployment
# ============================================================================
#
# This script extracts Claude CLI OAuth credentials from the host machine
# for use in Docker containers.
#
# Usage:
#   ./scripts/extract-claude-credentials.sh
#   ./scripts/extract-claude-credentials.sh --output /path/to/credentials.json
#
# Output:
#   Prints JSON credentials to stdout (or to file if --output specified)
#
# Platform Support:
#   - macOS: Extracts from Keychain (security command)
#   - Linux: Copies from ~/.claude/.credentials.json
#   - Windows (WSL): Copies from /mnt/c/Users/<user>/.claude/.credentials.json
#
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Output file (optional)
OUTPUT_FILE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --output|-o)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--output FILE]"
            echo ""
            echo "Extract Claude OAuth credentials for Docker deployment."
            echo ""
            echo "Options:"
            echo "  --output, -o FILE  Write credentials to FILE instead of stdout"
            echo "  --help, -h         Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option $1${NC}" >&2
            exit 1
            ;;
    esac
done

# Function to output credentials
output_credentials() {
    local creds="$1"
    if [ -n "$OUTPUT_FILE" ]; then
        echo "$creds" > "$OUTPUT_FILE"
        chmod 600 "$OUTPUT_FILE"
        echo -e "${GREEN}Credentials saved to: $OUTPUT_FILE${NC}" >&2
    else
        echo "$creds"
    fi
}

# Detect platform and extract credentials
extract_credentials() {
    local creds=""

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # ========================================
        # macOS: Extract from Keychain
        # ========================================
        echo -e "${YELLOW}Detecting macOS...${NC}" >&2

        if ! command -v security &> /dev/null; then
            echo -e "${RED}Error: 'security' command not found.${NC}" >&2
            exit 1
        fi

        USERNAME=$(whoami)

        # Try to extract from Keychain
        creds=$(security find-generic-password -s "Claude Code-credentials" -a "$USERNAME" -w 2>/dev/null) || true

        if [ -z "$creds" ]; then
            # Fallback to file-based credentials
            if [ -f "$HOME/.claude/.credentials.json" ]; then
                echo -e "${YELLOW}Keychain empty, using file-based credentials...${NC}" >&2
                creds=$(cat "$HOME/.claude/.credentials.json")
            else
                echo -e "${RED}Error: No Claude credentials found.${NC}" >&2
                echo -e "${YELLOW}Run 'claude login' first to authenticate.${NC}" >&2
                exit 1
            fi
        fi

    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # ========================================
        # Linux: Check for credentials file
        # ========================================
        echo -e "${YELLOW}Detecting Linux...${NC}" >&2

        # Check for WSL
        if grep -qi microsoft /proc/version 2>/dev/null; then
            echo -e "${YELLOW}WSL detected, checking Windows credentials...${NC}" >&2

            # Get Windows username
            WIN_USER=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r\n')
            WIN_CREDS="/mnt/c/Users/$WIN_USER/.claude/.credentials.json"

            if [ -f "$WIN_CREDS" ]; then
                creds=$(cat "$WIN_CREDS")
            elif [ -f "$HOME/.claude/.credentials.json" ]; then
                creds=$(cat "$HOME/.claude/.credentials.json")
            fi
        else
            # Standard Linux
            if [ -f "$HOME/.claude/.credentials.json" ]; then
                creds=$(cat "$HOME/.claude/.credentials.json")
            fi
        fi

        if [ -z "$creds" ]; then
            echo -e "${RED}Error: No Claude credentials found at ~/.claude/.credentials.json${NC}" >&2
            echo -e "${YELLOW}Run 'claude login' first to authenticate.${NC}" >&2
            exit 1
        fi

    elif [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]]; then
        # ========================================
        # Windows (Git Bash / Cygwin)
        # ========================================
        echo -e "${YELLOW}Detecting Windows...${NC}" >&2

        WIN_CREDS="$USERPROFILE/.claude/.credentials.json"
        if [ -f "$WIN_CREDS" ]; then
            creds=$(cat "$WIN_CREDS")
        else
            echo -e "${RED}Error: No Claude credentials found at $WIN_CREDS${NC}" >&2
            echo -e "${YELLOW}Run 'claude login' first to authenticate.${NC}" >&2
            exit 1
        fi
    else
        echo -e "${RED}Error: Unsupported platform: $OSTYPE${NC}" >&2
        exit 1
    fi

    # Validate JSON
    if ! echo "$creds" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
        echo -e "${RED}Error: Extracted credentials are not valid JSON.${NC}" >&2
        exit 1
    fi

    output_credentials "$creds"
}

# Verify credentials have required fields
verify_credentials() {
    local creds="$1"

    # Check for accessToken or refreshToken
    if echo "$creds" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if 'accessToken' not in data and 'refreshToken' not in data:
    sys.exit(1)
" 2>/dev/null; then
        echo -e "${GREEN}Credentials verified successfully.${NC}" >&2
    else
        echo -e "${YELLOW}Warning: Credentials may be incomplete (no accessToken/refreshToken found).${NC}" >&2
    fi
}

# Main
echo -e "${GREEN}Claude Credentials Extractor${NC}" >&2
echo "==============================" >&2
extract_credentials

# If we wrote to file, verify it
if [ -n "$OUTPUT_FILE" ] && [ -f "$OUTPUT_FILE" ]; then
    verify_credentials "$(cat "$OUTPUT_FILE")"
fi
