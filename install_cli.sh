#!/bin/bash
# 🧸 AI Teddy Bear CLI Installation Script
# ==========================================

set -e  # Exit on any error

echo "🧸 AI Teddy Bear CLI Installation"
echo "=================================="

# Check Python version
echo "📋 Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✅ Python $PYTHON_VERSION detected"

# Make CLI executable
echo "🔧 Setting up CLI executable..."
chmod +x ai_teddy_cli.py

# Create convenience symlink
if [ ! -f "teddy" ]; then
    ln -s ai_teddy_cli.py teddy
    echo "✅ Created 'teddy' shortcut"
fi

# Verify installation
echo "🧪 Testing CLI installation..."
if python3 ai_teddy_cli.py --help > /dev/null 2>&1; then
    echo "✅ CLI installation successful!"
else
    echo "❌ CLI installation failed"
    exit 1
fi

echo ""
echo "🎉 Installation Complete!"
echo ""
echo "Usage examples:"
echo "  python3 ai_teddy_cli.py check --full"
echo "  python3 ai_teddy_cli.py test --security"
echo "  ./teddy check --full                    # Using shortcut"
echo ""
echo "For full documentation, see: CLI_USAGE_GUIDE.md"