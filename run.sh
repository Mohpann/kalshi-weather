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
if python3 -c "import requests, cryptography, bs4, flask" 2>/dev/null; then
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

# Optional: Open-Meteo defaults
export OPEN_METEO_ENABLED=${OPEN_METEO_ENABLED:-true}
export OPEN_METEO_LAT=${OPEN_METEO_LAT:-25.78805}
export OPEN_METEO_LON=${OPEN_METEO_LON:--80.31694}

# Optional: Event ticker (example: KXHIGHMIA-26JAN27)
if [ -z "$KALSHI_EVENT_TICKER" ]; then
    echo ""
    echo "KALSHI_EVENT_TICKER not set (e.g., KXHIGHMIA-26JAN27)."
    echo "Enter event ticker (or leave blank to skip):"
    read -r event_input
    if [ -n "$event_input" ]; then
        export KALSHI_EVENT_TICKER="$event_input"
    fi
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
        echo "⚠ Continuing without weather data (bot will run with limited info)"
        echo "  You can add it later: python3 manual_weather_input.py"
    fi
fi

echo ""
echo "=========================================="
echo "Setup complete! Starting bot..."
echo "=========================================="
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 main.py &
bot_pid=$!

echo "Starting Flask frontend..."
python3 app.py &
web_pid=$!

trap "echo ''; echo 'Stopping...'; kill $bot_pid $web_pid 2>/dev/null" INT TERM
wait
