# Kalshi Weather Boy v2 🌡️📈

An algorithmic trading bot that identifies and trades on inefficiencies in Kalshi's Miami temperature prediction markets by comparing real-time weather data with market prices.

## Overview

This bot continuously monitors:
- **Weather data** from wethr.net (official KMIA station at Miami International Airport)
- **Market data** from Kalshi's "Highest temperature in Miami today?" market
- **Order book** with live bids and asks

It analyzes discrepancies between observed temperatures and market pricing to identify profitable trading opportunities.

## Architecture

### Core Components

1. **`kalshi_auth.py`** - Authentication Module
   - Implements RSA-PSS signature generation with SHA256
   - Loads private keys and creates signed request headers
   - Follows Kalshi's authentication specification exactly

2. **`kalshi_client.py`** - Kalshi API Client
   - Full-featured API wrapper for Kalshi trading platform
   - Methods for market data, positions, orders, and trading
   - Handles authenticated requests automatically

3. **`weather_scraper.py`** - Weather Data Scraper
   - Scrapes live temperature data from wethr.net
   - Extracts current temp, daily high/low, and observation times
   - Uses BeautifulSoup for HTML parsing

4. **`main.py`** - Trading Bot Main Loop
   - Coordinates data fetching from both sources
   - Runs heartbeat monitoring at configurable intervals
   - Analyzes opportunities and displays status updates
   - Ready for trading logic implementation

## Setup

### Prerequisites

```bash
# Python 3.8+
python3 --version

# Install dependencies
pip install -r requirements.txt
```

### API Keys

1. Get your Kalshi API credentials:
   - Go to [kalshi.com](https://kalshi.com) (or [demo.kalshi.com](https://demo.kalshi.com) for testing)
   - Navigate to Account & Security → API Keys
   - Create a new key and download both files

2. Place in project root:
   - `kalshi_public.txt` - Your API key ID
   - `kalshi_private.pem` - Your private key file

**⚠️ SECURITY**: Never commit these files to git (already in `.gitignore`)

### Weather Data

**Important**: wethr.net blocks automated scraping with 406 errors. Use manual data entry:

```bash
python3 manual_weather_input.py
```

This creates `weather_data.json` which the bot reads. Update this file periodically throughout the day as temperatures change.

### Configuration

Edit `main.py` line 205 to choose environment:
```python
base_url = "https://api.elections.kalshi.com"  # Production (real money)
# OR
base_url = "https://demo-api.kalshi.co"  # Demo/testing
```

## Usage

### Run the Bot

```bash
# Step 1: Enter current weather data
python3 manual_weather_input.py

# Step 2: Start the bot
python3 main.py
```

### Run the Frontend (Flask)

```bash
pip install -r requirements.txt
python3 app.py
```

Open `http://localhost:5000` in your browser.

### Open-Meteo Cross-Check

Optional: pull GFS/ECMWF daily highs from Open-Meteo for the KMIA station.

```bash
export OPEN_METEO_ENABLED=true
export OPEN_METEO_LAT=25.78805
export OPEN_METEO_LON=-80.31694
```

### Live Logs (WebSocket)

The frontend streams `main.py` logs over WebSocket at `/ws/logs`. Start the bot to generate logs:

```bash
export BOT_LOG_FILE=bot.log
python3 main.py
```

The bot will:
1. Authenticate with Kalshi API
2. Display your account balance
3. Start heartbeat monitoring (60-second intervals)
4. Print weather data, market data, and order book continuously

### Example Output

```
Testing Kalshi API connection...
✓ Connected! Balance: $1000.00

Starting Kalshi Weather Trading Bot...
Monitoring Miami temperature market
Update interval: 60 seconds

============================================================
Status Update: 2026-01-26 21:10:45
============================================================

--- Weather Data (wethr.net) ---
Current Temp: 70°F
Today's High: 88°F at 2:21 PM
Today's Low: 70°F at 9:10 PM
Last Update: 9:10 PM

--- Kalshi Market Data ---
Ticker: KXHIGHMIA-26JAN26
Title: Highest temperature in Miami today?
Status: open
Volume: 1234
Last Price: 65¢

--- Order Book ---
YES side (top 3):
  1. Price: 66¢, Qty: 100
  2. Price: 65¢, Qty: 200
  3. Price: 64¢, Qty: 150
...
```

## Development Guide

### Adding Trading Logic

The trading strategy goes in `main.py` → `analyze_opportunity()`:

```python
def analyze_opportunity(self, weather_data, market_data, orderbook):
    # Your strategy here
    # Example: If it's 8pm and high is 88°F, market should reflect that
    
    if analysis['has_opportunity']:
        # Place order via:
        self.kalshi.place_order(
            ticker=ticker,
            action='buy',
            side='yes',
            count=10,
            order_type='limit',
            yes_price=70  # Price in cents
        )
```

### Key Concepts

**Market Ticker Format**: `KXHIGHMIA-26JAN26` (date-based)
- The bot automatically generates today's ticker

**Temperature Resolution**: 
- Markets settle based on official KMIA station readings
- Wethr.net scrapes the same official source
- Temperature is recorded in whole degrees Fahrenheit

**Pricing**:
- All prices in cents (1-99)
- YES price + NO price = 100
- Example: 70¢ YES = 70% probability

### Testing

```bash
# Test system setup
python3 test_setup.py

# Test authentication
python3 -c "from kalshi_client import KalshiClient; \
c = KalshiClient('$(cat kalshi_public.txt)', 'kalshi_private.pem', 'https://demo-api.kalshi.co'); \
print(c.get_balance())"

# Enter weather data manually
python3 manual_weather_input.py
```

### Alternative Weather Data Sources

Since wethr.net blocks scraping, consider:
1. **Manual entry** (current solution via `manual_weather_input.py`)
2. **Browser automation** (Selenium/Playwright to bypass detection)
3. **Commercial APIs** (Weather.com API, OpenWeatherMap, etc.)
4. **Official sources** (NOAA/NWS ASOS data for KMIA station)

## Important Notes

### Market Timing
- Wethr.net does NOT release forecasts for the next day
- Bot focuses on current day's market only
- Best opportunities often late in the day when high is established

### Safety Considerations
- Start with demo environment
- Test thoroughly before using real money
- Implement position limits
- Add error handling for network issues
- Monitor for API rate limits

### Data Sources
- **Weather**: [wethr.net/market/miami](https://wethr.net/market/miami)
- **Market**: [kalshi.com/markets/kxhighmia](https://kalshi.com/markets/kxhighmia)
- **API Docs**: [docs.kalshi.com](https://docs.kalshi.com)

## File Structure

```
kalshi-weather-boy-v2/
├── main.py                 # Main bot entry point
├── kalshi_auth.py         # Authentication logic
├── kalshi_client.py       # Kalshi API wrapper
├── weather_scraper.py     # Wethr.net scraper
├── requirements.txt       # Python dependencies
├── .gitignore            # Git ignore (includes API keys)
├── kalshi_public.txt     # Your API key (not in git)
├── kalshi_private.pem    # Your private key (not in git)
└── .github/
    └── copilot-instructions.md  # AI agent guide
```

## Contributing

This is a personal trading bot. If you fork it:
1. Use your own API keys
2. Understand that trading involves risk
3. Test thoroughly in demo environment
4. Don't rely on this for financial advice

## License

Private use only. See Kalshi's terms of service for API usage restrictions.

## Disclaimer

This bot is for educational purposes. Trading on prediction markets involves risk. The developer assumes no liability for trading losses. Use at your own risk.
