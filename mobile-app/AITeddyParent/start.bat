@echo off
REM AI Teddy Parent App - Quick Start Script for Windows

echo.
echo  AI Teddy Parent App - Starting...
echo ==================================
echo.

REM Check if node_modules exists
if not exist "node_modules" (
    echo Installing dependencies...
    npm install
)

REM Check if .env exists
if not exist ".env" (
    echo No .env file found. Creating from example...
    copy .env.example .env >nul 2>&1 || echo API_BASE_URL=http://localhost:8000 > .env
)

echo.
echo  Starting Expo...
echo ==================================
echo  Scan QR code with Expo Go app
echo  Press 'w' for web browser
echo  Press 'a' for Android emulator
echo  Press 'i' for iOS simulator
echo ==================================
echo.
echo Test Credentials:
echo   Email: a@a.com / Password: 123
echo   Email: test@test.com / Password: 123456
echo ==================================
echo.

REM Start Expo
npm start