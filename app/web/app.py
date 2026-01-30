import json
import os
import time
from flask import Flask, jsonify, render_template
from flask_sock import Sock

from dotenv import load_dotenv

from app.services.bot import WeatherTradingBot

app = Flask(__name__, template_folder="templates", static_folder="static")
sock = Sock(app)

load_dotenv()

_SNAPSHOT_CACHE = {
    "ts": 0.0,
    "data": None,
}

def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default

def _get_env_float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default

def _init_bot():
    api_key_id = os.getenv("KALSHI_API_KEY")
    private_key_path = os.getenv("KALSHI_PRIVATE_KEY", "kalshi_private.pem")
    base_url = os.getenv("KALSHI_BASE_URL", "https://api.elections.kalshi.com")
    series_ticker = os.getenv("KALSHI_SERIES_TICKER", "KXHIGHMIA")
    event_ticker = os.getenv("KALSHI_EVENT_TICKER")
    market_ticker_override = os.getenv("KALSHI_MARKET_TICKER")

    if not api_key_id:
        return None, "Missing KALSHI_API_KEY env var"

    bot = WeatherTradingBot(
        api_key_id=api_key_id,
        private_key_path=private_key_path,
        base_url=base_url,
        series_ticker=series_ticker,
        event_ticker=event_ticker,
        market_ticker_override=market_ticker_override,
        request_timeout=_get_env_int("KALSHI_TIMEOUT", 15),
        max_retries=_get_env_int("KALSHI_MAX_RETRIES", 3),
        backoff_factor=_get_env_float("KALSHI_BACKOFF_FACTOR", 0.5),
        weather_timeout=_get_env_int("WEATHER_TIMEOUT", 10),
        orderbook_depth=_get_env_int("ORDERBOOK_DEPTH", 10),
        event_market_limit=_get_env_int("EVENT_MARKET_LIMIT", 200),
        event_orderbook_limit=_get_env_int("EVENT_ORDERBOOK_LIMIT", 50),
        event_markets_interval=_get_env_int("EVENT_MARKETS_INTERVAL", 300),
        event_orderbook_interval=_get_env_int("EVENT_ORDERBOOK_INTERVAL", 120),
        event_orderbook_workers=_get_env_int("EVENT_ORDERBOOK_WORKERS", 8),
        open_meteo_enabled=os.getenv("OPEN_METEO_ENABLED", "true").lower() in {"1", "true", "yes", "y", "on"},
        open_meteo_lat=float(os.getenv("OPEN_METEO_LAT", "25.78805")),
        open_meteo_lon=float(os.getenv("OPEN_METEO_LON", "-80.31694")),
        open_meteo_interval=_get_env_int("OPEN_METEO_INTERVAL", 900),
        open_meteo_workers=_get_env_int("OPEN_METEO_WORKERS", 2),
        max_order_size=_get_env_int("MAX_ORDER_SIZE", 5),
        max_position=_get_env_int("MAX_POSITION", 20),
        min_edge_cents=_get_env_int("MIN_EDGE_CENTS", 2),
        fee_cents=_get_env_float("FEE_CENTS", 0.0),
        trade_enabled=os.getenv("TRADE_ENABLED", "false").lower() in {"1", "true", "yes", "y", "on"},
        orders_note=os.getenv("ORDERS_NOTE"),
    )
    return bot, None

