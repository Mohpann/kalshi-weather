# Baseline Performance Profile (Phase 0)

This baseline is derived from code inspection and runtime behavior (no instrumentation yet).

## Where Time Is Spent
Each bot cycle (default 60s) performs multiple network calls:
- Kalshi:
  - `/exchange/status`
  - `/markets`, `/markets/{ticker}`
  - `/markets/{ticker}/orderbook`
  - `/portfolio/balance`, `/portfolio/positions`, `/portfolio/orders`
- Weather:
  - NWS station observation
  - Meteosource current/daily
- Open-Meteo forecast pull

These calls dominate cycle latency and are **I/O-bound**.

## CPU Hotspots
- NWS API + Meteosource weather sources
- Small local transforms (parsing titles, computing heuristic probs)

These are minor relative to network I/O.

## Memory Footprint
- In-memory JSON payloads from external APIs
- Cached event markets/orderbooks in `WeatherTradingBot`

Memory usage is low (<100MB) under normal operation; transient spikes can occur if large market lists are fetched.

## I/O-Bound vs CPU-Bound
- **I/O-bound:** external API calls (Kalshi, NWS, Meteosource, Open-Meteo)
- **CPU-bound:** parsing titles, minimal computation in `analyze_opportunity`
- **Disk I/O:** write `snapshot.json`, append `bot.log`

## Suggested Measurement Points (for later phases)
- Per API call latency (requests duration)
- End-to-end cycle time
- Snapshot serialization time
- Memory RSS (optional)
