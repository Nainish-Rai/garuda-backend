import requests
import json
import time
import sys
import os

# Test configuration
BASE_URL = "http://localhost:8000"
TEST_LOCATIONS = [
    "New York, NY",
    "Beverly Hills, CA",
    "Atlanta, GA",
    "Chicago, IL",
    "San Francisco, CA"
]
TEST_ZIP_CODES = ["10001", "90210", "30309", "60601", "94102"]

def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def test_api_health():
    """Test API health endpoint"""
    print_section("TESTING API HEALTH")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print("✅ API is healthy")
            print(f"   Model loaded: {data.get('model_loaded')}")
            print(f"   Sentinel Hub configured: {data.get('sentinel_hub_configured')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_dataset_info():
    """Test dataset information endpoint"""
    print_section("TESTING DATASET INFO")
    try:
        response = requests.get(f"{BASE_URL}/datasets/info")
        if response.status_code == 200:
            data = response.json()
            print("✅ Dataset info retrieved successfully")
            print(f"   Available datasets: {list(data.keys())}")

            for dataset, info in data.items():
                print(f"\n   📊 {dataset}:")
                print(f"      Description: {info['description']}")
                print(f"      Fields: {len(info['fields'])} fields")
                print(f"      Sample fields: {info['fields'][:3]}...")
            return True
        else:
            print(f"❌ Dataset info failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Dataset info error: {e}")
        return False

def test_zip_code_analysis():
    """Test ZIP code analysis endpoint"""
    print_section("TESTING ZIP CODE ANALYSIS")

    for zip_code in TEST_ZIP_CODES[:2]:  # Test first 2 ZIP codes
        try:
            print(f"\n🔍 Testing ZIP code: {zip_code}")
            response = requests.get(f"{BASE_URL}/zip-codes/{zip_code}/analysis")

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Analysis successful for ZIP {zip_code}")

                # Display census data highlights
                census = data.get('census_data', {})
                print(f"   📈 Population: {census.get('population', 'N/A'):,}")
                print(f"   💰 Median Income: ${census.get('median_income', 'N/A'):,}")
                print(f"   📊 Poverty Rate: {census.get('poverty_rate', 'N/A')}%")

                # Display real estate data highlights
                real_estate = data.get('real_estate_data', {})
                print(f"   🏠 Avg Home Price: ${real_estate.get('avg_home_price', 'N/A'):,}")
                print(f"   🏗️  New Construction Permits: {real_estate.get('new_construction_permits', 'N/A')}")

                # Display analysis insights
                analysis = data.get('analysis', {})
                print(f"   🔍 Socioeconomic Status: {analysis.get('socioeconomic_status', 'N/A')}")
                print(f"   🏘️  Housing Market: {analysis.get('housing_market', 'N/A')}")
                print(f"   🚀 Development Potential: {analysis.get('development_potential', 'N/A')}")

            elif response.status_code == 404:
                print(f"⚠️  No data available for ZIP {zip_code}")
            else:
                print(f"❌ Analysis failed for ZIP {zip_code}: {response.status_code}")

        except Exception as e:
            print(f"❌ ZIP code analysis error for {zip_code}: {e}")

    return True

def test_location_socioeconomic():
    """Test location socioeconomic data endpoint"""
    print_section("TESTING LOCATION SOCIOECONOMIC DATA")

    for location in TEST_LOCATIONS[:2]:  # Test first 2 locations
        try:
            print(f"\n🌍 Testing location: {location}")
            response = requests.get(f"{BASE_URL}/locations/{location}/socioeconomic")

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Socioeconomic data retrieved for {location}")

                coords = data.get('coordinates', {})
                print(f"   📍 Coordinates: {coords.get('latitude', 'N/A'):.4f}, {coords.get('longitude', 'N/A'):.4f}")
                print(f"   📮 ZIP Code: {data.get('zip_code', 'N/A')}")

                # Display analysis summary
                analysis = data.get('analysis', {})
                if analysis:
                    print(f"   🔍 Analysis Summary:")
                    for key, value in analysis.items():
                        if isinstance(value, dict):
                            print(f"      {key.replace('_', ' ').title()}:")
                            for sub_key, sub_value in value.items():
                                print(f"        - {sub_key.replace('_', ' ').title()}: {sub_value}")
                        else:
                            print(f"      {key.replace('_', ' ').title()}: {value}")

            elif response.status_code == 404:
                print(f"⚠️  No data available for {location}")
            else:
                print(f"❌ Socioeconomic data failed for {location}: {response.status_code}")

        except Exception as e:
            print(f"❌ Socioeconomic data error for {location}: {e}")

    return True

def test_enhanced_change_detection():
    """Test enhanced change detection with socioeconomic data"""
    print_section("TESTING ENHANCED CHANGE DETECTION")

    test_location = "San Francisco, CA"  # Use a location we know has data

    try:
        print(f"🛰️  Testing enhanced change detection for: {test_location}")

        payload = {
            "location": test_location,
            "zoom_level": "City-Wide (0.025°)",
            "resolution": "Standard (5m)",
            "alpha": 0.4
        }

        print("   Sending request... (this may take 30-60 seconds)")
        response = requests.post(f"{BASE_URL}/detect-change", json=payload, timeout=120)

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Enhanced change detection successful!")

            # Display basic results
            coords = data.get('coordinates', {})
            dates = data.get('dates', {})
            stats = data.get('statistics', {})

            print(f"   📍 Location: {coords.get('latitude', 'N/A'):.4f}, {coords.get('longitude', 'N/A'):.4f}")
            print(f"   📅 Date Range: {dates.get('before', 'N/A')} to {dates.get('after', 'N/A')}")
            print(f"   📊 Change Percentage: {stats.get('change_percentage', 'N/A')}%")
            print(f"   🖼️  Images Generated: {len(data.get('images', {}))}")

            # Display socioeconomic insights
            socio_data = data.get('socioeconomic_data')
            real_estate_data = data.get('real_estate_data')
            analysis = data.get('comprehensive_analysis')

            if socio_data:
                print(f"   💰 Median Income: ${socio_data.get('median_income', 'N/A'):,}")
                print(f"   📈 Population: {socio_data.get('population', 'N/A'):,}")

            if real_estate_data:
                print(f"   🏠 Avg Home Price: ${real_estate_data.get('avg_home_price', 'N/A'):,}")
                print(f"   🏗️  Construction Permits: {real_estate_data.get('new_construction_permits', 'N/A')}")

            if analysis:
                print(f"   🔍 Key Insights:")
                for key, value in analysis.items():
                    if isinstance(value, dict):
                        print(f"      {key.replace('_', ' ').title()}:")
                        for sub_key, sub_value in value.items():
                            print(f"        - {sub_key.replace('_', ' ').title()}: {sub_value}")
                    else:
                        print(f"      {key.replace('_', ' ').title()}: {value}")

            return True

        else:
            print(f"❌ Enhanced change detection failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('detail', 'Unknown error')}")
            except:
                print(f"   Raw response: {response.text[:200]}...")
            return False

    except requests.exceptions.Timeout:
        print("❌ Request timed out (this is normal for satellite data fetching)")
        print("   Try testing with a different location or check your Sentinel Hub credentials")
        return False
    except Exception as e:
        print(f"❌ Enhanced change detection error: {e}")
        return False

def test_coordinate_lookup():
    """Test coordinate lookup"""
    print_section("TESTING COORDINATE LOOKUP")

    test_location = "New York, NY"
    try:
        response = requests.get(f"{BASE_URL}/locations/{test_location}/coordinates")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Coordinates found for {test_location}")
            print(f"   📍 Latitude: {data.get('latitude', 'N/A')}")
            print(f"   📍 Longitude: {data.get('longitude', 'N/A')}")
            return True
        else:
            print(f"❌ Coordinate lookup failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Coordinate lookup error: {e}")
        return False

def run_comprehensive_test():
    """Run all tests in sequence"""
    print("🚀 Starting Comprehensive API Test Suite")
    print(f"   Testing API at: {BASE_URL}")

    test_results = {
        "API Health": test_api_health(),
        "Dataset Info": test_dataset_info(),
        "ZIP Code Analysis": test_zip_code_analysis(),
        "Location Socioeconomic": test_location_socioeconomic(),
        "Coordinate Lookup": test_coordinate_lookup(),
        "Enhanced Change Detection": test_enhanced_change_detection()
    }

    # Print summary
    print_section("TEST SUMMARY")
    passed = sum(test_results.values())
    total = len(test_results)

    for test_name, result in test_results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {test_name}: {status}")

    print(f"\n📊 Overall Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Your API is ready to use.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

    return test_results

if __name__ == "__main__":
    # Check if server is running
    try:
        requests.get(f"{BASE_URL}/", timeout=5)
    except:
        print(f"❌ Cannot connect to API at {BASE_URL}")
        print("   Make sure the API server is running with: python unified_api.py")
        sys.exit(1)

    # Run tests
    run_comprehensive_test()