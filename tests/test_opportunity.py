from app.domain.opportunity import (
    parse_market_condition,
    estimate_prob_reach_threshold,
    estimate_prob_no_new_high,
    estimate_prob_yes,
)


def test_parse_market_condition_range():
    cond = parse_market_condition("Will the high be between 72°F and 73°F?")
    assert cond == {"type": "range", "low": 72, "high": 73}


def test_parse_market_condition_gte():
    cond = parse_market_condition("Will the high be at least 75°F?")
    assert cond == {"type": "gte", "threshold": 75}


def test_parse_market_condition_lte():
    cond = parse_market_condition("Will the high be at most 65°F?")
    assert cond == {"type": "lte", "threshold": 65}


def test_estimate_prob_reach_threshold_bounds():
    assert 0.05 <= estimate_prob_reach_threshold(10, 9) <= 0.95
    assert estimate_prob_reach_threshold(-1, 12) == 0.95


def test_estimate_prob_no_new_high_monotonic():
    assert estimate_prob_no_new_high(10) < estimate_prob_no_new_high(22)


def test_estimate_prob_yes_gte():
    cond = {"type": "gte", "threshold": 75}
    prob = estimate_prob_yes(cond, high_today=74, hour=12)
    assert prob is not None
    assert 0.05 <= prob <= 0.95
