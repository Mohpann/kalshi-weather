# Copilot Instructions for kalshi-weather-boy-v2

## Project Overview
Algorithmic trading bot that exploits pricing inefficiencies in Kalshi's Miami temperature prediction markets by comparing real-time weather observations with market prices. Trades the daily "Highest temperature in Miami today?" market using data from the official KMIA weather station.

## Architecture

### Four-Component Design
1. **`kalshi_auth.py`**: RSA-PSS signature generation (SHA256) for API authentication
2. **`kalshi_client.py`**: Full Kalshi API wrapper (markets, orders, positions, orderbook)
3. **`weather_scraper.py`**: BeautifulSoup-based scraper for wethr.net (current temp, daily high/low)
4. **`main.py`**: Heartbeat loop coordinating data fetching, analysis, and trading

### Data Flow
```
wethr.net scrape → weather_data
Kalshi API calls → market_data + orderbook
    ↓
analyze_opportunity() → trading decision
    ↓
place_order() or skip
```

## Critical Implementation Details

### Authentication (Kalshi-Specific)
**CRITICAL**: Kalshi uses RSA-PSS (NOT RSA-PKCS1v15). Signature algorithm:
```python
message = f"{timestamp_ms}{METHOD}{path_without_query_params}"
signature = private_key.sign(message, PSS(MGF1(SHA256()), DIGEST_LENGTH), SHA256())
headers = {
    'KALSHI-ACCESS-KEY': api_key_id,
    'KALSHI-ACCESS-SIGNATURE': base64(signature),
    'KALSHI-ACCESS-TIMESTAMP': timestamp_ms
}
```
- Strip query params BEFORE signing: `/trade-api/v2/markets/TICKER` not `/trade-api/v2/markets/TICKER?status=open`
- Timestamp in milliseconds (not seconds!)
- Private key is PEM format

### Market Ticker Format
Dynamic date-based: `KXHIGHMIA-{DD}{MMM}{YY}` (e.g., `KXHIGHMIA-26JAN26`)
- Bot auto-generates today's ticker in `get_todays_market_ticker()`
- Market changes daily - never hardcode tickers

### Weather Data Parsing
**CURRENT LIMITATION**: Wethr.net blocks automated requests (406 errors).

Workaround: Manual data entry via `manual_weather_input.py`
- Creates `weather_data.json` with current observations
- `weather_scraper.py` falls back to this file when scraping fails
- Update throughout day as temperatures change

Future alternatives:
- Browser automation (Selenium/Playwright)
- Official NOAA ASOS API for KMIA station
- Commercial weather APIs (OpenWeatherMap, etc.)

### Trading Workflow
1. **Run bot**: `python main.py`
2. **Choose environment**: Edit line 205 in main.py
   - Production: `https://api.kalshi.com` (real money!)
   - Demo: `https://demo-api.kalshi.co` (testing)
3. **Strategy implementation**: Add logic to `analyze_opportunity()` in main.py
4. **Order placement**: Use `kalshi_client.place_order()` with prices in CENTS (1-99)

### Setup Requirements
```bash
pip install -r requirements.txt

# Place API keys in root:
# - kalshi_public.txt (API key ID)
# - kalshi_private.pem (RSA private key)

# Enter weather data manually (wethr.net blocks scraping):
python3 manual_weather_input.py

# Test setup:
python3 test_setup.py

# Run bot:
python3 main.py  # Starts 60-second heartbeat loop
```

## Key Conventions

### Error Handling
- All API methods raise on HTTP errors (`response.raise_for_status()`)
- Weather scraper returns empty dict `{}` on failure (never crashes bot)
- Main loop has keyboard interrupt handler for graceful shutdown

### Price Format
- All Kalshi prices in CENTS (integer 1-99)
- Display: divide by 100 for dollars
- Order example: `yes_price=70` means 70¢ or 70% probability

### Time Sensitivity
- **CRITICAL**: Wethr.net does NOT publish next-day forecasts
- Bot only trades CURRENT DAY market
- Best opportunities late in day (after ~6pm) when daily high is likely established

## Testing Without Real Money
```bash
# 1. Change base_url in main.py line 205:
base_url = "https://demo-api.kalshi.co"

# 2. Get demo API keys from demo.kalshi.com (separate from production)

# 3. Test individual components:
python -c "from kalshi_client import KalshiClient; c = KalshiClient('key', 'kalshi_private.pem', 'https://demo-api.kalshi.co'); print(c.get_balance())"
```

## Common Pitfalls
1. **Signature errors**: Check timestamp is milliseconds, query params stripped, PSS padding used
2. **Market not found**: Ticker format must match exactly (date-based, uppercase)
3. **Weather parsing fails**: Wethr.net HTML structure can change - check regex patterns
4. **Order rejection**: Prices must be 1-99 cents, YES + NO = 100

## Safety Mechanisms to Add
- Position size limits (avoid overexposure)
- Max daily loss threshold
- API rate limit tracking (Kalshi docs specify limits)
- Order validation before submission
- Kill switch for emergencies

## Extending the Bot
- **New markets**: Modify `get_todays_market_ticker()` for different cities/series
- **Better strategy**: Enhance `analyze_opportunity()` with time-of-day logic, historical patterns
- **Multiple markets**: Run separate bot instances or add multi-market support to main loop
- **Logging**: Add file logging for post-trade analysis
