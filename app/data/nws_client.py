"""
NWS API client for station observations.
"""

from datetime import datetime
from typing import Dict, Optional

import requests


class NWSClient:
    """Fetch observations from api.weather.gov."""

    def __init__(self, user_agent: str, timeout: int = 10):
        self.user_agent = user_agent
        self.timeout = timeout
        self.base_url = "https://api.weather.gov"

    @staticmethod
    def _c_to_f(value_c: Optional[float]) -> Optional[int]:
        if value_c is None:
            return None
        try:
            return int(round((value_c * 9 / 5) + 32))
        except (TypeError, ValueError):
            return None

    def get_latest_observation(self, station_id: str) -> Dict:
        """Return normalized observation fields for a station."""
        if not station_id:
            return {}

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/geo+json",
        }
        url = f"{self.base_url}/stations/{station_id}/observations/latest"
        resp = requests.get(url, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        payload = resp.json()
        props = payload.get("properties") or {}

        data = {
            "timestamp": datetime.now().isoformat(),
            "source": "nws_api",
            "station_id": station_id,
        }

        data["current_temp"] = self._c_to_f((props.get("temperature") or {}).get("value"))
        data["observation_time"] = props.get("timestamp")

        max_24 = (props.get("maxTemperatureLast24Hours") or {}).get("value")
        min_24 = (props.get("minTemperatureLast24Hours") or {}).get("value")
        data["high_today"] = self._c_to_f(max_24)
        data["low_today"] = self._c_to_f(min_24)

        return data
