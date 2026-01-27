"""
Pure opportunity logic for market condition parsing and heuristic probabilities.
"""

from typing import Dict, Optional, List
import re


def parse_market_condition(title: str) -> Optional[Dict]:
    """Best-effort parse of market title to infer temperature condition."""
    if not title:
        return None
    temps: List[int] = [int(t) for t in re.findall(r"(-?\d+)\s*°?\s*F", title, re.I)]
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


def estimate_prob_reach_threshold(diff: int, hour: int) -> float:
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


def estimate_prob_no_new_high(hour: int) -> float:
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


def estimate_prob_yes(condition: Dict, high_today: int, hour: int) -> Optional[float]:
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
        return estimate_prob_reach_threshold(diff, hour)
    if ctype == "lte":
        threshold = condition.get("threshold")
        if threshold is None:
            return None
        if high_today > threshold:
            return 0.01
        if high_today == threshold:
            return estimate_prob_no_new_high(hour)
        diff = threshold - high_today
        return max(0.01, 1 - estimate_prob_reach_threshold(diff, hour))
    if ctype == "range":
        low = condition.get("low")
        high = condition.get("high")
        if low is None or high is None:
            return None
        if high_today > high:
            return 0.01
        if high_today < low:
            diff = low - high_today
            prob_reach_low = estimate_prob_reach_threshold(diff, hour)
            prob_not_exceed_high = estimate_prob_no_new_high(hour)
            return max(0.01, min(0.99, prob_reach_low * prob_not_exceed_high))
        prob_not_exceed_high = estimate_prob_no_new_high(hour)
        return max(0.01, min(0.99, prob_not_exceed_high))
    return None