def _build_snapshot(bot: WeatherTradingBot) -> dict:
    weather_data = bot.get_weather_data()
    open_meteo = bot.get_open_meteo_cached()
    event_markets = bot.get_event_markets_cached()
    event_orderbooks = bot.get_event_orderbooks_cached(event_markets)
    ticker = bot.resolve_market_ticker()
    market_data = bot.get_market_data(ticker=ticker)
    orderbook = bot.get_orderbook(ticker=ticker, depth=bot.orderbook_depth)

    portfolio = {}
    positions = {}
    orders = {}
    try:
        portfolio = bot.kalshi.get_balance()
    except Exception:
        pass
    try:
        positions = bot.kalshi.get_positions()
    except Exception:
        pass
    try:
        orders = bot.kalshi.get_orders(status="executed")
    except Exception:
        pass

    market_info = (market_data.get("market") or {}) if isinstance(market_data, dict) else {}
    book = orderbook.get("orderbook") if isinstance(orderbook, dict) else {}
    yes_bids = (book.get("yes") or []) if isinstance(book, dict) else []
    no_bids = (book.get("no") or []) if isinstance(book, dict) else []

    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ticker": market_info.get("ticker"),
        "title": market_info.get("title"),
        "status": market_info.get("status"),
        "last_price": market_info.get("last_price"),
        "weather": {
            "current_temp": weather_data.get("current_temp") if isinstance(weather_data, dict) else None,
            "high_today": weather_data.get("high_today") if isinstance(weather_data, dict) else None,
            "forecast_high": weather_data.get("forecast_high") if isinstance(weather_data, dict) else None,
            "forecast_period": weather_data.get("forecast_period") if isinstance(weather_data, dict) else None,
            "forecast_updated": weather_data.get("forecast_updated") if isinstance(weather_data, dict) else None,
            "forecast_source": weather_data.get("forecast_source") if isinstance(weather_data, dict) else None,
        },
        "open_meteo": open_meteo,
        "portfolio": portfolio,
        "positions": positions,
        "orders": orders,
        "orders_note": bot.orders_note,
        "event_ticker": bot.event_ticker,
        "event_markets": [
            {
                "ticker": m.get("ticker"),
                "title": m.get("title"),
                "status": m.get("status"),
                "last_price": m.get("last_price"),
            }
            for m in event_markets
            if isinstance(m, dict)
        ],
        "event_orderbooks": event_orderbooks,
        "orderbook": {
            "yes": bot._normalize_bids(yes_bids, depth=bot.orderbook_depth),
            "no": bot._normalize_bids(no_bids, depth=bot.orderbook_depth),
        },
    }

def _write_snapshot(snapshot: dict) -> None:
    snapshot_file = os.getenv("BOT_SNAPSHOT_FILE", "snapshot.json")
    tmp_file = f"{snapshot_file}.tmp"
    with open(tmp_file, "w") as f:
        json.dump(snapshot, f)
    os.replace(tmp_file, snapshot_file)


@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/snapshot")
def snapshot():
    snapshot_file = os.getenv("BOT_SNAPSHOT_FILE", "snapshot.json")
    if os.path.exists(snapshot_file):
        try:
            ttl = _get_env_float("SNAPSHOT_CACHE_TTL", 2.0)
            now = time.time()
            cached = _SNAPSHOT_CACHE["data"]
            if cached is not None and now - _SNAPSHOT_CACHE["ts"] < ttl:
                return app.response_class(cached, mimetype="application/json")
            with open(snapshot_file, "r") as f:
                data = f.read()
            _SNAPSHOT_CACHE["data"] = data
            _SNAPSHOT_CACHE["ts"] = now
            return app.response_class(data, mimetype="application/json")
        except Exception as e:
            return jsonify({"error": f"Snapshot read failed: {e}"}), 500
    _SNAPSHOT_CACHE["data"] = None
    _SNAPSHOT_CACHE["ts"] = 0.0
    return jsonify({"error": "Snapshot missing. Use /api/snapshot/refresh to generate one."}), 404


@app.post("/api/snapshot/refresh")
def snapshot_refresh():
    bot, error = _init_bot()
    if error:
        return jsonify({"error": error}), 400
    try:
        snapshot = _build_snapshot(bot)
        _write_snapshot(snapshot)
        return jsonify(snapshot)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sock.route("/ws/logs")
def logs(ws):
    log_file = os.getenv("BOT_LOG_FILE", "bot.log")
    if not os.path.exists(log_file):
        ws.send("Log file not found. Start main.py to generate logs.")
        return

    try:
        with open(log_file, "r") as f:
            # Send last ~200 lines on connect
            try:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(size - 4000, 0))
            except OSError:
                f.seek(0)
            for line in f.readlines()[-200:]:
                ws.send(line.rstrip("\n"))

            while True:
                line = f.readline()
                if line:
                    ws.send(line.rstrip("\n"))
                else:
                    time.sleep(0.5)
    except Exception as e:
        ws.send(f"Log stream error: {e}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
