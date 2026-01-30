"""
Weather Data Scraper

Fetches current temperature data and forecasts from wethr.net for Miami.
This data is used to identify inefficiencies in the Kalshi temperature markets.

Enhanced with better headers and user agent rotation to avoid bot detection.
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict
import re
import random
import time
from datetime import datetime
import os

from app.data.meteosource_client import MeteosourceClient
from app.data.nws_client import NWSClient

class WeatherScraper:
    """Scrapes weather data from wethr.net for market analysis."""
    
    # Pool of realistic user agents (latest browsers)
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    
    def __init__(self, timeout: int = 15):
        self.base_url = "https://wethr.net"
        self.timeout = timeout
        self.session = requests.Session()
        self.last_request_time = 0
        self.min_request_delay = 2  # Seconds between requests
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
    
    def _get_headers(self) -> Dict[str, str]:
        """Generate realistic browser headers."""
        return {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        }
    
    def _respect_rate_limit(self):
        """Add delay between requests to appear human-like."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_delay:
            sleep_time = self.min_request_delay - time_since_last + random.uniform(0.5, 1.5)
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def get_miami_data(self) -> Dict:
        """
        Fetch current Miami weather data.
        """
        url = f"{self.base_url}/market/miami"

        # Try NWS station observations first
        nws_data = self._get_nws_data()
        if nws_data.get("current_temp") is not None:
            if nws_data.get("high_today") is None or nws_data.get("low_today") is None:
                meteo_data = self._get_meteosource_data()
                nws_data = self._merge_weather(nws_data, meteo_data)
            return nws_data

        # Try Meteosource next
        meteo_data = self._get_meteosource_data()
        if meteo_data.get("current_temp") is not None:
            return meteo_data
        
        try:
            # Respect rate limiting
            self._respect_rate_limit()
            
            # Try with enhanced headers
            headers = self._get_headers()
            response = self.session.get(url, headers=headers, timeout=self.timeout, allow_redirects=True)
            
            # If blocked, retry once with different user agent
            if response.status_code == 406:
                print("⚠ Received 406, retrying with different headers...")
                time.sleep(random.uniform(2, 4))
                headers = self._get_headers()
                response = self.session.get(url, headers=headers, timeout=self.timeout)
            
            response.raise_for_status()
            
            # Validate response
            if len(response.text) < 100 or 'Not Acceptable' in response.text:
                print("⚠ Blocked by wethr.net.")
                return {}
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            data = self._parse_weather_data(soup)
            
            if data and data.get('current_temp'):
                print("✓ Successfully scraped weather data")
                return data
            else:
                print("⚠ Could not parse data.")
                return {}
            
        except Exception as e:
            print(f"⚠ Scraping failed ({e})")
            return {}
    
    def _parse_weather_data(self, soup: BeautifulSoup) -> Dict:
        """Parse weather data with multiple strategies."""
        data = {
            'timestamp': datetime.now().isoformat(),
            'source': 'wethr.net_scrape'
        }
        
        # Look for "CURRENT TEMP"
        current = soup.find(string=re.compile(r'CURRENT TEMP', re.I))
        if current:
            parent = current.find_parent()
            if parent:
                temp = parent.find_next(string=re.compile(r'\d+°'))
                if temp:
                    match = re.search(r'(\d+)', temp)
                    if match:
                        data['current_temp'] = int(match.group(1))
                
                time_text = parent.find_next(string=re.compile(r'\d+:\d+\s*[AP]M', re.I))
                if time_text:
                    data['observation_time'] = time_text.strip()
        
        # Look for "TEMP CHANGE"
        temp_change = soup.find(string=re.compile(r'TEMP CHANGE', re.I))
        if temp_change:
            parent = temp_change.find_parent()
            if parent:
                change = parent.find_next(string=re.compile(r'[+-]?\d+°'))
                if change:
                    match = re.search(r'([+-]?\d+)', change)
                    if match:
                        data['temp_change'] = int(match.group(1))
        
        # Look for "WETHR EXTREMES"
        extremes = soup.find(string=re.compile(r'WETHR EXTREMES', re.I))
        if extremes:
            parent = extremes.find_parent()
            if parent:
                text = parent.get_text()
                temps = re.findall(r'(\d+)°\s*(\d+:\d+\s*[AP]M)', text, re.I)
                if len(temps) >= 2:
                    data['high_today'] = int(temps[0][0])
                    data['high_time'] = temps[0][1]
                    data['low_today'] = int(temps[1][0])
                    data['low_time'] = temps[1][1]
        
        return data
    
    def get_forecast(self) -> Dict:
        """
        Attempt to get forecast data from wethr.net.
        
        Note: According to requirements, wethr.net does not release forecasts 
        for the following day, so this may return limited data.
        
        Returns:
            Dictionary with any available forecast information
        """
        # This is a placeholder - wethr.net may require Pro subscription
        # for detailed forecasts. We'll focus on current observations.
        print("Note: Wethr.net forecasts for next day may not be available")
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
