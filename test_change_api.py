#!/usr/bin/env python3
"""
Test script for the Change Detection API
Run this to verify all endpoints are working correctly
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

def main():
    """Run comprehensive API tests."""
    print("🚀 Starting Change Detection API Tests")

    # Test 1: Health check
    print("\n1. Testing health endpoints...")
    test_endpoint("GET", "/")
    test_endpoint("GET", "/health")

    # Test 2: Location coordinates
    print("\n2. Testing location coordinates...")
    test_endpoint("GET", "/locations/Dubai/coordinates")
    test_endpoint("GET", "/locations/San Francisco/coordinates")

    # Test 3: Change detection (this will take time)
    print("\n3. Testing change detection...")
    change_request = {
        "location": "Dubai",
        "zoom_level": "City-Wide (0.025°)",
        "resolution": "Standard (5m)",
        "alpha": 0.4
    }

    result = test_endpoint("POST", "/detect-change", change_request)

    if result and result.get("success"):
        print("\n4. Saving received images...")
        images = result.get("images", {})

        # Create output directory
        os.makedirs("api_test_images", exist_ok=True)

        # Save all images
        for img_type, base64_data in images.items():
            if base64_data:
                save_base64_image(base64_data, f"api_test_images/dubai_{img_type}.png")

    # Test 4: Individual image endpoints
    print("\n5. Testing individual image endpoints...")
    for img_type in ['before', 'after', 'mask', 'overlay']:
        image_data = test_endpoint(
            "GET",
            f"/detect-change/Dubai/images/{img_type}",
            params={"zoom_level": "City-Wide (0.025°)", "resolution": "Standard (5m)"}
        )

        if image_data:
            # Save the image
            os.makedirs("api_test_images", exist_ok=True)
            with open(f"api_test_images/dubai_{img_type}_direct.png", "wb") as f:
                f.write(image_data)
            print(f"Saved direct image: dubai_{img_type}_direct.png")

    print("\n✅ API tests completed!")
    print("Check the 'api_test_images' folder for downloaded images.")

if __name__ == "__main__":
    main()