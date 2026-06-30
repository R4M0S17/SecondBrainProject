#!/bin/bash
#
# Grant Accessibility permissions to Cerebro Python venv
#

VENV_PYTHON="/Users/mb/Desktop/Javier/SecondBrain/.venv/bin/python"

echo "🔐 Granting Accessibility permission to Cerebro Python..."
echo "Path: $VENV_PYTHON"
echo ""
echo "You will be prompted for your Mac password (required for Accessibility permissions)"
echo ""

# Grant Accessibility permission
sudo tccutil grant Accessibility "$VENV_PYTHON"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ SUCCESS! Accessibility permission granted!"
    echo ""
    echo "Next steps:"
    echo "1. Restart Cerebro (close all windows/terminals)"
    echo "2. Run: make engine   (Terminal 1)"
    echo "3. Run: make run      (Terminal 2)"
    echo "4. Run: cd ui/tray && npm run dev  (Terminal 3)"
    echo "5. Open http://localhost:5173 in browser"
    echo "6. Go to Mac Flows → Record routine"
else
    echo ""
    echo "❌ Permission grant failed. Try manually:"
    echo "   sudo tccutil grant Accessibility $VENV_PYTHON"
fi
