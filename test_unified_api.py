#!/usr/bin/env python3
"""
Test script for the Unified Change Detection API
This script tests both simple and advanced API endpoints
"""

import requests
import json
import base64
from PIL import Image
import io
import os

# API base URL
BASE_URL = "http://localhost:8000"

def test_endpoint(method: str, endpoint: str, data: dict = None, params: dict = None):
    """Test an API endpoint and return the response."""
    url = f"{BASE_URL}{endpoint}"

    try:
        if method.upper() == "GET":
            response = requests.get(url, params=params)
        elif method.upper() == "POST":
            response = requests.post(url, json=data)
        else:
            raise ValueError(f"Unsupported method: {method}")

        print(f"\n{'='*60}")
        print(f"{method.upper()} {endpoint}")
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            if 'image' in response.headers.get('content-type', ''):
                print(f"Response: Image received ({len(response.content)} bytes)")
                return response.content
            else:
                result = response.json()
                print(f"Response: {json.dumps(result, indent=2)[:500]}...")
                return result
        else:
            print(f"Error: {response.text}")
            return None

    except Exception as e:
        print(f"Request failed: {e}")
        return None

def save_base64_image(base64_string: str, filename: str):
    """Save a base64 encoded image to file"""
    try:
        image_data = base64.b64decode(base64_string)
        image = Image.open(io.BytesIO(image_data))
        image.save(filename)
        print(f"Saved image: {filename}")
    except Exception as e:
        print(f"Failed to save image {filename}: {e}")

def test_simple_api():
    """Test the simple API endpoints (from original api_service.py)"""
    print("\n🔍 TESTING SIMPLE API ENDPOINTS")
    print("=" * 60)

    # Test simple change detection
    print("\n1. Testing simple change detection...")
    simple_request = {
        "location": "Dubai",
        "zoom_level": "City-Wide (0.025°)",
        "resolution": "Standard (5m)",
        "alpha": 0.4
    }

    result = test_endpoint("POST", "/detect-change", simple_request)

    if result and result.get("success"):
        print("\n✅ Simple API working!")

        # Save images from simple API
        os.makedirs("unified_test_images", exist_ok=True)
        images = result.get("images", {})

        for img_type, base64_data in images.items():
            if base64_data:
                save_base64_image(base64_data, f"unified_test_images/simple_{img_type}.png")

    # Test individual image endpoints
    print("\n2. Testing individual image downloads...")
    for img_type in ['before', 'after', 'overlay']:
        image_data = test_endpoint(
            "GET",
            f"/detect-change/Dubai/images/{img_type}",
            params={"zoom_level": "City-Wide (0.025°)", "resolution": "Standard (5m)"}
        )

        if image_data:
            os.makedirs("unified_test_images", exist_ok=True)
            with open(f"unified_test_images/simple_direct_{img_type}.png", "wb") as f:
                f.write(image_data)
            print(f"Saved: simple_direct_{img_type}.png")

def test_advanced_api():
    """Test the advanced API endpoints (from geospatial agent)"""
    print("\n🏗️ TESTING ADVANCED API ENDPOINTS")
    print("=" * 60)

    # Test location search
    print("\n1. Testing location search...")
    search_request = {
        "query": "San Francisco",
        "limit": 3
    }
    test_endpoint("POST", "/locations/search", search_request)

    # Test coordinate-based analysis (advanced format)
    print("\n2. Testing advanced analysis with coordinates...")
    advanced_request = {
        "location": {"lat": 25.2048, "lon": 55.2708},  # Dubai coordinates
        "zoom_level": "City-Wide (0.025°)",
        "resolution": "Standard (5m)",
        "overlay_alpha": 0.4,
        "include_images": True
    }

    result = test_endpoint("POST", "/analyze", advanced_request)

    if result and result.get("status") == "COMPLETE":
        print("\n✅ Advanced API working!")

        # Save analysis ID for later tests
        analysis_id = result.get("jobId")
        if analysis_id:
            print(f"Analysis ID: {analysis_id}")

            # Test getting analysis by ID
            print("\n3. Testing analysis retrieval by ID...")
            test_endpoint("GET", f"/analyze/history/{analysis_id}")

    # Test location-based analysis (uses location name)
    print("\n4. Testing location-based analysis...")
    location_request = {
        "location_name": "Tokyo",
        "zoom_level": "Block-Level (0.01°)",
        "resolution": "Fine (2.5m)"
    }
    test_endpoint("POST", "/analyze/location", location_request)

def test_utility_endpoints():
    """Test utility and information endpoints"""
    print("\n🔧 TESTING UTILITY ENDPOINTS")
    print("=" * 60)

    # Test system info
    print("\n1. Testing system information...")
    test_endpoint("GET", "/system/info")

    # Test analysis history
    print("\n2. Testing analysis history...")
    test_endpoint("GET", "/analyze/history", params={"limit": 5})

    # Test available dates
    print("\n3. Testing available dates...")
    test_endpoint("GET", "/locations/dates", params={
        "lat": 25.2048,
        "lon": 55.2708,
        "zoom_level": "City-Wide (0.025°)"
    })

    # Test analysis summary
    print("\n4. Testing analysis summary...")
    test_endpoint("GET", "/stats/summary")

def main():
    """Run comprehensive tests for the unified API."""
    print("🚀 Starting Unified Change Detection API Tests")
    print("Testing both Simple API and Advanced API endpoints on port 8000")

    # Test basic endpoints first
    print("\n0. Testing basic endpoints...")
    test_endpoint("GET", "/")
    test_endpoint("GET", "/health")
    test_endpoint("GET", "/locations/Dubai/coordinates")

    # Test simple API (original api_service.py functionality)
    test_simple_api()

    # Test advanced API (geospatial agent functionality)
    test_advanced_api()

    # Test utility endpoints
    test_utility_endpoints()

    print("\n✅ Unified API tests completed!")
    print("Check the 'unified_test_images' folder for downloaded images.")
    print("\nThe unified API provides:")
    print("  📍 Simple API: Easy location-based change detection")
    print("  🏗️ Advanced API: Detailed geospatial analysis with GeoJSON")
    print("  🔧 Utility APIs: History, search, statistics, and more")

if __name__ == "__main__":
    main()