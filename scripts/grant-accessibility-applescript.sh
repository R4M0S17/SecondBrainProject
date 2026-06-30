#!/bin/bash
#
# Grant Accessibility permission using AppleScript
# Works on all macOS versions
#

PYTHON_PATH="/Users/mb/Desktop/Javier/SecondBrain/.venv/bin/python"

echo "🔐 Granting Accessibility permission to Cerebro Python..."
echo ""

# Create AppleScript to open System Preferences and show instructions
osascript << 'SCRIPT'
tell application "System Preferences"
    activate
    set current pane to pane "com.apple.preference.security"
    delay 1
    tell application "System Events"
        # Try to click on Privacy tab
        try
            click button "Privacy" of window 1
            delay 0.5
        end try
        # Try to click on Accessibility in the list
        try
            click item "Accessibility" of outline 1 of scroll area 1 of tab group 1 of window 1
        end try
    end tell
end tell

# Show dialog with instructions
tell application "System Events"
    activate
    display dialog "✅ System Settings opened!

Steps to grant Accessibility permission:
1. Look for 'Accessibility' in the left sidebar
2. Click on 'Accessibility'
3. Click the lock 🔒 at the bottom left
4. Enter your Mac password
5. Click the + button
6. Go to: /Users/mb/Desktop/Javier/SecondBrain/.venv/bin/
7. Select 'python' and click Open
8. Close System Preferences

Then try Mac Flows → Record routine again!" buttons {"Got it!"} default button 1
end tell
SCRIPT

echo ""
echo "✅ Instructions shown! Follow the steps in the dialog."
