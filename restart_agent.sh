#!/bin/bash

echo "🛑 Stopping any running Python processes..."
pkill -f "python.*run.py" || echo "No running processes found"

echo "🧹 Clearing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

echo "✅ Cache cleared!"
echo ""
echo "📝 To start the agent with updated code, run:"
echo "   python run.py --backend lmstudio --agent-auto"
echo ""
echo "✅ Look for these NEW debug messages to confirm code is loaded:"
echo "   🎯 Active objectives count: X"
echo "   🏢 Floor check: Current floor = X, Target floor = Y"
echo "   🗺️ MAP CHANGE DETECTED: ..."
echo ""
