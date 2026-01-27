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
import json
import random
import time
from datetime import datetime
from pathlib import Path


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
        Fetch current Miami weather data from wethr.net.
        Falls back to manual data if scraping fails.
        """
        url = f"{self.base_url}/market/miami"
        
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
                print("⚠ Blocked by wethr.net, using manual data...")
                return self._load_manual_data()
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            data = self._parse_weather_data(soup)
            
            if data and data.get('current_temp'):
                print("✓ Successfully scraped weather data")
                return data
            else:
                print("⚠ Could not parse data, using manual fallback...")
                return self._load_manual_data()
            
        except Exception as e:
            print(f"⚠ Scraping failed ({e}), using manual data...")
            return self._load_manual_data()
    
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
    
    def _load_manual_data(self) -> Dict:
        """Load manually entered weather data from JSON file."""
        try:
            path = Path("weather_data.json")
            if not path.exists():
                print("❌ No manual weather data found. Run: python3 manual_weather_input.py")
                return {}
            
            with open(path) as f:
                data = json.load(f)
            
            age_str = data.get('timestamp', 'unknown time')
            print(f"✓ Loaded manual weather data from {age_str[:19]}")
            return data
        except Exception as e:
            print(f"❌ Error loading manual data: {e}")
            return {}
    
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
