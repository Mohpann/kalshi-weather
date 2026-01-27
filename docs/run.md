# Run Guide (Phase 0)

## Requirements
- Python 3.9+
- `pip install -r requirements.txt`

## Environment
Copy `.env.example` to `.env` and fill:
- `KALSHI_API_KEY`
- `KALSHI_PRIVATE_KEY`
- `KALSHI_BASE_URL`
- `NWS_USER_AGENT`
- `METEOSOURCE_API_KEY` (free tier)

Optional:
- `KALSHI_EVENT_TICKER` to view event markets
- `OPEN_METEO_*` for forecast checks

## Run (Bot + Dashboard)
```bash
./run.sh
```

## Run (Bot Only)
```bash
python3 main.py
```

## Run (Dashboard Only)
```bash
python3 app.py
```

## Expected Output (Bot)
- Prints Kalshi exchange status
- Periodic status updates every 60s
- Writes `snapshot.json`

## Expected Output (Dashboard)
- `http://localhost:5000` shows snapshot data
- Logs stream into the Live Logs panel
