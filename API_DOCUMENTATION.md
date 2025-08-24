# Unified Geospatial Change Detection API Documentation

## Overview

The Unified Geospatial Change Detection API provides comprehensive satellite-based urban change detection capabilities. It combines both simple and advanced analysis endpoints, offering flexibility for different use cases from basic change detection to detailed geospatial analysis with GeoJSON responses.

**Base URL:** `http://localhost:8000`
**API Version:** 2.0.0
**Content-Type:** `application/json`

## Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication](#authentication)
3. [Simple API Endpoints](#simple-api-endpoints)
4. [Advanced API Endpoints](#advanced-api-endpoints)
5. [Utility Endpoints](#utility-endpoints)
6. [Response Formats](#response-formats)
7. [Error Handling](#error-handling)
8. [Examples](#examples)
9. [Rate Limits](#rate-limits)

## Quick Start

```python
import requests

# Simple change detection
response = requests.post("http://localhost:8000/detect-change", json={
    "location": "Dubai",
    "zoom_level": "City-Wide (0.025°)",
    "resolution": "Standard (5m)"
})

# Advanced analysis
response = requests.post("http://localhost:8000/analyze", json={
    "location": {"lat": 25.2048, "lon": 55.2708},
    "zoom_level": "City-Wide (0.025°)"
})
```

## Authentication

Currently, the API does not require authentication. All endpoints are publicly accessible.

---

# Simple API Endpoints

These endpoints provide straightforward change detection functionality with easy-to-use request formats.

## POST /detect-change

Perform change detection analysis using a location name.

### Request Body

```json
{
  "location": "string", // Required: Location name (e.g., "Dubai", "San Francisco")
  "zoom_level": "string", // Optional: "City-Wide (0.025°)" | "Block-Level (0.01°)" | "Zoomed-In (0.005°)"
  "resolution": "string", // Optional: "Coarse (10m)" | "Standard (5m)" | "Fine (2.5m)"
  "alpha": 0.4 // Optional: Overlay transparency (0.0-1.0)
}
```

### Response

```json
{
  "success": true,
  "message": "Change detection completed successfully",
  "coordinates": {
    "latitude": 25.2048,
    "longitude": 55.2708
  },
  "dates": {
    "before": "2019-03-15",
    "after": "2024-08-20"
  },
  "statistics": {
    "changed_pixels": 12543,
    "total_pixels": 262144,
    "change_percentage": 4.78
  },
  "images": {
    "before": "base64_encoded_image_data",
    "after": "base64_encoded_image_data",
    "mask": "base64_encoded_image_data",
    "overlay": "base64_encoded_image_data"
  }
}
```

### Example

```python
import requests

response = requests.post("http://localhost:8000/detect-change", json={
    "location": "Dubai",
    "zoom_level": "City-Wide (0.025°)",
    "resolution": "Standard (5m)",
    "alpha": 0.4
})

if response.status_code == 200:
    result = response.json()
    if result["success"]:
        print(f"Change detected: {result['statistics']['change_percentage']:.2f}%")
```

## GET /detect-change/{location}/images/{image_type}

Download individual images from change detection analysis.

### Parameters

- **location** (path): Location name
- **image_type** (path): Image type (`before` | `after` | `mask` | `overlay`)
- **zoom_level** (query): Optional zoom level
- **resolution** (query): Optional resolution
- **alpha** (query): Optional overlay transparency

### Response

Returns PNG image file directly.

### Example

```python
response = requests.get(
    "http://localhost:8000/detect-change/Dubai/images/overlay",
    params={"zoom_level": "City-Wide (0.025°)", "resolution": "Standard (5m)"}
)

if response.status_code == 200:
    with open("dubai_overlay.png", "wb") as f:
        f.write(response.content)
```

## GET /locations/{location}/coordinates

Get coordinates for a location name.

### Response

```json
{
  "location": "Dubai",
  "latitude": 25.2048,
  "longitude": 55.2708
}
```

---

# Advanced API Endpoints

These endpoints provide detailed geospatial analysis with comprehensive response formats including GeoJSON data.

## POST /analyze

Perform detailed geospatial analysis using coordinates.

### Request Body

```json
{
  "location": {
    // Required: Coordinate object
    "lat": 25.2048,
    "lon": 55.2708
  },
  "time_range": {
    // Optional: Custom date range
    "start": "2020-01-01",
    "end": "2023-12-31"
  },
  "analysis_type": "urban_change", // Optional: Analysis type
  "zoom_level": "City-Wide (0.025°)", // Optional: Zoom level
  "resolution": "Standard (5m)", // Optional: Resolution
  "overlay_alpha": 0.4, // Optional: Overlay transparency
  "include_images": true // Optional: Include base64 images
}
```

### Response

```json
{
  "jobId": "uuid-string",
  "status": "COMPLETE",
  "progress": "Analysis complete",
  "elapsedTime": 30000,
  "data": {
    "type": "change_detection_analysis",
    "intent": {
      "intent": "CHANGE_DETECTION",
      "location": "Lat: 25.2048, Lon: 55.2708",
      "dateRange": ["2019-03-15", "2024-08-20"],
      "confidence": 95,
      "extractedParams": {
        "priceThreshold": null,
        "riskCriteria": true,
        "timeFrame": null
      }
    },
    "data": {
      "changePolygons": {
        "type": "FeatureCollection",
        "features": [
          {
            "type": "Feature",
            "geometry": {
              "type": "Polygon",
              "coordinates": [[[lon1, lat1], [lon2, lat2], ...]]
            },
            "properties": {
              "changeType": "land_use_change",
              "confidence": 0.85,
              "area": 12543,
              "detectionMethod": "satellite_analysis"
            }
          }
        ]
      },
      "statistics": {
        "totalChangeArea": 12543,
        "changePercentage": 4.78,
        "changedPixels": 12543,
        "totalPixels": 262144
      },
      "images": {
        "beforeImage": "data:image/png;base64,iVBORw0KGgoAAAA...",
        "afterImage": "data:image/png;base64,iVBORw0KGgoAAAA...",
        "overlayImage": "data:image/png;base64,iVBORw0KGgoAAAA...",
        "maskImage": "data:image/png;base64,iVBORw0KGgoAAAA..."
      },
      "metadata": {
        "location": "Lat: 25.2048, Lon: 55.2708",
        "dateRange": ["2019-03-15", "2024-08-20"],
        "resolution": "Standard (5m)",
        "algorithm": "U-Net Change Detection",
        "analysisDate": "2025-08-24T10:30:00Z"
      }
    },
    "placeholder": false
  }
}
```

## POST /analyze/location

Perform geospatial analysis using a location name instead of coordinates.

### Request Body

```json
{
  "location_name": "Dubai", // Required: Location name
  "zoom_level": "City-Wide (0.025°)", // Optional: Zoom level
  "resolution": "Standard (5m)", // Optional: Resolution
  "overlay_alpha": 0.4 // Optional: Overlay transparency
}
```

### Response

Same format as `/analyze` endpoint.

## POST /locations/search

Search for locations by name or address.

### Request Body

```json
{
  "query": "San Francisco", // Required: Search query
  "limit": 10 // Optional: Maximum results (default: 10)
}
```

### Response

```json
{
  "status": "success",
  "locations": [
    {
      "name": "San Francisco, California, United States",
      "display_name": "San Francisco, California, United States",
      "coordinates": {
        "lat": 37.7749,
        "lon": -122.4194
      },
      "bbox": [37.7049, 37.8349, -122.5144, -122.3544],
      "place_type": "city",
      "country": "United States"
    }
  ]
}
```

## GET /analyze/history

Get analysis history with pagination.

### Parameters

- **limit** (query): Maximum number of results (default: 50)
- **offset** (query): Number of results to skip (default: 0)

### Response

```json
{
  "status": "success",
  "analyses": [
    {
      "id": "uuid-string",
      "timestamp": "2025-08-24T10:30:00Z",
      "location": { "lat": 25.2048, "lon": 55.2708 },
      "parameters": {
        "zoom_level": "City-Wide (0.025°)",
        "resolution": "Standard (5m)",
        "overlay_alpha": 0.4
      },
      "result": {
        "coordinates": { "lat": 25.2048, "lon": 55.2708 },
        "dates": { "before": "2019-03-15", "after": "2024-08-20" },
        "statistics": {
          "changed_pixels": 12543,
          "total_pixels": 262144,
          "change_percentage": 4.78
        }
      }
    }
  ]
}
```

## GET /analyze/history/{analysis_id}

Get a specific analysis by ID.

### Response

```json
{
  "status": "success",
  "data": {
    "id": "uuid-string",
    "timestamp": "2025-08-24T10:30:00Z",
    "location": {"lat": 25.2048, "lon": 55.2708},
    "parameters": {...},
    "result": {...}
  }
}
```

## DELETE /analyze/history/{analysis_id}

Delete a specific analysis from history.

### Response

```json
{
  "status": "success",
  "message": "Analysis deleted"
}
```

---

# Utility Endpoints

## GET /

Get API information and available endpoints.

### Response

```json
{
  "message": "Unified Geospatial Change Detection API",
  "status": "running",
  "version": "2.0.0",
  "endpoints": {
    "simple_api": {
      "detect_change": "/detect-change",
      "get_image": "/detect-change/{location}/images/{image_type}",
      "get_coordinates": "/locations/{location}/coordinates"
    },
    "advanced_api": {
      "analyze": "/analyze",
      "analyze_by_location": "/analyze/location",
      "batch_analyze": "/analyze/batch",
      "search_locations": "/locations/search",
      "history": "/analyze/history"
    }
  }
}
```

## GET /health

Check API health status.

### Response

```json
{
  "status": "healthy",
  "model_loaded": true,
  "sentinel_hub_configured": true
}
```

## GET /system/info

Get detailed system information.

### Response

```json
{
  "status": "success",
  "system_info": {
    "api_version": "2.0.0",
    "model_loaded": true,
    "available_zoom_levels": [
      "City-Wide (0.025°)",
      "Block-Level (0.01°)",
      "Zoomed-In (0.005°)"
    ],
    "available_resolutions": ["Coarse (10m)", "Standard (5m)", "Fine (2.5m)"],
    "analysis_types": ["urban_change"],
    "max_batch_size": 20,
    "supported_image_formats": ["PNG", "JPEG", "TIFF"],
    "endpoints": {
      "simple_api_count": 3,
      "advanced_api_count": 8,
      "total_endpoints": 11
    }
  }
}
```

## GET /locations/dates

Get available satellite imagery dates for a location.

### Parameters

- **lat** (query): Latitude
- **lon** (query): Longitude
- **zoom_level** (query): Optional zoom level

### Response

```json
{
  "status": "success",
  "available_dates": ["2019-03-15", "2019-05-22", "2020-01-10", "2024-08-20"],
  "total_dates": 4
}
```

## GET /stats/summary

Get analysis summary statistics.

### Response

```json
{
  "status": "success",
  "summary": {
    "total_analyses": 15,
    "average_change_percentage": 3.42,
    "max_change_percentage": 8.91,
    "min_change_percentage": 0.15,
    "recent_analyses": 5
  }
}
```

---

# Response Formats

## Success Response

All successful responses include a status indicator and relevant data:

```json
{
  "success": true,           // For simple API
  "status": "success",       // For advanced API
  "message": "...",          // Human-readable message
  "data": {...}              // Response data
}
```

## Error Response

Error responses follow a consistent format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

## Image Responses

Images are returned in two formats:

1. **Base64 encoded** (in JSON responses): `"iVBORw0KGgoAAAANSUhEUgAA..."`
2. **Direct PNG** (for image endpoints): Binary PNG data with `Content-Type: image/png`

---

# Error Handling

## HTTP Status Codes

- **200**: Success
- **400**: Bad Request (invalid parameters)
- **404**: Not Found (location/resource not found)
- **500**: Internal Server Error (analysis failed)

## Common Error Scenarios

### Location Not Found

```json
{
  "detail": "Location not found"
}
```

### No Satellite Images Available

```json
{
  "detail": "Not enough 0% cloud images found for this location"
}
```

### Analysis Failure

```json
{
  "detail": "Analysis failed: Failed to fetch satellite images"
}
```

---

# Examples

## Complete Change Detection Workflow

```python
import requests
import base64
from PIL import Image
import io

# 1. Check API health
health = requests.get("http://localhost:8000/health")
print(f"API Status: {health.json()['status']}")

# 2. Search for a location
search_response = requests.post("http://localhost:8000/locations/search", json={
    "query": "Tokyo",
    "limit": 1
})
locations = search_response.json()["locations"]
if locations:
    coords = locations[0]["coordinates"]
    print(f"Found: {coords}")

# 3. Perform change detection
analysis_response = requests.post("http://localhost:8000/detect-change", json={
    "location": "Tokyo",
    "zoom_level": "City-Wide (0.025°)",
    "resolution": "Standard (5m)",
    "alpha": 0.5
})

if analysis_response.status_code == 200:
    result = analysis_response.json()
    if result["success"]:
        print(f"Change detected: {result['statistics']['change_percentage']:.2f}%")

        # Save overlay image
        overlay_data = base64.b64decode(result["images"]["overlay"])
        image = Image.open(io.BytesIO(overlay_data))
        image.save("tokyo_changes.png")
        print("Saved tokyo_changes.png")

# 4. Get individual images directly
overlay_response = requests.get(
    "http://localhost:8000/detect-change/Tokyo/images/overlay",
    params={"zoom_level": "City-Wide (0.025°)"}
)

if overlay_response.status_code == 200:
    with open("tokyo_overlay_direct.png", "wb") as f:
        f.write(overlay_response.content)
    print("Saved tokyo_overlay_direct.png")
```

## Advanced Analysis with History

```python
import requests

# Perform advanced analysis
analysis_response = requests.post("http://localhost:8000/analyze", json={
    "location": {"lat": 35.6762, "lon": 139.6503},  # Tokyo coordinates
    "zoom_level": "Block-Level (0.01°)",
    "resolution": "Fine (2.5m)",
    "overlay_alpha": 0.3,
    "include_images": True
})

if analysis_response.status_code == 200:
    result = analysis_response.json()
    job_id = result["jobId"]

    print(f"Analysis completed with ID: {job_id}")
    print(f"Change detected: {result['data']['data']['statistics']['changePercentage']:.2f}%")

    # Get analysis history
    history_response = requests.get("http://localhost:8000/analyze/history?limit=5")
    history = history_response.json()["analyses"]

    print(f"Total analyses in history: {len(history)}")

    # Get statistics summary
    stats_response = requests.get("http://localhost:8000/stats/summary")
    stats = stats_response.json()["summary"]

    print(f"Average change across all analyses: {stats['average_change_percentage']:.2f}%")
```

---

# Rate Limits

Currently, there are no rate limits enforced. However, satellite image processing can be computationally intensive, so:

- Allow 30-60 seconds for analysis completion
- Avoid concurrent requests for the same location
- Consider caching results for repeated queries

---

# Notes

1. **Satellite Data**: Uses Sentinel-2 satellite imagery via Sentinel Hub
2. **Model**: Change detection powered by U-Net deep learning model
3. **Coverage**: Global coverage where Sentinel-2 data is available
4. **Cloud Coverage**: Automatically finds dates with minimal cloud coverage
5. **Image Quality**: Higher resolution settings provide more detail but take longer to process

For support or questions, please refer to the API health endpoint or check the logs when running the service.
