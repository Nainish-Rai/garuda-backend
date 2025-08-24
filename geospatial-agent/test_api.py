#!/usr/bin/env python3
"""
Test script for the Geospatial Agent API
Run this to verify all endpoints are working correctly
"""

import requests
import json
import time
from typing import Dict, Any

# API base URL
BASE_URL = "http://localhost:8001"

def test_endpoint(method: str, endpoint: str, data: Dict[Any, Any] = None, params: Dict[str, Any] = None):
    """Test an API endpoint and return the response."""
    url = f"{BASE_URL}{endpoint}"

    try:
        if method.upper() == "GET":
            response = requests.get(url, params=params)
        elif method.upper() == "POST":
            response = requests.post(url, json=data)
        elif method.upper() == "DELETE":
            response = requests.delete(url)
        else:
            raise ValueError(f"Unsupported method: {method}")

        print(f"\n{'='*60}")
        print(f"{method.upper()} {endpoint}")
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)[:500]}...")
            return result
        else:
            print(f"Error: {response.text}")
            return None

    except Exception as e:
        print(f"Request failed: {e}")
        return None

def main():
    """Run comprehensive API tests."""
    print("🚀 Starting Geospatial Agent API Tests")

    # Test 1: Health check
    print("\n1. Testing health endpoints...")
    test_endpoint("GET", "/")
    test_endpoint("GET", "/health")

    # Test 2: System info
    print("\n2. Testing system info...")
    test_endpoint("GET", "/system/info")

    # Test 3: Location search
    print("\n3. Testing location search...")
    test_endpoint("POST", "/locations/search", {
        "query": "Dubai",
        "limit": 5
    })

    # Test 4: Get coordinates
    print("\n4. Testing coordinate lookup...")
    test_endpoint("GET", "/locations/coordinates/Dubai")

    # Test 5: Location info
    print("\n5. Testing location info...")
    test_endpoint("GET", "/locations/info", params={
        "lat": 25.2048,
        "lon": 55.2708
    })

    # Test 6: Preview analysis area
    print("\n6. Testing analysis preview...")
    test_endpoint("POST", "/analyze/preview", {
        "lat": 25.2048,
        "lon": 55.2708,
        "zoom_level": "City-Wide (0.025°)"
    })

    # Test 7: Get available dates
    print("\n7. Testing available dates...")
    test_endpoint("GET", "/locations/dates", params={
        "lat": 25.2048,
        "lon": 55.2708,
        "zoom_level": "City-Wide (0.025°)"
    })

    # Test 8: Analysis history (should be empty initially)
    print("\n8. Testing analysis history...")
    test_endpoint("GET", "/analyze/history")

    # Test 9: Analysis summary
    print("\n9. Testing analysis summary...")
    test_endpoint("GET", "/stats/summary")

    # Test 10: Batch analysis (minimal test)
    print("\n10. Testing batch analysis...")
    batch_response = test_endpoint("POST", "/analyze/batch", {
        "locations": [
            {"name": "Dubai", "lat": 25.2048, "lon": 55.2708},
            {"name": "Abu Dhabi", "lat": 24.4539, "lon": 54.3773}
        ],
        "zoom_level": "City-Wide (0.025°)",
        "resolution": "Standard (5m)"
    })

    if batch_response and "batch_id" in batch_response:
        batch_id = batch_response["batch_id"]
        print(f"\n11. Testing batch status check...")
        time.sleep(2)  # Wait a bit
        test_endpoint("GET", f"/analyze/batch/{batch_id}")

    print("\n✅ API tests completed!")
    print("Note: Full analysis tests are skipped as they require satellite imagery access.")
    print("To test full analysis, ensure your .env file has valid Sentinel Hub credentials.")

if __name__ == "__main__":
    main()