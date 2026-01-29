# Kalshi Weather Bot - Quick Reference

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add API keys to project root:
#    - kalshi_public.txt
#    - kalshi_private.pem

# 3. Run bot
python3 main.py

# OR use the quick start script:
./run.sh
```

## Daily Workflow

1. **Morning**: Verify NWS/Meteosource updates are flowing
2. **Throughout day**: Monitor bot for trading opportunities
3. **Evening**: Confirm daily high on dashboard

## Project Structure

```
kalshi-weather-boy-v2/
├── main.py                   # Bot entry point (heartbeat loop)
├── kalshi_auth.py           # RSA-PSS authentication
├── kalshi_client.py         # Kalshi API wrapper
├── weather_scraper.py       # Weather data (API sources)
├── nws_client.py            # NWS API client
├── meteosource_client.py    # Meteosource API client
├── test_setup.py            # System verification
├── run.sh                   # Quick start script
├── requirements.txt         # Python dependencies
├── kalshi_public.txt        # Your API key (DO NOT COMMIT)
├── kalshi_private.pem       # Your private key (DO NOT COMMIT)
├── README.md                # Full documentation
└── .github/
    └── copilot-instructions.md  # AI agent guide
```

## Key Files

### Main Bot ([main.py](main.py))
- `WeatherTradingBot` class
- `run_heartbeat()` - Main monitoring loop
- `analyze_opportunity()` - **ADD YOUR STRATEGY HERE**
- `get_todays_market_ticker()` - Auto-generates ticker

### API Client ([kalshi_client.py](kalshi_client.py))
- `get_market()` - Fetch market data
- `get_orderbook()` - Get bids/asks
- `place_order()` - Submit trade
- `get_positions()` - View holdings

### Authentication ([kalshi_auth.py](kalshi_auth.py))
- `create_signature()` - RSA-PSS signing
- `get_headers()` - Auth headers for requests

## Important Constants

**Base URLs**:
- Production: `https://api.elections.kalshi.com` (real money!)
- Demo: `https://demo-api.kalshi.co` (testing)

**Market Ticker**: `KXHIGHMIA-{DD}{MMM}{YY}`
- Example: `KXHIGHMIA-26JAN26`
- Auto-generated in bot

**Price Format**: Cents (1-99)
- 70 = 70¢ = 70% probability
- YES + NO = 100

## Trading Strategy Template

Edit `main.py` → `analyze_opportunity()`:

```python
def analyze_opportunity(self, weather_data, market_data, orderbook):
    current_temp = weather_data.get('current_temp')
    high_today = weather_data.get('high_today')
    
    # Example: Late day, high established
    if is_after_6pm and high_today > 85:
        # Market should reflect this
        # Compare with orderbook prices
        # Return trading decision
        pass
    
    return {'has_opportunity': False, ...}
```

## Testing

```bash
# Full system test
python3 test_setup.py

# Test Kalshi connection
python3 -c "from kalshi_client import KalshiClient; \
c = KalshiClient('$(cat kalshi_public.txt)', 'kalshi_private.pem', 'https://api.elections.kalshi.com'); \
print(c.get_balance())"

```

## Common Issues

**"406 Not Acceptable" from wethr.net**
→ NWS/Meteosource should still provide data; wethr.net is only a last-resort scrape

**"Connection refused" to Kalshi**
→ Check internet connection, verify API endpoint

**"Signature error"**
→ Verify timestamp is milliseconds, query params stripped

**"Market not found"**
→ Ticker format must be exact: `KXHIGHMIA-26JAN26`

## Safety Checklist

- [ ] Start with demo API first
- [ ] Test with small position sizes
- [ ] Implement max loss limits
- [ ] Add order validation
- [ ] Monitor for API rate limits
- [ ] Keep API keys secure (never commit!)

## Environment Switching

Edit [main.py](main.py) line 205:

```python
# Testing
base_url = "https://demo-api.kalshi.co"

# Production (real money!)
base_url = "https://api.kalshi.com"
```

## Resources

- [Kalshi API Docs](https://docs.kalshi.com)
- [Miami Market](https://kalshi.com/markets/kxhighmia)
- [Weather Data](https://wethr.net/market/miami)
- [Full README](README.md)
- [Copilot Instructions](.github/copilot-instructions.md)
