"""
Kalshi Weather Trading Bot - Main Entry Point

This bot identifies and trades on inefficiencies in Kalshi's Miami temperature markets
by comparing real-time weather data from wethr.net with market prices.
"""

import os
import time
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List

from dotenv import load_dotenv

from app.data.kalshi_client import KalshiClient
from app.data.weather_scraper import WeatherScraper
from app.data.open_meteo import OpenMeteoClient
from app.domain.opportunity import (
    parse_market_condition,
    estimate_prob_reach_threshold,
    estimate_prob_no_new_high,
    estimate_prob_yes,
)


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
        event_ticker: Optional[str] = None,
        market_ticker_override: Optional[str] = None,
        request_timeout: int = 15,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        weather_timeout: int = 10,
        orderbook_depth: int = 10,
        event_market_limit: int = 200,
        event_orderbook_limit: int = 50,
        event_markets_interval: int = 300,
        event_orderbook_interval: int = 120,
        open_meteo_enabled: bool = True,
        open_meteo_lat: float = 25.78805,
        open_meteo_lon: float = -80.31694,
        open_meteo_interval: int = 900,
        max_order_size: int = 5,
        max_position: int = 20,
        min_edge_cents: int = 2,
        fee_cents: float = 0.0,
        trade_enabled: bool = False,
        orders_note: Optional[str] = None,
    ):
        """
        Initialize the trading bot.
        
        Args:
            api_key_id: Kalshi API key ID
            private_key_path: Path to private key file
            base_url: Kalshi API base URL
            series_ticker: Kalshi series ticker (e.g., KXHIGHMIA)
            event_ticker: Kalshi event ticker (e.g., KXHIGHMIA-26JAN26)
            market_ticker_override: Override exact market ticker if needed
            request_timeout: HTTP timeout in seconds
            max_retries: Max HTTP retries for transient errors
            backoff_factor: HTTP retry backoff factor
            weather_timeout: Weather scraper timeout in seconds
            orderbook_depth: Depth for orderbook snapshots
            event_market_limit: Max markets to pull for event
            event_orderbook_limit: Max markets to fetch orderbooks for per cycle
            event_markets_interval: Seconds between event market refreshes
            event_orderbook_interval: Seconds between event orderbook refreshes
            open_meteo_enabled: Whether to pull Open-Meteo forecasts
            open_meteo_lat: Latitude for forecasts
            open_meteo_lon: Longitude for forecasts
            open_meteo_interval: Seconds between forecast refreshes
            max_order_size: Max contracts per order
            max_position: Max total contracts per ticker
            min_edge_cents: Minimum expected edge (cents) to trade
            fee_cents: Estimated fee per contract (cents)
            trade_enabled: If True, submit orders automatically
            orders_note: Optional manual note about recent orders
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
        self.event_ticker = event_ticker
        self.market_ticker_override = market_ticker_override
        self.market_ticker = None  # Will be set dynamically
        self.orderbook_depth = orderbook_depth
        self.event_market_limit = event_market_limit
        self.event_orderbook_limit = event_orderbook_limit
        self.event_markets_interval = event_markets_interval
        self.event_orderbook_interval = event_orderbook_interval
        self._last_event_markets_ts = 0.0
        self._last_event_orderbooks_ts = 0.0
        self._cached_event_markets = []
        self._cached_event_orderbooks = []
        self.open_meteo_enabled = open_meteo_enabled
        self.open_meteo_lat = open_meteo_lat
        self.open_meteo_lon = open_meteo_lon
        self.open_meteo_interval = open_meteo_interval
        self._last_open_meteo_ts = 0.0
        self._cached_open_meteo = {}
        self._open_meteo = OpenMeteoClient(timeout=request_timeout)
        self.max_order_size = max_order_size
        self.max_position = max_position
        self.min_edge_cents = min_edge_cents
        self.fee_cents = fee_cents
        self.trade_enabled = trade_enabled
        self.orders_note = orders_note

    @staticmethod
    def _normalize_bids(bids: List, depth: int = 10) -> List[Dict]:
        normalized = []
        for bid in (bids or [])[:depth]:
            if isinstance(bid, dict):
                price = bid.get("price")
                count = bid.get("count")
            elif isinstance(bid, (list, tuple)):
                price = bid[0] if len(bid) > 0 else None
                count = bid[1] if len(bid) > 1 else None
            else:
                price = None
                count = None
            normalized.append({"price": price, "count": count})
        return normalized
        
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
        return parse_market_condition(title)

    def _estimate_prob_reach_threshold(self, diff: int, hour: int) -> float:
        """Heuristic probability of reaching a higher temperature later today."""
        return estimate_prob_reach_threshold(diff, hour)

    def _estimate_prob_no_new_high(self, hour: int) -> float:
        """Heuristic probability that today's high will not increase further."""
        return estimate_prob_no_new_high(hour)

    def _estimate_prob_yes(self, condition: Dict, high_today: int, hour: int) -> Optional[float]:
        """Estimate probability for YES based on parsed market condition."""
        return estimate_prob_yes(condition, high_today, hour)

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
    
    def get_market_data(self, ticker: Optional[str] = None) -> Dict:
        """Fetch current market data for Miami temperature."""
        try:
            ticker = ticker or self.resolve_market_ticker()
            if not ticker:
                return {}
            print(f"Fetching market data for: {ticker}")
            
            market = self.kalshi.get_market(ticker)
            return market
        except Exception as e:
            print(f"Error fetching market data: {e}")
            return {}
    
    def get_orderbook(self, ticker: Optional[str] = None, depth: Optional[int] = None) -> Dict:
        """Fetch the order book for the Miami temperature market."""
        try:
            ticker = ticker or self.resolve_market_ticker()
            if not ticker:
                return {}
            orderbook = self.kalshi.get_market_orderbook(ticker, depth=depth or self.orderbook_depth)
            return orderbook
        except Exception as e:
            print(f"Error fetching orderbook: {e}")
            return {}
    
    def get_weather_data(self) -> Dict:
        """Fetch current Miami weather data."""
        return self.weather.get_miami_data()

    def get_event_markets(self) -> List[Dict]:
        """Fetch markets for the configured event ticker."""
        if not self.event_ticker:
            return []
        try:
            markets_resp = self.kalshi.get_markets(
                event_ticker=self.event_ticker,
                status="open",
                limit=self.event_market_limit,
            )
            markets = markets_resp.get("markets") or markets_resp.get("data") or []
            return [m for m in markets if isinstance(m, dict)]
        except Exception as e:
            print(f"Warning: failed to fetch event markets: {e}")
            return []

    def get_event_orderbooks(self, event_markets: List[Dict]) -> List[Dict]:
        """Fetch orderbooks for markets in the event."""
        orderbooks = []
        for market in event_markets[: self.event_orderbook_limit]:
            market_ticker = market.get("ticker")
            if not market_ticker:
                continue
            try:
                ob = self.kalshi.get_market_orderbook(market_ticker, depth=self.orderbook_depth)
                book = ob.get("orderbook") if isinstance(ob, dict) else {}
                yes_bids = (book.get("yes") or []) if isinstance(book, dict) else []
                no_bids = (book.get("no") or []) if isinstance(book, dict) else []
                orderbooks.append(
                    {
                        "ticker": market_ticker,
                        "yes": self._normalize_bids(yes_bids, depth=self.orderbook_depth),
                        "no": self._normalize_bids(no_bids, depth=self.orderbook_depth),
                    }
                )
            except Exception as e:
                print(f"Warning: failed to fetch orderbook for {market_ticker}: {e}")
        return orderbooks

    def get_event_markets_cached(self) -> List[Dict]:
        now = time.time()
        if self._cached_event_markets and now - self._last_event_markets_ts < self.event_markets_interval:
            return self._cached_event_markets
        self._cached_event_markets = self.get_event_markets()
        self._last_event_markets_ts = now
        return self._cached_event_markets

    def get_event_orderbooks_cached(self, event_markets: List[Dict]) -> List[Dict]:
        now = time.time()
        if self._cached_event_orderbooks and now - self._last_event_orderbooks_ts < self.event_orderbook_interval:
            return self._cached_event_orderbooks
        self._cached_event_orderbooks = self.get_event_orderbooks(event_markets)
        self._last_event_orderbooks_ts = now
        return self._cached_event_orderbooks

    def get_open_meteo_cached(self) -> Dict:
        if not self.open_meteo_enabled:
            return {}
        now = time.time()
        if self._cached_open_meteo and now - self._last_open_meteo_ts < self.open_meteo_interval:
            return self._cached_open_meteo
        gfs_high, ecmwf_high = self._open_meteo.get_daily_highs(
            lat=self.open_meteo_lat, lon=self.open_meteo_lon
        )
        self._cached_open_meteo = {
            "gfs_high": gfs_high,
            "ecmwf_high": ecmwf_high,
        }
        if gfs_high is not None and ecmwf_high is not None:
            self._cached_open_meteo["spread"] = abs(gfs_high - ecmwf_high)
        self._last_open_meteo_ts = now
        return self._cached_open_meteo
    
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
    
    def print_status(
        self,
        weather_data: Dict,
        market_data: Dict,
        orderbook: Dict,
        event_markets: Optional[list] = None,
        event_orderbooks: Optional[list] = None,
    ) -> None:
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
        
        # Event markets summary
        if event_markets:
            print(f"\n--- Event Markets ({len(event_markets)}) ---")
            book_by_ticker = {}
            for ob in event_orderbooks or []:
                if isinstance(ob, dict) and ob.get("ticker"):
                    book_by_ticker[ob["ticker"]] = ob
            for market in event_markets:
                if not isinstance(market, dict):
                    continue
                ticker = market.get("ticker", "N/A")
                title = market.get("title", "N/A")
                status = market.get("status", "N/A")
                last_price = market.get("last_price", "N/A")
                print(f"{ticker} | {status} | {last_price}¢ | {title}")
                ob = book_by_ticker.get(ticker)
                if ob:
                    yes = ob.get("yes") or []
                    no = ob.get("no") or []
                    if yes:
                        print(f"  YES top: {yes[0].get('price')}¢ x {yes[0].get('count')}")
                    if no:
                        print(f"  NO top: {no[0].get('price')}¢ x {no[0].get('count')}")

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
                # Check exchange status first; skip if down
                try:
                    exchange = self.kalshi.get_exchange_status()
                    if exchange.get("exchange_active") is False or exchange.get("trading_active") is False:
                        print("\n⚠ Exchange is down or trading paused; skipping this cycle.")
                        time.sleep(interval)
                        continue
                except Exception as e:
                    print(f"\n⚠ Could not fetch exchange status: {e}")

                # Fetch all data
                weather_data = self.get_weather_data()
                open_meteo = self.get_open_meteo_cached()
                event_markets = self.get_event_markets_cached()
                event_orderbooks = self.get_event_orderbooks_cached(event_markets)
                ticker = self.resolve_market_ticker()
                market_data = self.get_market_data(ticker=ticker)
                orderbook = self.get_orderbook(ticker=ticker, depth=self.orderbook_depth)
                portfolio = {}
                positions = {}
                try:
                    portfolio = self.kalshi.get_balance()
                except Exception as e:
                    print(f"Warning: failed to fetch balance: {e}")
                try:
                    positions = self.kalshi.get_positions()
                except Exception as e:
                    print(f"Warning: failed to fetch positions: {e}")
                orders = {}
                try:
                    orders = self.kalshi.get_orders(status="executed")
                except Exception as e:
                    print(f"Warning: failed to fetch orders: {e}")
                current_exposure = 0
                if ticker:
                    current_exposure = self.get_position_exposure(ticker)
                
                # Display status
                self.print_status(
                    weather_data,
                    market_data,
                    orderbook,
                    event_markets=event_markets,
                    event_orderbooks=event_orderbooks,
                )
                
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

                # Persist snapshot for frontend
                try:
                    snapshot_file = os.getenv("BOT_SNAPSHOT_FILE", "snapshot.json")
                    market_info = market_data.get("market") if isinstance(market_data, dict) else {}
                    book = orderbook.get("orderbook") if isinstance(orderbook, dict) else {}
                    yes_bids = (book.get("yes") or []) if isinstance(book, dict) else []
                    no_bids = (book.get("no") or []) if isinstance(book, dict) else []

                    snapshot = {
                        "timestamp": datetime.now().isoformat(),
                        "ticker": market_info.get("ticker"),
                        "title": market_info.get("title"),
                        "status": market_info.get("status"),
                        "last_price": market_info.get("last_price"),
                        "weather": {
                            "current_temp": weather_data.get("current_temp") if isinstance(weather_data, dict) else None,
                            "high_today": weather_data.get("high_today") if isinstance(weather_data, dict) else None,
                        },
                        "open_meteo": open_meteo,
                        "portfolio": portfolio,
                        "positions": positions,
                        "orders": orders,
                        "orders_note": self.orders_note,
                        "event_ticker": self.event_ticker,
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
                            "yes": self._normalize_bids(yes_bids, depth=self.orderbook_depth),
                            "no": self._normalize_bids(no_bids, depth=self.orderbook_depth),
                        },
                    }
                    tmp_file = f"{snapshot_file}.tmp"
                    with open(tmp_file, "w") as f:
                        json.dump(snapshot, f)
                    os.replace(tmp_file, snapshot_file)
                except Exception as e:
                    print(f"Warning: failed to write snapshot: {e}")
                
                # Wait before next update
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\nBot stopped by user.")
        except Exception as e:
            print(f"\n\nError in main loop: {e}")
            raise

