#!/bin/bash
# =============================================================================
# Generate Self-Signed SSL Certificate for Development
# =============================================================================
#
# Usage:
#   ./scripts/generate-ssl-cert.sh [CERT_DIR] [DOMAIN] [DAYS]
#
# Arguments:
#   CERT_DIR  - Directory to store certificates (default: ./certs)
#   DOMAIN    - Domain name for the certificate (default: localhost)
#   DAYS      - Certificate validity in days (default: 365)
#
# Examples:
#   ./scripts/generate-ssl-cert.sh
#   ./scripts/generate-ssl-cert.sh ./certs localhost 365
#   ./scripts/generate-ssl-cert.sh ./certs myserver.local 730
#
# =============================================================================

set -e

CERT_DIR="${1:-./certs}"
DOMAIN="${2:-localhost}"
DAYS="${3:-365}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "  SSL Certificate Generator"
echo "=============================================="
echo ""

# Check if openssl is installed
if ! command -v openssl &> /dev/null; then
    echo -e "${RED}ERROR: openssl is not installed${NC}"
    echo "Please install openssl:"
    echo "  Ubuntu/Debian: sudo apt-get install openssl"
    echo "  macOS: brew install openssl"
    echo "  Windows: Install Git Bash or use WSL"
    exit 1
fi

# Create certificate directory
mkdir -p "$CERT_DIR"

echo -e "${YELLOW}Generating self-signed certificate for: $DOMAIN${NC}"
echo "Validity: $DAYS days"
echo ""

# Generate private key and certificate
openssl req -x509 -nodes -days "$DAYS" -newkey rsa:2048 \
    -keyout "$CERT_DIR/server.key" \
    -out "$CERT_DIR/server.crt" \
    -subj "/C=XX/ST=Development/L=Local/O=AutoCoder/CN=$DOMAIN" \
    -addext "subjectAltName=DNS:$DOMAIN,DNS:localhost,IP:127.0.0.1,IP:0.0.0.0" \
    2>/dev/null

# Set permissions
chmod 600 "$CERT_DIR/server.key"
chmod 644 "$CERT_DIR/server.crt"

echo ""
echo -e "${GREEN}Certificate generated successfully!${NC}"
echo ""
echo "Files created:"
echo "  Certificate: $CERT_DIR/server.crt"
echo "  Private key: $CERT_DIR/server.key"
echo ""
echo "=============================================="
echo "  Add these lines to your .env file:"
echo "=============================================="
echo ""
echo "HTTPS_ENABLED=true"
echo "SSL_CERTFILE=$CERT_DIR/server.crt"
echo "SSL_KEYFILE=$CERT_DIR/server.key"
echo "COOKIE_SECURE=true"
echo ""
echo "=============================================="
echo ""
echo -e "${YELLOW}Note: Self-signed certificates will show a browser warning.${NC}"
echo "For production, use Let's Encrypt with nginx reverse proxy."
echo ""
