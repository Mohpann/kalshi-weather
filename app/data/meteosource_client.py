"""
Meteosource API client (current + daily).
"""

from datetime import datetime
from typing import Dict, Optional

import requests


class MeteosourceClient:
    """Fetch current and daily data from Meteosource."""

    def __init__(self, api_key: str, timeout: int = 10, base_url: Optional[str] = None):
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = base_url or "https://www.meteosource.com/api/v1/free/point"

    @staticmethod
    def _first_daily(daily):
        if isinstance(daily, list) and daily:
            return daily[0]
        if isinstance(daily, dict):
            if isinstance(daily.get("data"), list) and daily["data"]:
                return daily["data"][0]
            if isinstance(daily.get("days"), list) and daily["days"]:
                return daily["days"][0]
        return None

    @staticmethod
    def _extract_high_low(day: Dict) -> Dict:
        if not isinstance(day, dict):
            return {}

        def _find(container, keys):
            if not isinstance(container, dict):
                return None
            for key in keys:
                if key in container:
                    return container.get(key)
            return None

        high = None
        low = None
        for container in (day, day.get("all_day"), day.get("day")):
            high = _find(container, ("temperature_max", "temp_max", "temperature_high")) or high
            low = _find(container, ("temperature_min", "temp_min", "temperature_low")) or low
            temp_obj = container.get("temperature") if isinstance(container, dict) else None
            if isinstance(temp_obj, dict):
                high = _find(temp_obj, ("max", "high")) or high
                low = _find(temp_obj, ("min", "low")) or low

        return {"high_today": high, "low_today": low}

    def get_point(self, lat: float, lon: float, sections: str = "current,daily", timezone: str = "auto", units: str = "us") -> Dict:
        if not self.api_key:
            return {}
        params = {
            "lat": lat,
            "lon": lon,
            "sections": sections,
            "timezone": timezone,
            "units": units,
            "key": self.api_key,
        }
        try:
            resp = requests.get(self.base_url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if e.response is not None:
                body = e.response.text[:500]
                raise RuntimeError(
                    f"Meteosource error {e.response.status_code}: {body}"
                ) from e
            raise

    def get_miami_data(self, lat: float, lon: float) -> Dict:
        payload = self.get_point(lat, lon)
        if not payload:
            return {}

        data = {
            "timestamp": datetime.now().isoformat(),
            "source": "meteosource_api",
        }

        current = payload.get("current") or {}
        if isinstance(current, dict):
            data["current_temp"] = current.get("temperature")
            data["observation_time"] = current.get("observation_time") or current.get("timestamp")

        daily = self._first_daily(payload.get("daily"))
        data.update(self._extract_high_low(daily or {}))

        return data