def main():
    """Main entry point."""
    load_dotenv()

    class _Tee:
        def __init__(self, *streams):
            self._streams = streams

        def write(self, data):
            for stream in self._streams:
                stream.write(data)
                stream.flush()

        def flush(self):
            for stream in self._streams:
                stream.flush()

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

    log_file = os.getenv("BOT_LOG_FILE", "bot.log")
    try:
        log_handle = open(log_file, "a", buffering=1)
        sys.stdout = _Tee(sys.stdout, log_handle)
        sys.stderr = _Tee(sys.stderr, log_handle)
    except Exception as e:
        print(f"Warning: could not open log file {log_file}: {e}")

    # Load API credentials from env or fallback files
    api_key_id = os.getenv("KALSHI_API_KEY")
    private_key_path = os.getenv("KALSHI_PRIVATE_KEY", "kalshi_private.pem")

    if not api_key_id:
        api_key_file = Path("kalshi_public.txt")
        if not api_key_file.exists():
            print("Error: set KALSHI_API_KEY or create kalshi_public.txt")
            return
        with open(api_key_file) as f:
            api_key_id = f.read().strip()

    private_key_file = Path(private_key_path)
    if not private_key_file.exists():
        print(f"Error: private key not found at {private_key_path}")
        return

    # Initialize bot
    # Use demo API for testing: https://demo-api.kalshi.co
    # Use production API for live trading: https://api.elections.kalshi.com
    base_url = os.getenv("KALSHI_BASE_URL", "https://api.elections.kalshi.com")
    interval = _get_env_int("BOT_INTERVAL", 60)
    series_ticker = os.getenv("KALSHI_SERIES_TICKER", "KXHIGHMIA")
    event_ticker = os.getenv("KALSHI_EVENT_TICKER")
    market_ticker_override = os.getenv("KALSHI_MARKET_TICKER")
    request_timeout = _get_env_int("KALSHI_TIMEOUT", 15)
    max_retries = _get_env_int("KALSHI_MAX_RETRIES", 3)
    backoff_factor = _get_env_float("KALSHI_BACKOFF_FACTOR", 0.5)
    weather_timeout = _get_env_int("WEATHER_TIMEOUT", 10)
    orderbook_depth = _get_env_int("ORDERBOOK_DEPTH", 10)
    event_market_limit = _get_env_int("EVENT_MARKET_LIMIT", 200)
    event_orderbook_limit = _get_env_int("EVENT_ORDERBOOK_LIMIT", 50)
    event_markets_interval = _get_env_int("EVENT_MARKETS_INTERVAL", 300)
    event_orderbook_interval = _get_env_int("EVENT_ORDERBOOK_INTERVAL", 120)
    open_meteo_enabled = _get_env_bool("OPEN_METEO_ENABLED", True)
    open_meteo_lat = float(os.getenv("OPEN_METEO_LAT", "25.78805"))
    open_meteo_lon = float(os.getenv("OPEN_METEO_LON", "-80.31694"))
    open_meteo_interval = _get_env_int("OPEN_METEO_INTERVAL", 900)
    max_order_size = _get_env_int("MAX_ORDER_SIZE", 5)
    max_position = _get_env_int("MAX_POSITION", 20)
    min_edge_cents = _get_env_int("MIN_EDGE_CENTS", 2)
    fee_cents = _get_env_float("FEE_CENTS", 0.0)
    trade_enabled = _get_env_bool("TRADE_ENABLED", False)
    orders_note = os.getenv("ORDERS_NOTE")

    bot = WeatherTradingBot(
        api_key_id=api_key_id,
        private_key_path=str(private_key_file),
        base_url=base_url,
        series_ticker=series_ticker,
        event_ticker=event_ticker,
        market_ticker_override=market_ticker_override,
        request_timeout=request_timeout,
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        weather_timeout=weather_timeout,
        orderbook_depth=orderbook_depth,
        event_market_limit=event_market_limit,
        event_orderbook_limit=event_orderbook_limit,
        event_markets_interval=event_markets_interval,
        event_orderbook_interval=event_orderbook_interval,
        open_meteo_enabled=open_meteo_enabled,
        open_meteo_lat=open_meteo_lat,
        open_meteo_lon=open_meteo_lon,
        open_meteo_interval=open_meteo_interval,
        max_order_size=max_order_size,
        max_position=max_position,
        min_edge_cents=min_edge_cents,
        fee_cents=fee_cents,
        trade_enabled=trade_enabled,
        orders_note=orders_note,
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
