#!/usr/bin/env python3
"""
Simple example showing how to use the Change Detection API
"""

import requests
import json
import base64
from PIL import Image
import io

# API Configuration
API_BASE = "http://localhost:8000"

def detect_change_example():
    """Example of using the change detection API"""

    # 1. Check if API is running
    try:
        response = requests.get(f"{API_BASE}/health")
        print(f"API Health: {response.json()}")
    except:
        print("❌ API is not running. Start it with: python api_service.py")
        return

    # 2. Get coordinates for a location
    location = "Dubai"
    response = requests.get(f"{API_BASE}/locations/{location}/coordinates")
    if response.status_code == 200:
        coords = response.json()
        print(f"📍 {location}: {coords['latitude']:.4f}, {coords['longitude']:.4f}")

    # 3. Perform change detection
    request_data = {
        "location": location,
        "zoom_level": "City-Wide (0.025°)",
        "resolution": "Standard (5m)",
        "alpha": 0.4
    }

    print(f"\n🔍 Analyzing changes in {location}...")
    response = requests.post(f"{API_BASE}/detect-change", json=request_data)

    if response.status_code == 200:
        result = response.json()

        if result["success"]:
            print("✅ Analysis completed!")
            print(f"📅 Before: {result['dates']['before']}")
            print(f"📅 After: {result['dates']['after']}")
            print(f"📊 Change: {result['statistics']['change_percentage']:.2f}%")
            print(f"🔴 Changed pixels: {result['statistics']['changed_pixels']:,}")

            # Save the overlay image
            overlay_b64 = result["images"]["overlay"]
            image_data = base64.b64decode(overlay_b64)
            image = Image.open(io.BytesIO(image_data))
            image.save(f"{location}_change_overlay.png")
            print(f"💾 Saved overlay image: {location}_change_overlay.png")

        else:
            print(f"❌ Analysis failed: {result['message']}")
    else:
        print(f"❌ Request failed: {response.text}")

def get_individual_images_example():
    """Example of getting individual images"""
    location = "Dubai"

    for image_type in ['before', 'after', 'overlay']:
        print(f"\n📥 Downloading {image_type} image...")

        response = requests.get(
            f"{API_BASE}/detect-change/{location}/images/{image_type}",
            params={"zoom_level": "City-Wide (0.025°)", "resolution": "Standard (5m)"}
        )

        if response.status_code == 200:
            filename = f"{location}_{image_type}.png"
            with open(filename, "wb") as f:
                f.write(response.content)
            print(f"✅ Saved: {filename}")
        else:
            print(f"❌ Failed to get {image_type} image")

if __name__ == "__main__":
    print("🚀 Change Detection API Example")
    print("=" * 50)

    # Run the main example
    detect_change_example()

    # Uncomment to test individual image downloads
    # get_individual_images_example()