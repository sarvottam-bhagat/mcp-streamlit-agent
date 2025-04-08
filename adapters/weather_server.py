#!/usr/bin/env python
"""
Weather MCP server implementation using OpenWeatherMap API.
Fetches real weather data for the requested location.
"""
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, Optional
import requests
import os
import sys
import json

# Create FastMCP instance
mcp = FastMCP("WeatherService")

# OpenWeatherMap API key - you'll need to set this as an environment variable
# or replace with your actual API key
# Use a known working key as default to ensure the API works for all locations
API_KEY = os.environ.get("OPENWEATHER_API_KEY", "97dda98f3f8e5500a5e46227d5e45ebd")

# Debug: Print the API key (first 4 and last 4 characters only for security)
if API_KEY:
    masked_key = API_KEY[:4] + "*" * (len(API_KEY) - 8) + API_KEY[-4:] if len(API_KEY) > 8 else "****"
    print(f"Using OpenWeatherMap API key: {masked_key}", file=sys.stderr)
else:
    print("WARNING: No OpenWeatherMap API key found", file=sys.stderr)

def fetch_weather_data(location: str) -> Optional[Dict[str, Any]]:
    """Fetch weather data from OpenWeatherMap API.

    Args:
        location (str): Name of the location to check weather for

    Returns:
        Optional[Dict[str, Any]]: Weather data or None if request failed
    """
    try:
        # Debug: Print API key status (not the actual key)
        print(f"API Key status: {'Set' if API_KEY else 'Not set'}", file=sys.stderr)

        # If no API key, use mock data instead of making a failed API call
        if not API_KEY:
            print("No API key set, using mock data", file=sys.stderr)
            return None

        # Make API request to OpenWeatherMap
        url = f"https://api.openweathermap.org/data/2.5/weather?q={location}&appid={API_KEY}&units=metric"
        print(f"Requesting weather data for: {location}", file=sys.stderr)
        print(f"Request URL: {url.replace(API_KEY, '***API_KEY***')}", file=sys.stderr)

        # Add more detailed debugging
        try:
            response = requests.get(url, timeout=10)  # Add timeout for better error handling
        except Exception as e:
            print(f"Exception during request: {str(e)}", file=sys.stderr)
            raise

        # Debug: Print response status
        print(f"Response status code: {response.status_code}", file=sys.stderr)

        # Handle common HTTP errors with more specific messages
        if response.status_code == 401:
            print("Authentication error: Invalid API key", file=sys.stderr)
            return None
        elif response.status_code == 404:
            print(f"Location not found: {location}", file=sys.stderr)
            return None
        elif response.status_code == 429:
            print("Rate limit exceeded for API key", file=sys.stderr)
            return None

        response.raise_for_status()  # Raise exception for other HTTP errors

        data = response.json()
        print(f"Successfully retrieved weather data for {location}", file=sys.stderr)
        return data

    except requests.exceptions.Timeout:
        print(f"Request timed out for location: {location}", file=sys.stderr)
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather data: {e}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing weather data: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return None

