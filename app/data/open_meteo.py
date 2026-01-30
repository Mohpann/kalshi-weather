"""
Open-Meteo client for simple forecast cross-checks.
"""

from datetime import datetime
from typing import Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

import requests


class OpenMeteoClient:
    """Fetch hourly temperature forecasts from Open-Meteo models."""

    def __init__(self, timeout: int = 10, max_workers: int = 2):
        self.timeout = timeout
        self.max_workers = max_workers

    def _fetch_hourly(self, model: str, lat: float, lon: float, days: int = 2) -> Optional[Dict]:
        url = f"https://api.open-meteo.com/v1/{model}"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m",
            "forecast_days": days,
            "temperature_unit": "fahrenheit",
            "timezone": "auto",
        }
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return None

    @staticmethod
    def _daily_high_from_hourly(hourly: Dict, target_date: datetime.date) -> Optional[float]:
        times = hourly.get("time") or []
        temps = hourly.get("temperature_2m") or []
        if not times or not temps or len(times) != len(temps):
            return None
        max_temp = None
        for ts, temp in zip(times, temps):
            try:
                dt = datetime.fromisoformat(ts)
            except ValueError:
                continue
            if dt.date() != target_date:
                continue
            try:
                temp_val = float(temp)
            except (TypeError, ValueError):
                continue
            if max_temp is None or temp_val > max_temp:
                max_temp = temp_val
        return max_temp

    def get_daily_highs(
        self, lat: float, lon: float, target_date: Optional[datetime.date] = None
    ) -> Tuple[Optional[float], Optional[float]]:
        """Return (gfs_high, ecmwf_high) for target_date."""
        if target_date is None:
            target_date = datetime.now().date()
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            gfs_future = executor.submit(self._fetch_hourly, "gfs", lat, lon)
            ecmwf_future = executor.submit(self._fetch_hourly, "ecmwf", lat, lon)
            gfs = gfs_future.result()
            ecmwf = ecmwf_future.result()
        gfs_high = self._daily_high_from_hourly(gfs.get("hourly", {}) if gfs else {}, target_date)
        ecmwf_high = self._daily_high_from_hourly(ecmwf.get("hourly", {}) if ecmwf else {}, target_date)
        return gfs_high, ecmwf_high
