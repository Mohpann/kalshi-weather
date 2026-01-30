"""
NWS API client for station observations.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
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

    def get_forecast_high(self, lat: float, lon: float) -> Dict:
        """Return today's forecast high from the NWS point forecast."""
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/geo+json",
        }
        points_url = f"{self.base_url}/points/{lat},{lon}"
        points_resp = requests.get(points_url, headers=headers, timeout=self.timeout)
        points_resp.raise_for_status()
        forecast_url = (points_resp.json().get("properties") or {}).get("forecast")
        if not forecast_url:
            return {}

        forecast_resp = requests.get(forecast_url, headers=headers, timeout=self.timeout)
        forecast_resp.raise_for_status()
        periods = (forecast_resp.json().get("properties") or {}).get("periods") or []
        if not periods:
            return {}

        local_tz = ZoneInfo("America/New_York")
        now_local = datetime.now(local_tz)
        today_date = now_local.date()
        chosen = None
        max_temp = None
        next_daytime = None
        for period in periods:
            if not isinstance(period, dict):
                continue
            start = period.get("startTime")
            is_day = period.get("isDaytime")
            if not start or is_day is not True:
                continue
            try:
                start_dt = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(local_tz)
                start_date = start_dt.date()
            except ValueError:
                continue
            if start_date == today_date:
                temp = period.get("temperature")
                if isinstance(temp, (int, float)) and (max_temp is None or temp > max_temp):
                    max_temp = temp
                    chosen = period
                continue
            if start_dt >= now_local and next_daytime is None:
                next_daytime = period

        if not chosen:
            chosen = next_daytime
        if not chosen:
            for period in periods:
                if isinstance(period, dict) and period.get("isDaytime") is True:
                    chosen = period
                    break
        if not chosen:
            return {}
        if not chosen:
            return {}

        temp = chosen.get("temperature")
        return {
            "forecast_high": temp if isinstance(temp, (int, float)) else None,
            "forecast_period": chosen.get("name"),
            "forecast_updated": chosen.get("startTime"),
            "forecast_source": "nws_forecast",
        }