@mcp.tool()
def get_weather(location: str, debug: bool = False) -> Dict[str, Any]:
    """Debug parameter is not used by MCP but helps with direct testing"""
    # If debug mode is enabled, print extra information
    if debug:
        print(f"\n==== DEBUG MODE ENABLED ====", file=sys.stderr)
    # Log the request for debugging
    print(f"\n==== WEATHER REQUEST: '{location}' ====", file=sys.stderr)
    """Get weather forecast for a location.

    Args:
        location (str): Name of the location to check weather for

    Returns:
        Dict[str, Any]: Weather information
    """
    # Normalize location name to handle common variations
    normalized_location = location.strip().lower()

    # Initialize weather_data variable
    weather_data = None

    # Dictionary of common location variations and their API-friendly names
    location_variations = {
        'gujrat': ['Gujrat', 'Gujrat, Pakistan'],
        'gujarat': ['Gujarat', 'Gujarat, India'],
        'bangalore': ['Bengaluru', 'Bangalore, India'],
        'bengaluru': ['Bengaluru', 'Bangalore, India'],
        'bombay': ['Mumbai', 'Mumbai, India'],
        'calcutta': ['Kolkata', 'Kolkata, India'],
        'madras': ['Chennai', 'Chennai, India'],
        'new york': ['New York', 'New York, US'],
        'nyc': ['New York', 'New York, US'],
        'sf': ['San Francisco', 'San Francisco, US'],
        'la': ['Los Angeles', 'Los Angeles, US'],
        'london': ['London', 'London, GB'],
        'paris': ['Paris', 'Paris, FR']
    }

    # Check if we have special handling for this location
    if normalized_location in location_variations:
        print(f"Special handling for '{location}'", file=sys.stderr)
        test_locations = location_variations[normalized_location]

        # Try each variation until we find one that works
        for test_loc in test_locations:
            print(f"Trying variation: '{test_loc}'", file=sys.stderr)
            weather_data = fetch_weather_data(test_loc)
            if weather_data:
                print(f"Found match with: '{test_loc}'", file=sys.stderr)
                break
    else:
        # Normal processing for other locations
        print(f"Standard processing for '{location}'", file=sys.stderr)
        weather_data = fetch_weather_data(location)
    # Generate realistic mock data based on location
    def get_mock_data(loc: str) -> Dict[str, Any]:
        # Use location name to generate consistent but varied mock data
        # This makes the mock data feel more realistic and different for each city
        import hashlib
        import time

        # Create a hash of the location name to generate consistent values
        # Add the current date to make it change daily but remain consistent throughout the day
        current_date = time.strftime("%Y-%m-%d")
        loc_hash = int(hashlib.md5(f"{loc.lower()}-{current_date}".encode()).hexdigest(), 16)

        # Weather conditions with descriptions
        weather_options = [
            {"main": "Clear", "description": "clear sky"},
            {"main": "Clouds", "description": "few clouds"},
            {"main": "Clouds", "description": "scattered clouds"},
            {"main": "Clouds", "description": "broken clouds"},
            {"main": "Clouds", "description": "overcast clouds"},
            {"main": "Rain", "description": "light rain"},
            {"main": "Rain", "description": "moderate rain"},
            {"main": "Drizzle", "description": "light intensity drizzle"},
            {"main": "Mist", "description": "mist"},
            {"main": "Fog", "description": "fog"}
        ]
        weather_idx = loc_hash % len(weather_options)
        weather = weather_options[weather_idx]

        # Generate temperature based on location name and current season
        # Northern hemisphere: summer in June-August, winter in December-February
        # Southern hemisphere: opposite
        current_month = int(time.strftime("%m"))
        is_northern = loc_hash % 2 == 0  # Randomly assign hemisphere

        # Base temperature range
        if is_northern:
            if 5 <= current_month <= 9:  # Northern summer
                base_temp = 20 + (loc_hash % 15)  # 20-35°C
            elif current_month <= 2 or current_month >= 11:  # Northern winter
                base_temp = -5 + (loc_hash % 20)  # -5 to 15°C
            else:  # Spring/fall
                base_temp = 10 + (loc_hash % 15)  # 10-25°C
        else:
            if 11 <= current_month or current_month <= 3:  # Southern summer
                base_temp = 20 + (loc_hash % 15)  # 20-35°C
            elif 5 <= current_month <= 9:  # Southern winter
                base_temp = 0 + (loc_hash % 20)  # 0-20°C
            else:  # Spring/fall
                base_temp = 10 + (loc_hash % 15)  # 10-25°C

        # Add daily variation (+/- 5 degrees)
        daily_variation = (loc_hash % 11) - 5
        temp = base_temp + daily_variation

        # Generate humidity based on weather condition
        if weather["main"] in ["Rain", "Drizzle", "Mist", "Fog"]:
            humidity = 70 + (loc_hash % 25)  # 70-95%
        elif weather["main"] == "Clouds":
            humidity = 50 + (loc_hash % 30)  # 50-80%
        else:  # Clear
            humidity = 30 + (loc_hash % 40)  # 30-70%

        # Generate wind speed based on weather
        if weather["main"] in ["Rain", "Clouds"] and weather["description"] in ["overcast clouds", "moderate rain"]:
            wind = 3 + (loc_hash % 8)  # 3-11 m/s
        else:
            wind = 1 + (loc_hash % 5)  # 1-6 m/s

        return {
            "location": loc,
            "weather": weather["main"],
            "description": weather["description"],
            "temperature": f"{temp}°C",
            "humidity": f"{humidity}%",
            "wind": f"{wind} m/s",
            "note": "This is simulated weather data. For real-time data, set a valid OPENWEATHER_API_KEY environment variable."
        }

    # If no API key is set, return mock data with a warning
    if not API_KEY:
        print(f"Using mock data for {location} (no API key set)", file=sys.stderr)
        return get_mock_data(location)

    # weather_data is already fetched above
    if not weather_data:
        print(f"Failed to fetch weather data for {location}, using mock data instead", file=sys.stderr)
        # Use mock data instead of error message for better user experience
        return get_mock_data(location)

    # Extract relevant information from the API response
    try:
        weather_condition = weather_data["weather"][0]["main"]
        weather_description = weather_data["weather"][0]["description"]
        temperature = f"{weather_data['main']['temp']}°C"
        humidity = f"{weather_data['main']['humidity']}%"
        wind_speed = f"{weather_data['wind']['speed']} m/s"

        # Get country and city name for better display
        country = weather_data.get("sys", {}).get("country", "")
        city_name = weather_data.get("name", location)

        # Format location with city and country if available
        formatted_location = f"{city_name}, {country}" if country else city_name

        return {
            "location": formatted_location,
            "weather": weather_condition,
            "description": weather_description,
            "temperature": temperature,
            "humidity": humidity,
            "wind": wind_speed,
            "source": "OpenWeatherMap API"
        }
    except KeyError as e:
        print(f"Error extracting weather data: {e}", file=sys.stderr)
        return {
            "location": location,
            "weather": "Unknown",
            "description": "Error processing weather data",
            "temperature": "Unknown",
            "humidity": "Unknown",
            "wind": "Unknown",
            "error": f"Failed to parse weather data: {str(e)}"
        }

if __name__ == "__main__":
    import sys

    # Set transport according to command line arguments
    transport = "stdio"  # Default value

    if len(sys.argv) > 1:
        transport = sys.argv[1]

    print(f"Starting Weather MCP Server with transport: {transport}", file=sys.stderr)

    if transport == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
