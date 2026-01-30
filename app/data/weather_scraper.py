"""
Weather Data Scraper

Fetches current temperature data and forecasts from NWS and Meteosource for Miami.
"""

from typing import Dict
import time
import os

from app.data.meteosource_client import MeteosourceClient
from app.data.nws_client import NWSClient

class WeatherScraper:
    """Fetches weather data from NWS and Meteosource for market analysis."""
    
    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.nws_cache_ttl = int(os.getenv("NWS_CACHE_TTL", "600"))
        self._nws_cache_ts = 0.0
        self._nws_cache_data = {}
        self.nws_station_id = os.getenv("NWS_STATION_ID", "KMIA")
        self.nws_user_agent = os.getenv(
            "NWS_USER_AGENT", "kalshi-weather-bot (contact: example@example.com)"
        )
        self.nws_lat = float(os.getenv("NWS_LAT", "25.78805"))
        self.nws_lon = float(os.getenv("NWS_LON", "-80.31694"))
        self.meteosource_key = os.getenv("METEOSOURCE_API_KEY")
        self.meteosource_tier = os.getenv("METEOSOURCE_TIER", "free").strip().lower()
        self.meteosource_base_url = os.getenv("METEOSOURCE_BASE_URL")
        self.meteosource_lat = float(os.getenv("METEOSOURCE_LAT", "25.78805"))
        self.meteosource_lon = float(os.getenv("METEOSOURCE_LON", "-80.31694"))

    @staticmethod
    def _merge_weather(primary: Dict, secondary: Dict) -> Dict:
        if not primary:
            return secondary or {}
        if not secondary:
            return primary
        merged = dict(primary)
        for key in ("current_temp", "high_today", "low_today", "observation_time"):
            if merged.get(key) is None and secondary.get(key) is not None:
                merged[key] = secondary.get(key)
        return merged

    def _get_nws_data(self) -> Dict:
        now = time.time()
        if self._nws_cache_data and now - self._nws_cache_ts < self.nws_cache_ttl:
            return dict(self._nws_cache_data)
        try:
            client = NWSClient(user_agent=self.nws_user_agent, timeout=self.timeout)
            data = client.get_latest_observation(self.nws_station_id)
            forecast = client.get_forecast_high(self.nws_lat, self.nws_lon)
            if forecast:
                data.update(forecast)
            if data.get("current_temp") is not None:
                print("✓ Loaded NWS station data")
                self._nws_cache_data = dict(data)
                self._nws_cache_ts = now
                return data
        except Exception as e:
            print(f"⚠ NWS fetch failed ({e})")
        return {}

    def _get_meteosource_data(self) -> Dict:
        if not self.meteosource_key:
            return {}
        base_url = self.meteosource_base_url
        if not base_url:
            if self.meteosource_tier == "flexi":
                base_url = "https://www.meteosource.com/api/v1/flexi/point"
            else:
                base_url = "https://www.meteosource.com/api/v1/free/point"
        try:
            client = MeteosourceClient(self.meteosource_key, timeout=self.timeout, base_url=base_url)
            data = client.get_miami_data(self.meteosource_lat, self.meteosource_lon)
            if data.get("current_temp") is not None:
                print("✓ Loaded Meteosource data")
                return data
        except Exception as e:
            print(f"⚠ Meteosource fetch failed ({e})")
            print(f"  Meteosource URL: {base_url}")
        return {}

    @staticmethod
    def _attach_meteosource_fields(target: Dict, meteo: Dict) -> None:
        if not meteo:
            return
        target["meteosource_current_temp"] = meteo.get("current_temp")
        target["meteosource_high_today"] = meteo.get("high_today")
        target["meteosource_low_today"] = meteo.get("low_today")
        target["meteosource_observation_time"] = meteo.get("observation_time")
        target["meteosource_source"] = meteo.get("source")
    
    def get_miami_data(self) -> Dict:
        """
        Fetch current Miami weather data.
        """
        meteo_data = self._get_meteosource_data()
        # Try NWS station observations first
        nws_data = self._get_nws_data()
        if nws_data.get("current_temp") is not None:
            self._attach_meteosource_fields(nws_data, meteo_data)
            if nws_data.get("high_today") is None or nws_data.get("low_today") is None:
                nws_data = self._merge_weather(nws_data, meteo_data)
            return nws_data

        # Try Meteosource next
        if meteo_data.get("current_temp") is not None:
            self._attach_meteosource_fields(meteo_data, meteo_data)
            return meteo_data
        return {}
    
    def print_summary(self, data: Dict) -> None:
        """Print formatted weather data summary."""
        if not data:
            print("No data available")
            return
        
        print("\n=== Miami Weather Data ===")
        print(f"Source: {data.get('source', 'unknown')}")
        print(f"Timestamp: {data.get('timestamp', 'N/A')[:19]}")
        print(f"Current Temp: {data.get('current_temp', 'N/A')}°F")
        print(f"Temp Change: {data.get('temp_change', 'N/A')}°F")
        print(f"Today's High: {data.get('high_today', 'N/A')}°F at {data.get('high_time', 'N/A')}")
        print(f"Today's Low: {data.get('low_today', 'N/A')}°F at {data.get('low_time', 'N/A')}")
        print(f"Last Observation: {data.get('observation_time', 'N/A')}")
        print("=" * 30)
