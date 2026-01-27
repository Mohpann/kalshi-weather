import os
import time
from flask import Flask, jsonify, render_template
from flask_sock import Sock

from main import WeatherTradingBot

app = Flask(__name__)
sock = Sock(app)


@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/snapshot")
def snapshot():
    snapshot_file = os.getenv("BOT_SNAPSHOT_FILE", "snapshot.json")
    if os.path.exists(snapshot_file):
        try:
            with open(snapshot_file, "r") as f:
                data = f.read()
            return app.response_class(data, mimetype="application/json")
        except Exception as e:
            return jsonify({"error": f"Snapshot read failed: {e}"}), 500

    api_key_id = os.getenv("KALSHI_API_KEY")
    private_key_path = os.getenv("KALSHI_PRIVATE_KEY", "kalshi_private.pem")
    base_url = os.getenv("KALSHI_BASE_URL", "https://api.elections.kalshi.com")
    series_ticker = os.getenv("KALSHI_SERIES_TICKER", "KXHIGHMIA")
    event_ticker = os.getenv("KALSHI_EVENT_TICKER")
    market_ticker_override = os.getenv("KALSHI_MARKET_TICKER")

    if not api_key_id:
        return jsonify({"error": "Missing KALSHI_API_KEY env var"}), 400

    try:
        bot = WeatherTradingBot(
            api_key_id=api_key_id,
            private_key_path=private_key_path,
            base_url=base_url,
            series_ticker=series_ticker,
            event_ticker=event_ticker,
            market_ticker_override=market_ticker_override,
            request_timeout=int(os.getenv("KALSHI_TIMEOUT", "15")),
            max_retries=int(os.getenv("KALSHI_MAX_RETRIES", "3")),
            backoff_factor=float(os.getenv("KALSHI_BACKOFF_FACTOR", "0.5")),
            weather_timeout=int(os.getenv("WEATHER_TIMEOUT", "10")),
        )

        exchange = bot.kalshi.get_exchange_status()
        exchange_active = exchange.get("exchange_active")
        trading_active = exchange.get("trading_active")

        ticker = bot.resolve_market_ticker()
        weather = bot.get_weather_data()
        market_data = bot.get_market_data() if ticker else {}
        market_info = market_data.get("market") if isinstance(market_data, dict) else {}

        event_ticker = os.getenv("KALSHI_EVENT_TICKER")
        event_markets = []
        if event_ticker:
            try:
                markets_resp = bot.kalshi.get_markets(event_ticker=event_ticker, status="open", limit=200)
                markets = markets_resp.get("markets") or markets_resp.get("data") or []
                event_markets = [
                    {
                        "ticker": m.get("ticker"),
                        "title": m.get("title"),
                        "status": m.get("status"),
                        "last_price": m.get("last_price"),
                    }
                    for m in markets
                    if isinstance(m, dict)
                ]
            except Exception as e:
                event_markets = [{"ticker": None, "title": f"Error: {e}", "status": None, "last_price": None}]

        return jsonify(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "exchange": {
                    "exchange_active": exchange_active,
                    "trading_active": trading_active,
                },
                "market": {
                    "ticker": market_info.get("ticker"),
                    "title": market_info.get("title"),
                    "status": market_info.get("status"),
                    "last_price": market_info.get("last_price"),
                },
                "event_ticker": event_ticker,
                "event_markets": event_markets,
                "event_orderbooks": [],
                "open_meteo": {},
                "weather": weather,
            }
        )
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
