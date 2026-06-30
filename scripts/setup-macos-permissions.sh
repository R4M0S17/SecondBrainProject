#!/bin/bash
#
# Setup macOS Accessibility permissions for Cerebro
# Usage: bash setup-macos-permissions.sh
#

set -e

echo "🔐 Cerebro macOS Permissions Setup"
echo "===================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Find Python executable
PYTHON_PATH=$(which python3)
if [ -z "$PYTHON_PATH" ]; then
    echo -e "${RED}❌ Python3 not found in PATH${NC}"
    echo "Please install Python or ensure it's in your PATH"
    exit 1
fi

echo -e "${YELLOW}Found Python: $PYTHON_PATH${NC}"
echo ""

# Check if tccutil is available
if ! command -v tccutil &> /dev/null; then
    echo -e "${RED}❌ tccutil not found (macOS system utility)${NC}"
    echo "This script requires macOS 10.13 or later"
    exit 1
fi

echo "🔓 Granting Accessibility permission to Python..."
echo ""
echo "⚠️  You may be prompted for your password (sudo required)"
echo ""

# Grant Accessibility permission
sudo tccutil grant Accessibility "$PYTHON_PATH" 2>/dev/null || {
    echo -e "${RED}❌ Failed to grant Accessibility permission${NC}"
    echo "Try manually:"
    echo "  sudo tccutil grant Accessibility $PYTHON_PATH"
    exit 1
}

echo -e "${GREEN}✅ Accessibility permission granted!${NC}"
echo ""

# Verify permission was granted
if tccutil dump | grep -q "Accessibility"; then
    echo -e "${GREEN}✅ Permission verified in system database${NC}"
else
    echo -e "${YELLOW}⚠️  Could not verify permission (may take a moment)${NC}"
fi

echo ""
echo "📝 Next steps:"
echo "  1. Restart Cerebro application"
echo "  2. Try the 'Grabar rutina' (Recording) feature"
echo ""

# Offer to open System Preferences
read -p "Would you like to open System Preferences to verify? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
fi

echo -e "${GREEN}✅ Setup complete!${NC}"
