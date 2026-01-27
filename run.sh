#!/bin/bash
# Quick start script for Kalshi Weather Bot

echo "=========================================="
echo "Kalshi Weather Bot - Quick Start"
echo "=========================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

echo "✓ Python 3 found"

# Check dependencies
echo ""
echo "Checking dependencies..."
if python3 -c "import requests, cryptography, bs4" 2>/dev/null; then
    echo "✓ All dependencies installed"
else
    echo "⚠ Installing dependencies..."
    pip install -r requirements.txt
fi

# Check API keys
echo ""
echo "Checking API keys..."
if [ -f "kalshi_public.txt" ] && [ -f "kalshi_private.pem" ]; then
    echo "✓ API keys found"
else
    echo "❌ API keys missing!"
    echo "   Please add:"
    echo "   - kalshi_public.txt (your API key ID)"
    echo "   - kalshi_private.pem (your private key)"
    exit 1
fi

# Check weather data
echo ""
echo "Checking weather data..."
if [ -f "weather_data.json" ]; then
    echo "✓ Weather data found"
    echo ""
    echo "Current weather data:"
    python3 -c "import json; d=json.load(open('weather_data.json')); print(f\"  High: {d.get('high_today')}°F at {d.get('high_time')}\"); print(f\"  Current: {d.get('current_temp')}°F\"); print(f\"  Updated: {d.get('timestamp')[:19]}\")"
else
    echo "⚠ No weather data found"
    echo ""
    echo "Would you like to enter weather data now? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        python3 manual_weather_input.py
    else
        echo ""
        echo "⚠ Bot will not work without weather data"
        echo "  Run: python3 manual_weather_input.py"
        exit 1
    fi
fi

echo ""
echo "=========================================="
echo "Setup complete! Starting bot..."
echo "=========================================="
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 main.py
