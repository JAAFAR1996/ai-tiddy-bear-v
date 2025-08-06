#!/bin/bash
# AI Teddy Parent App - Quick Start Script

echo "🧸 AI Teddy Parent App - Starting..."
echo "=================================="

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Using .env.example..."
    cp .env.example .env 2>/dev/null || echo "API_BASE_URL=http://localhost:8000" > .env
fi

echo ""
echo "🚀 Starting Expo..."
echo "=================================="
echo "📱 Scan QR code with Expo Go app"
echo "💻 Press 'w' for web browser"
echo "📱 Press 'a' for Android emulator"
echo "📱 Press 'i' for iOS simulator"
echo "=================================="
echo ""
echo "Test Credentials:"
echo "  Email: a@a.com / Password: 123"
echo "  Email: test@test.com / Password: 123456"
echo "=================================="

# Start Expo
npm start