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

# Load .env if present
if [ -f ".env" ]; then
    set -a
    . ./.env
    set +a
fi

# Check dependencies
echo ""
echo "Checking dependencies..."
if python3 -c "import requests, cryptography, bs4, flask, flask_sock, dotenv" 2>/dev/null; then
    echo "✓ All dependencies installed"
else
    echo "⚠ Installing dependencies..."
    pip install -r requirements.txt
fi

# Check API keys
echo ""
echo "Checking API keys..."
api_key_file="kalshi_public.txt"
private_key_file="${KALSHI_PRIVATE_KEY:-kalshi_private.pem}"

if [ -n "$KALSHI_API_KEY" ] && [ ! -f "$api_key_file" ]; then
    echo "Writing kalshi_public.txt from KALSHI_API_KEY..."
    echo "$KALSHI_API_KEY" > "$api_key_file"
fi

if [ -f "$api_key_file" ] && [ -f "$private_key_file" ]; then
    echo "✓ API keys found"
else
    echo "❌ API keys missing!"
    echo "   Please add:"
    echo "   - kalshi_public.txt (your API key ID) or set KALSHI_API_KEY"
    echo "   - ${private_key_file} (your private key) or set KALSHI_PRIVATE_KEY"
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

echo ""
echo "=========================================="
echo "Setup complete! Starting bot..."
echo "=========================================="
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 -m app.services.bot &
bot_pid=$!

echo "Starting Flask frontend..."
python3 -m app.web.app &
web_pid=$!

trap "echo ''; echo 'Stopping...'; kill $bot_pid $web_pid 2>/dev/null" INT TERM
wait
