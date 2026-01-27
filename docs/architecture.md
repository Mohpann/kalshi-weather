# Architecture (Phase 0)

## Overview
This project has two primary execution paths:

1) **Bot loop** (CLI) — `main.py` (wrapper for `app/services/bot.py`)
   - Periodically fetches weather, market data, and orderbooks
   - Computes opportunity heuristics
   - Logs to stdout + `bot.log`
   - Writes `snapshot.json` for the dashboard

2) **Dashboard** (Flask) — `app.py` (wrapper for `app/web/app.py`)
   - Serves `templates/index.html` and static assets
   - `GET /api/snapshot` reads `snapshot.json` or pulls live data
   - `/ws/logs` streams `bot.log`

## Modules and Responsibilities

- `app/services/bot.py`
  - Orchestrates the bot loop
  - Pulls weather + market data
  - Runs `analyze_opportunity()`
  - Writes `snapshot.json`

- `app/data/kalshi_auth.py`
  - RSA-PSS signing per Kalshi API

- `app/data/kalshi_client.py`
  - API client for Kalshi (markets, orderbooks, orders, portfolio)

- `app/data/weather_scraper.py`
  - Weather ingestion with fallback chain:
    1) NWS station observations (KMIA)
    2) Meteosource (free tier)
    3) Wethr.net scrape (last resort)

- `app/data/nws_client.py`
  - NWS API client (station observations)

- `app/data/meteosource_client.py`
  - Meteosource API client (current + daily)

- `app/data/open_meteo.py`
  - Open-Meteo model highs (forecast cross-check)

- `app/web/app.py`
  - Flask app + snapshot API + WebSocket log stream

- `app/web/templates/index.html` + `app/web/static/*`
  - Dashboard UI

## Data Flow

### Bot loop
```
weather_scraper -> (NWS/Meteosource/Wethr) -> weather_data
kalshi_client -> market + orderbook + portfolio + positions
open_meteo -> forecast highs
analyze_opportunity(weather, market, orderbook) -> recommendation
write snapshot.json -> consumed by dashboard
```

### Dashboard
```
GET /api/snapshot -> snapshot.json (or live fetch)
Render UI -> positions, orders, portfolio, weather, logs
WebSocket /ws/logs -> stream bot.log
```

## Persistence
- `snapshot.json` (latest bot state)
- `bot.log` (streamed logs)

## Config Handling
- `.env` (loaded by bot and Flask)
- `run.sh` exports env vars and starts bot + Flask

## Entry Points
- Bot: `python3 main.py` (or `./run.sh`)
- Dashboard: `python3 app.py` (or `./run.sh`)
