#!/usr/bin/env python3
"""
Test script for the Geospatial Agent API
"""
import requests
import json
import time

# Base URL for the geospatial agent
BASE_URL = "http://localhost:8001"

def test_health_check():
    """Test the health check endpoint"""
    print("Testing health check endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_analyze_with_coordinates():
    """Test analysis with coordinates"""
    print("\nTesting analysis with coordinates (Dubai)...")
    payload = {
        "location": {"lat": 25.2048, "lon": 55.2708},
        "analysis_type": "urban_change",
        "zoom_level": "Block-Level (0.01°)",
        "resolution": "Standard (5m)",
        "overlay_alpha": 0.4
    }

    try:
        response = requests.post(f"{BASE_URL}/analyze", json=payload)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("Analysis successful!")
            print(f"Change percentage: {result['data']['statistics']['change_percentage']}%")
            print(f"Dates analyzed: {result['data']['dates']['before']} to {result['data']['dates']['after']}")
            print(f"Summary: {result['data']['summary']}")
        else:
            print(f"Error: {response.text}")

        return response.status_code == 200
    except Exception as e:
        print(f"Analysis test failed: {e}")
        return False

def test_analyze_with_location_name():
    """Test analysis with location name"""
    print("\nTesting analysis with location name...")
    payload = {
        "location_name": "Dubai, UAE",
        "zoom_level": "City-Wide (0.025°)",
        "resolution": "Coarse (10m)",
        "overlay_alpha": 0.3
    }

    try:
        response = requests.post(f"{BASE_URL}/analyze/location", json=payload)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("Location-based analysis successful!")
            print(f"Coordinates: {result['data']['coordinates']}")
            print(f"Change percentage: {result['data']['statistics']['change_percentage']}%")
        else:
            print(f"Error: {response.text}")

        return response.status_code == 200
    except Exception as e:
        print(f"Location-based analysis test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Starting Geospatial Agent API Tests")
    print("=" * 50)

    tests = [
        test_health_check,
        test_analyze_with_coordinates,
        test_analyze_with_location_name
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
            time.sleep(1)  # Small delay between tests
        except Exception as e:
            print(f"Test failed with exception: {e}")
            results.append(False)

    print("\n" + "=" * 50)
    print("Test Results Summary:")
    print(f"Health Check: {'✅ PASS' if results[0] else '❌ FAIL'}")
    print(f"Coordinate Analysis: {'✅ PASS' if results[1] else '❌ FAIL'}")
    print(f"Location Name Analysis: {'✅ PASS' if results[2] else '❌ FAIL'}")

    total_passed = sum(results)
    print(f"\nTotal: {total_passed}/{len(results)} tests passed")

if __name__ == "__main__":
    main()