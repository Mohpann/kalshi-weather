"""
Alternative Weather Data Input

Since wethr.net blocks automated requests, this module provides
a simple way to manually input weather observations for trading.

You can run this script to update weather data, which the main bot will read.
"""

import json
from datetime import datetime
from pathlib import Path


def get_manual_weather_data():
    """Prompt user for manual weather data entry."""
    print("\n=== Manual Weather Data Entry ===")
    print("Visit: https://wethr.net/market/miami")
    print("Enter the current observations:\n")
    
    data = {
        'timestamp': datetime.now().isoformat(),
        'source': 'manual_entry'
    }
    
    try:
        data['current_temp'] = int(input("Current Temperature (°F): "))
        data['high_today'] = int(input("Today's High (°F): "))
        data['high_time'] = input("Time of High (e.g., '2:21 PM'): ")
        data['low_today'] = int(input("Today's Low (°F): "))
        data['low_time'] = input("Time of Low (e.g., '9:10 PM'): ")
        data['observation_time'] = input("Last Observation Time (e.g., '9:10 PM'): ")
        
        return data
    except (ValueError, KeyboardInterrupt) as e:
        print(f"\nInput cancelled or invalid: {e}")
        return None


def save_weather_data(data, filename="weather_data.json"):
    """Save weather data to JSON file."""
    path = Path(filename)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\n✓ Weather data saved to {filename}")


def load_weather_data(filename="weather_data.json"):
    """Load weather data from JSON file."""
    path = Path(filename)
    if not path.exists():
        return None
    
    with open(path) as f:
        return json.load(f)


def print_weather_data(data):
    """Display weather data."""
    if not data:
        print("No data available")
        return
    
    print("\n=== Current Weather Data ===")
    print(f"Timestamp: {data.get('timestamp', 'N/A')}")
    print(f"Source: {data.get('source', 'N/A')}")
    print(f"Current Temp: {data.get('current_temp', 'N/A')}°F")
    print(f"Today's High: {data.get('high_today', 'N/A')}°F at {data.get('high_time', 'N/A')}")
    print(f"Today's Low: {data.get('low_today', 'N/A')}°F at {data.get('low_time', 'N/A')}")
    print(f"Last Observation: {data.get('observation_time', 'N/A')}")
    print("=" * 30)


def main():
    """Main entry point for manual data entry."""
    print("Kalshi Weather Bot - Manual Weather Data Entry")
    print("=" * 50)
    
    # Show existing data if any
    existing = load_weather_data()
    if existing:
        print("\nCurrent data on file:")
        print_weather_data(existing)
    
    # Prompt for new data
    print("\nWould you like to update the weather data?")
    choice = input("(y/n): ").lower()
    
    if choice == 'y':
        data = get_manual_weather_data()
        if data:
            save_weather_data(data)
            print_weather_data(data)
            print("\n✓ The main bot will use this data in its next update")
    else:
        print("No changes made")


if __name__ == "__main__":
    main()
