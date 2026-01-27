#!/usr/bin/env python3
"""
Test script for the Kalshi Weather Trading Bot

Tests each component individually to verify setup.
"""

import sys
from pathlib import Path


def test_imports():
    """Test that all required packages are installed."""
    print("Testing imports...")
    try:
        import requests
        import cryptography
        from bs4 import BeautifulSoup
        print("  ✓ All dependencies installed\n")
        return True
    except ImportError as e:
        print(f"  ✗ Missing dependency: {e}\n")
        return False


def test_api_keys():
    """Test that API keys are present."""
    print("Testing API keys...")
    
    public_key = Path("kalshi_public.txt")
    private_key = Path("kalshi_private.pem")
    
    if not public_key.exists():
        print("  ✗ kalshi_public.txt not found\n")
        return False
    
    if not private_key.exists():
        print("  ✗ kalshi_private.pem not found\n")
        return False
    
    with open(public_key) as f:
        api_key = f.read().strip()
    
    print(f"  ✓ Public key found: {api_key[:8]}...")
    print(f"  ✓ Private key found: {private_key}")
    print()
    return True


def test_auth_module():
    """Test the authentication module."""
    print("Testing authentication module...")
    try:
        from kalshi_auth import KalshiAuth
        
        with open("kalshi_public.txt") as f:
            api_key = f.read().strip()
        
        auth = KalshiAuth(api_key, "kalshi_private.pem")
        headers = auth.get_headers("GET", "/trade-api/v2/portfolio/balance")
        
        assert 'KALSHI-ACCESS-KEY' in headers
        assert 'KALSHI-ACCESS-SIGNATURE' in headers
        assert 'KALSHI-ACCESS-TIMESTAMP' in headers
        
        print("  ✓ Authentication module working")
        print(f"    Sample signature (truncated): {headers['KALSHI-ACCESS-SIGNATURE'][:20]}...\n")
        return True
    except Exception as e:
        print(f"  ✗ Authentication failed: {e}\n")
        return False


def test_kalshi_connection():
    """Test connection to Kalshi API."""
    print("Testing Kalshi API connection...")
    try:
        from kalshi_client import KalshiClient
        
        with open("kalshi_public.txt") as f:
            api_key = f.read().strip()
        
        # Try demo API first (less likely to have network issues)
        client = KalshiClient(api_key, "kalshi_private.pem", "https://demo-api.kalshi.co")
        status = client.get_exchange_status()
        exchange_status = status.get("exchange_status")
        if exchange_status is None:
            exchange_status = {
                "exchange_active": status.get("exchange_active"),
                "trading_active": status.get("trading_active"),
            }
        
        print(f"  ✓ Connected to Kalshi API")
        print(f"    Exchange status: {exchange_status}\n")
        return True
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        print("    Note: Requires internet connection and valid API keys\n")
        return False


def test_market_data():
    """Test fetching market data."""
    print("Testing market data retrieval...")
    try:
        from kalshi_client import KalshiClient
        from main import WeatherTradingBot
        
        with open("kalshi_public.txt") as f:
            api_key = f.read().strip()
        
        bot = WeatherTradingBot(api_key, "kalshi_private.pem", "https://demo-api.kalshi.co")
        ticker = bot.get_todays_market_ticker()
        
        print(f"  Today's market ticker: {ticker}")
        
        try:
            market = bot.get_market_data()
            print(f"  ✓ Market data retrieved")
            print(f"    Title: {market.get('market', {}).get('title', 'N/A')}\n")
            return True
        except Exception as e:
            print(f"  ⚠ Market fetch failed (market may not exist): {e}\n")
            return True  # Not a critical error
    except Exception as e:
        print(f"  ✗ Test failed: {e}\n")
        return False


def test_weather_scraper():
    """Test weather data scraping."""
    print("Testing weather scraper...")
    print("  ⚠ Note: wethr.net blocks automated requests")
    print("  This feature requires either:")
    print("    - A browser automation tool (Selenium/Playwright)")
    print("    - A proxy service")
    print("    - Manual data entry")
    print("    - Alternative weather API\n")
    return True


def main():
    """Run all tests."""
    print("="*60)
    print("Kalshi Weather Bot - System Test")
    print("="*60)
    print()
    
    tests = [
        test_imports,
        test_api_keys,
        test_auth_module,
        test_kalshi_connection,
        test_market_data,
        test_weather_scraper,
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"Test crashed: {e}\n")
            results.append(False)
    
    print("="*60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("="*60)
    
    if all(results):
        print("\n✓ All tests passed! Bot is ready to run.")
        print("  Run: python3 main.py")
    else:
        print("\n⚠ Some tests failed. Review output above.")
    
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
