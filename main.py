"""
Kalshi Weather Trading Bot - Main Entry Point

This bot identifies and trades on inefficiencies in Kalshi's Miami temperature markets
by comparing real-time weather data from wethr.net with market prices.
"""

import os
import time
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from kalshi_client import KalshiClient
from weather_scraper import WeatherScraper


class WeatherTradingBot:
    """
    Main trading bot that monitors Miami temperature data and Kalshi markets.
    """
    
    def __init__(
        self,
        api_key_id: str,
        private_key_path: str,
        base_url: str = "https://api.elections.kalshi.com",
        series_ticker: str = "KXHIGHMIA",
        market_ticker_override: Optional[str] = None,
        request_timeout: int = 15,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        weather_timeout: int = 10,
        max_order_size: int = 5,
        max_position: int = 20,
        min_edge_cents: int = 2,
        fee_cents: float = 0.0,
        trade_enabled: bool = False,
    ):
        """
        Initialize the trading bot.
        
        Args:
            api_key_id: Kalshi API key ID
            private_key_path: Path to private key file
            base_url: Kalshi API base URL
            series_ticker: Kalshi series ticker (e.g., KXHIGHMIA)
            market_ticker_override: Override exact market ticker if needed
            request_timeout: HTTP timeout in seconds
            max_retries: Max HTTP retries for transient errors
            backoff_factor: HTTP retry backoff factor
            weather_timeout: Weather scraper timeout in seconds
            max_order_size: Max contracts per order
            max_position: Max total contracts per ticker
            min_edge_cents: Minimum expected edge (cents) to trade
            fee_cents: Estimated fee per contract (cents)
            trade_enabled: If True, submit orders automatically
        """
        self.kalshi = KalshiClient(
            api_key_id,
            private_key_path,
            base_url,
            timeout=request_timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
        )
        self.weather = WeatherScraper(timeout=weather_timeout)
        self.series_ticker = series_ticker
        self.market_ticker_override = market_ticker_override
        self.market_ticker = None  # Will be set dynamically
        self.max_order_size = max_order_size
        self.max_position = max_position
        self.min_edge_cents = min_edge_cents
        self.fee_cents = fee_cents
        self.trade_enabled = trade_enabled
        
    def get_todays_market_ticker(self) -> Optional[str]:
        """
        Determine today's Miami temperature market ticker.
        Format: KXHIGHMIA-DDMMMYY (e.g., KXHIGHMIA-26JAN26)
        """
        today = datetime.now()
        # Format: 26JAN26
        date_str = today.strftime("%d%b%y").upper()
        ticker = f"KXHIGHMIA-{date_str}"
        return ticker

    def resolve_market_ticker(self) -> Optional[str]:
        """Resolve a valid market ticker using override, then series lookup."""
        if self.market_ticker_override:
            return self.market_ticker_override

        ticker = self.get_todays_market_ticker()
        if not self.series_ticker:
            return ticker

        try:
            series = self.kalshi.get_series(self.series_ticker)
            markets = series.get("markets") or series.get("series", {}).get("markets") or []
            for market in markets:
                if isinstance(market, dict) and market.get("ticker") == ticker:
                    return ticker
                if isinstance(market, str) and market == ticker:
                    return ticker
            print(f"Warning: {ticker} not found in series {self.series_ticker}; trying open markets list")
        except Exception as e:
            print(f"Warning: series lookup failed ({e}); trying open markets list")

        try:
            markets_resp = self.kalshi.get_markets(series_ticker=self.series_ticker, status="open", limit=200)
            markets = markets_resp.get("markets") or markets_resp.get("data") or []
            if markets:
                now_ts = int(datetime.now().timestamp())

                def _parse_ts(value):
                    if isinstance(value, (int, float)):
                        return int(value)
                    if isinstance(value, str):
                        try:
                            return int(value)
                        except ValueError:
                            try:
                                return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
                            except ValueError:
                                return None
                    return None

                def _close_ts(market):
                    for key in ("close_ts", "close_time", "close_timestamp", "close_ts_s"):
                        if key in market:
                            return _parse_ts(market.get(key))
                    return None

                upcoming = []
                for market in markets:
                    if not isinstance(market, dict):
                        continue
                    close_ts = _close_ts(market)
                    if close_ts is not None and close_ts >= now_ts:
                        upcoming.append((close_ts, market))
                if upcoming:
                    upcoming.sort(key=lambda item: item[0])
                    return upcoming[0][1].get("ticker") or ticker
                return markets[0].get("ticker") or ticker
            print(f"Warning: no open markets found for {self.series_ticker}; using {ticker}")
            return ticker
        except Exception as e:
            print(f"Warning: open markets lookup failed ({e}); using {ticker}")
            return ticker

    def _parse_market_condition(self, title: str) -> Optional[Dict]:
        """Best-effort parse of market title to infer temperature condition."""
        if not title:
            return None
        temps = [int(t) for t in re.findall(r'(-?\d+)\s*°?\s*F', title, re.I)]
        title_l = title.lower()
        if len(temps) >= 2 and ("between" in title_l or " to " in title_l):
            low, high = sorted(temps[:2])
            return {"type": "range", "low": low, "high": high}
        if any(k in title_l for k in ["at least", "or higher", "or above", "greater than", "above", ">="]):
            return {"type": "gte", "threshold": temps[0] if temps else None}
        if any(k in title_l for k in ["at most", "or lower", "or below", "less than", "below", "<="]):
            return {"type": "lte", "threshold": temps[0] if temps else None}
        if temps:
            return {"type": "unknown", "temps": temps}
        return None

    def _estimate_prob_reach_threshold(self, diff: int, hour: int) -> float:
        """Heuristic probability of reaching a higher temperature later today."""
        if diff <= 0:
            return 0.95
        diff_factor = max(0.05, 1 - (diff / 10))
        if hour < 10:
            time_factor = 1.1
        elif hour < 14:
            time_factor = 1.15
        elif hour < 17:
            time_factor = 0.95
        elif hour < 20:
            time_factor = 0.7
        else:
            time_factor = 0.4
        prob = diff_factor * time_factor
        return max(0.05, min(0.95, prob))

    def _estimate_prob_no_new_high(self, hour: int) -> float:
        """Heuristic probability that today's high will not increase further."""
        if hour >= 22:
            return 0.98
        if hour >= 20:
            return 0.95
        if hour >= 18:
            return 0.9
        if hour >= 16:
            return 0.8
        if hour >= 14:
            return 0.7
        if hour >= 12:
            return 0.6
        return 0.4

    def _estimate_prob_yes(self, condition: Dict, high_today: int, hour: int) -> Optional[float]:
        """Estimate probability for YES based on parsed market condition."""
        if not condition or high_today is None:
            return None
        ctype = condition.get("type")
        if ctype == "gte":
            threshold = condition.get("threshold")
            if threshold is None:
                return None
            if high_today >= threshold:
                return 0.99
            diff = threshold - high_today
            return self._estimate_prob_reach_threshold(diff, hour)
        if ctype == "lte":
            threshold = condition.get("threshold")
            if threshold is None:
                return None
            if high_today > threshold:
                return 0.01
            if high_today == threshold:
                return self._estimate_prob_no_new_high(hour)
            diff = threshold - high_today
            return max(0.01, 1 - self._estimate_prob_reach_threshold(diff, hour))
        if ctype == "range":
            low = condition.get("low")
            high = condition.get("high")
            if low is None or high is None:
                return None
            if high_today > high:
                return 0.01
            if high_today < low:
                diff = low - high_today
                prob_reach_low = self._estimate_prob_reach_threshold(diff, hour)
                prob_not_exceed_high = self._estimate_prob_no_new_high(hour)
                return max(0.01, min(0.99, prob_reach_low * prob_not_exceed_high))
            prob_not_exceed_high = self._estimate_prob_no_new_high(hour)
            return max(0.01, min(0.99, prob_not_exceed_high))
        return None

    def get_position_exposure(self, ticker: str) -> int:
        """Estimate current exposure (contracts) for a ticker."""
        try:
            positions = self.kalshi.get_positions()
            positions_list = (
                positions.get("positions")
                or positions.get("portfolio", {}).get("positions")
                or positions.get("data")
                or []
            )
            for pos in positions_list:
                if not isinstance(pos, dict):
                    continue
                if pos.get("ticker") != ticker:
                    continue
                for key in ("position", "count", "size", "quantity", "net_position"):
                    value = pos.get(key)
                    if isinstance(value, (int, float)):
                        return int(abs(value))
                yes_val = pos.get("yes") or pos.get("yes_position")
                no_val = pos.get("no") or pos.get("no_position")
                if isinstance(yes_val, (int, float)) or isinstance(no_val, (int, float)):
                    return int(abs(yes_val or 0) + abs(no_val or 0))
            return 0
        except Exception as e:
            print(f"Warning: failed to fetch positions ({e})")
            return 0
    
    def get_market_data(self) -> Dict:
        """Fetch current market data for Miami temperature."""
        try:
            ticker = self.resolve_market_ticker()
            if not ticker:
                return {}
            print(f"Fetching market data for: {ticker}")
            
            market = self.kalshi.get_market(ticker)
            return market
        except Exception as e:
            print(f"Error fetching market data: {e}")
            return {}
    
    def get_orderbook(self) -> Dict:
        """Fetch the order book for the Miami temperature market."""
        try:
            ticker = self.resolve_market_ticker()
            if not ticker:
                return {}
            orderbook = self.kalshi.get_market_orderbook(ticker, depth=10)
            return orderbook
        except Exception as e:
            print(f"Error fetching orderbook: {e}")
            return {}
    
    def get_weather_data(self) -> Dict:
        """Fetch current Miami weather data."""
        return self.weather.get_miami_data()
    
    def analyze_opportunity(
        self,
        weather_data: Dict,
        market_data: Dict,
        orderbook: Dict,
        current_exposure: int = 0,
    ) -> Dict:
        """
        Analyze if there's a trading opportunity based on weather vs market data.
        
        Args:
            weather_data: Current weather observations
            market_data: Kalshi market information
            orderbook: Current bids and asks
            
        Returns:
            Dictionary with analysis results and trading recommendation
        """
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'has_opportunity': False,
            'confidence': 0,
            'recommendation': None,
            'reasoning': [],
            'order': None,
        }
        
        # Extract key data
        current_temp = weather_data.get('current_temp')
        high_today = weather_data.get('high_today')
        
        if not current_temp or not high_today:
            analysis['reasoning'].append("Insufficient weather data")
            return analysis
        
        # Log the current state
        analysis['reasoning'].append(f"Current temp: {current_temp}°F")
        analysis['reasoning'].append(f"Today's high so far: {high_today}°F")

        # Pull best prices for context
        book = orderbook.get('orderbook', {}) if orderbook else {}
        yes_bids = book.get('yes', []) or []
        no_bids = book.get('no', []) or []
        market_info = market_data.get('market', {}) if market_data else {}
        title = market_info.get('title')
        if title:
            analysis['reasoning'].append(f"Market title: {title}")
        def _bid_price(bid):
            if isinstance(bid, dict):
                return bid.get("price")
            if isinstance(bid, (list, tuple)) and bid:
                return bid[0]
            return None

        if yes_bids:
            analysis['reasoning'].append(f"Best YES bid: {_bid_price(yes_bids[0])}¢")
        if no_bids:
            analysis['reasoning'].append(f"Best NO bid: {_bid_price(no_bids[0])}¢")
        
        # Heuristic EV model based on parsed market condition
        condition = self._parse_market_condition(title or "")
        if not condition or condition.get("type") == "unknown":
            analysis['reasoning'].append("Market condition not parsed; skipping EV model")
            return analysis

        now_hour = datetime.now().hour
        prob_yes = self._estimate_prob_yes(condition, high_today, now_hour)
        if prob_yes is None:
            analysis['reasoning'].append("Probability model could not estimate outcome")
            return analysis

        analysis['reasoning'].append(f"Heuristic P(YES): {prob_yes:.2f}")

        yes_price = None
        no_price = None
        if yes_bids:
            yes_price = _bid_price(yes_bids[0])
        if no_bids:
            no_price = _bid_price(no_bids[0])
        if yes_price is None:
            yes_price = market_info.get('last_price')
        if no_price is None and isinstance(yes_price, (int, float)):
            no_price = 100 - yes_price

        if yes_price is None and no_price is None:
            analysis['reasoning'].append("No usable price data; skipping EV model")
            return analysis

        def _ev(prob: float, price: Optional[float]) -> Optional[float]:
            if price is None:
                return None
            return prob * 100 - price - self.fee_cents

        ev_yes = _ev(prob_yes, yes_price)
        ev_no = _ev(1 - prob_yes, no_price)

        analysis['reasoning'].append(
            f"EV YES: {ev_yes:.2f}¢" if ev_yes is not None else "EV YES: N/A"
        )
        analysis['reasoning'].append(
            f"EV NO: {ev_no:.2f}¢" if ev_no is not None else "EV NO: N/A"
        )

        best_side = None
        best_ev = None
        best_price = None
        if ev_yes is not None and (best_ev is None or ev_yes > best_ev):
            best_side = "yes"
            best_ev = ev_yes
            best_price = yes_price
        if ev_no is not None and (best_ev is None or ev_no > best_ev):
            best_side = "no"
            best_ev = ev_no
            best_price = no_price

        if best_ev is None or best_ev < self.min_edge_cents:
            analysis['reasoning'].append(
                f"No edge >= {self.min_edge_cents}¢; skipping trade"
            )
            return analysis

        if best_price is None:
            analysis['reasoning'].append("No limit price available; skipping trade")
            return analysis

        remaining_capacity = max(0, self.max_position - current_exposure)
        order_size = min(self.max_order_size, remaining_capacity)
        if order_size <= 0:
            analysis['reasoning'].append("Position limit reached; skipping trade")
            return analysis

        analysis['has_opportunity'] = True
        analysis['confidence'] = round(best_ev, 2)
        analysis['recommendation'] = f"Buy {best_side.upper()} (edge {best_ev:.2f}¢)"
        price_int = int(round(best_price))
        price_int = max(1, min(99, price_int))
        analysis['order'] = {
            "side": best_side,
            "price": price_int,
            "count": int(order_size),
        }
        
        return analysis
    
    def print_status(self, weather_data: Dict, market_data: Dict, orderbook: Dict) -> None:
        """Print current status of weather and market."""
        print("\n" + "="*60)
        print(f"Status Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # Weather info
        print("\n--- Weather Data (wethr.net) ---")
        if weather_data:
            print(f"Current Temp: {weather_data.get('current_temp', 'N/A')}°F")
            print(f"Today's High: {weather_data.get('high_today', 'N/A')}°F at {weather_data.get('high_time', 'N/A')}")
            print(f"Today's Low: {weather_data.get('low_today', 'N/A')}°F at {weather_data.get('low_time', 'N/A')}")
            print(f"Last Update: {weather_data.get('observation_time', 'N/A')}")
        else:
            print("No weather data available")
        
        # Market info
        print("\n--- Kalshi Market Data ---")
        if market_data:
            market_info = market_data.get('market', {})
            print(f"Ticker: {market_info.get('ticker', 'N/A')}")
            print(f"Title: {market_info.get('title', 'N/A')}")
            print(f"Status: {market_info.get('status', 'N/A')}")
            print(f"Volume: {market_info.get('volume', 'N/A')}")
            print(f"Last Price: {market_info.get('last_price', 'N/A')}¢")
        else:
            print("No market data available")
        
        # Order book
        print("\n--- Order Book ---")
        if orderbook:
            book = orderbook.get('orderbook') or {}
            yes_bids = book.get('yes') or []
            no_bids = book.get('no') or []
            
            print("YES side (top 3):")
            for i, bid in enumerate(yes_bids[:3], 1):
                if isinstance(bid, dict):
                    price = bid.get('price', 'N/A')
                    qty = bid.get('count', 'N/A')
                elif isinstance(bid, (list, tuple)):
                    price = bid[0] if len(bid) > 0 else 'N/A'
                    qty = bid[1] if len(bid) > 1 else 'N/A'
                else:
                    price = 'N/A'
                    qty = 'N/A'
                print(f"  {i}. Price: {price}¢, Qty: {qty}")
            
            print("NO side (top 3):")
            for i, bid in enumerate(no_bids[:3], 1):
                if isinstance(bid, dict):
                    price = bid.get('price', 'N/A')
                    qty = bid.get('count', 'N/A')
                elif isinstance(bid, (list, tuple)):
                    price = bid[0] if len(bid) > 0 else 'N/A'
                    qty = bid[1] if len(bid) > 1 else 'N/A'
                else:
                    price = 'N/A'
                    qty = 'N/A'
                print(f"  {i}. Price: {price}¢, Qty: {qty}")
        else:
            print("No order book data available")
        
        print("="*60 + "\n")
    
    def run_heartbeat(self, interval: int = 60) -> None:
        """
        Run continuous monitoring with heartbeat updates.
        
        Args:
            interval: Seconds between updates (default: 60)
        """
        print("Starting Kalshi Weather Trading Bot...")
        print(f"Monitoring Miami temperature market")
        print(f"Update interval: {interval} seconds")
        print(f"Press Ctrl+C to stop\n")
        
        try:
            while True:
                # Fetch all data
                weather_data = self.get_weather_data()
                market_data = self.get_market_data()
                orderbook = self.get_orderbook()
                ticker = self.resolve_market_ticker()
                current_exposure = 0
                if ticker:
                    current_exposure = self.get_position_exposure(ticker)
                
                # Display status
                self.print_status(weather_data, market_data, orderbook)
                
                # Analyze for opportunities
                analysis = self.analyze_opportunity(
                    weather_data,
                    market_data,
                    orderbook,
                    current_exposure=current_exposure,
                )
                
                if analysis['has_opportunity']:
                    print("\n🚨 TRADING OPPORTUNITY DETECTED 🚨")
                    print(f"Confidence: {analysis['confidence']}")
                    print(f"Recommendation: {analysis['recommendation']}")
                    print("Reasoning:")
                    for reason in analysis['reasoning']:
                        print(f"  - {reason}")
                    if self.trade_enabled and ticker and analysis.get("order"):
                        order = analysis["order"]
                        try:
                            response = self.kalshi.place_order(
                                ticker=ticker,
                                action='buy',
                                side=order['side'],
                                count=order['count'],
                                order_type='limit',
                                yes_price=order['price'] if order['side'] == 'yes' else None,
                                no_price=order['price'] if order['side'] == 'no' else None,
                            )
                            print(f"✓ Order placed: {response}")
                        except Exception as e:
                            print(f"✗ Order failed: {e}")
                
                # Wait before next update
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\nBot stopped by user.")
        except Exception as e:
            print(f"\n\nError in main loop: {e}")
            raise

def main():
    """Main entry point."""
    def _get_env_int(name: str, default: int) -> int:
        value = os.getenv(name, "").strip()
        if not value:
            return default
        try:
            return int(value)
        except ValueError:
            print(f"Warning: invalid {name}='{value}', using {default}")
            return default

    def _get_env_float(name: str, default: float) -> float:
        value = os.getenv(name, "").strip()
        if not value:
            return default
        try:
            return float(value)
        except ValueError:
            print(f"Warning: invalid {name}='{value}', using {default}")
            return default

    def _get_env_bool(name: str, default: bool) -> bool:
        value = os.getenv(name, "").strip().lower()
        if not value:
            return default
        return value in {"1", "true", "yes", "y", "on"}

    # Load API credentials
    api_key_file = Path("kalshi_public.txt")
    private_key_file = Path("kalshi_private.pem")

    if not api_key_file.exists():
        print("Error: kalshi_public.txt not found")
        return

    if not private_key_file.exists():
        print("Error: kalshi_private.pem not found")
        return

    # Read API key
    with open(api_key_file) as f:
        api_key_id = f.read().strip()

    # Initialize bot
    # Use demo API for testing: https://demo-api.kalshi.co
    # Use production API for live trading: https://api.elections.kalshi.com
    base_url = os.getenv("KALSHI_BASE_URL", "https://api.elections.kalshi.com")
    interval = _get_env_int("BOT_INTERVAL", 60)
    series_ticker = os.getenv("KALSHI_SERIES_TICKER", "KXHIGHMIA")
    market_ticker_override = os.getenv("KALSHI_MARKET_TICKER")
    request_timeout = _get_env_int("KALSHI_TIMEOUT", 15)
    max_retries = _get_env_int("KALSHI_MAX_RETRIES", 3)
    backoff_factor = _get_env_float("KALSHI_BACKOFF_FACTOR", 0.5)
    weather_timeout = _get_env_int("WEATHER_TIMEOUT", 10)
    max_order_size = _get_env_int("MAX_ORDER_SIZE", 5)
    max_position = _get_env_int("MAX_POSITION", 20)
    min_edge_cents = _get_env_int("MIN_EDGE_CENTS", 2)
    fee_cents = _get_env_float("FEE_CENTS", 0.0)
    trade_enabled = _get_env_bool("TRADE_ENABLED", False)

    bot = WeatherTradingBot(
        api_key_id=api_key_id,
        private_key_path=str(private_key_file),
        base_url=base_url,
        series_ticker=series_ticker,
        market_ticker_override=market_ticker_override,
        request_timeout=request_timeout,
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        weather_timeout=weather_timeout,
        max_order_size=max_order_size,
        max_position=max_position,
        min_edge_cents=min_edge_cents,
        fee_cents=fee_cents,
        trade_enabled=trade_enabled,
    )

    # Test connection
    print("Testing Kalshi API connection...")
    try:
        status = bot.kalshi.get_exchange_status()
        exchange_status = status.get("exchange_status")
        if exchange_status is None:
            exchange_status = {
                "exchange_active": status.get("exchange_active"),
                "trading_active": status.get("trading_active"),
            }
        print(f"✓ Connected! Exchange status: {exchange_status}\n")
    except Exception as e:
        print(f"✗ Connection failed: {e}\n")
        return

    # Run the heartbeat monitor
    bot.run_heartbeat(interval=interval)


if __name__ == "__main__":
    main()
