from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uvicorn
import io
import base64
from datetime import datetime
import numpy as np
from PIL import Image
import cv2
import uuid
import os
import sys

# Import the functions from your existing app.py
from geopy.geocoders import Nominatim
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import img_to_array
from sentinelhub import (
    SHConfig, BBox, CRS, SentinelHubRequest, MimeType,
    DataCollection, bbox_to_dimensions, SentinelHubCatalog
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# Load the TensorFlow model
model = load_model("unet_model.h5")

app = FastAPI(
    title="Unified Geospatial Change Detection API",
    description="Comprehensive satellite-based urban change detection API with both simple and advanced endpoints",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for analysis history
analysis_history = []
active_analyses = {}

# ===== PYDANTIC MODELS =====

# Simple API Models (from api_service.py)
class ChangeDetectionRequest(BaseModel):
    location: str
    zoom_level: str = "City-Wide (0.025°)"
    resolution: str = "Standard (5m)"
    alpha: float = 0.4

class ChangeDetectionResponse(BaseModel):
    success: bool
    message: str
    coordinates: Optional[Dict[str, float]] = None
    dates: Optional[Dict[str, str]] = None
    statistics: Optional[Dict[str, Any]] = None
    images: Optional[Dict[str, str]] = None

# Advanced API Models (from geospatial agent)
class AnalysisRequest(BaseModel):
    location: Dict[str, float]  # {"lat": 25.2048, "lon": 55.2708}
    time_range: Optional[Dict[str, str]] = None
    analysis_type: str = "urban_change"
    zoom_level: Optional[str] = "City-Wide (0.025°)"
    resolution: Optional[str] = "Standard (5m)"
    overlay_alpha: Optional[float] = 0.4
    include_images: Optional[bool] = True

class BatchAnalysisRequest(BaseModel):
    locations: List[Dict[str, Any]]
    zoom_level: Optional[str] = "City-Wide (0.025°)"
    resolution: Optional[str] = "Standard (5m)"
    overlay_alpha: Optional[float] = 0.4
    include_images: Optional[bool] = True

class LocationSearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 10

class AnalysisResponse(BaseModel):
    status: str
    data: Dict[str, Any]

class BatchAnalysisResponse(BaseModel):
    status: str
    batch_id: str
    total_locations: int
    completed: int
    results: List[Dict[str, Any]]

class LocationSearchResponse(BaseModel):
    status: str
    locations: List[Dict[str, Any]]

class AnalysisHistoryResponse(BaseModel):
    status: str
    analyses: List[Dict[str, Any]]

# ===== UTILITY FUNCTIONS =====

def get_coordinates(location_name):
    geolocator = Nominatim(user_agent="unified_change_detector_app")
    location = geolocator.geocode(location_name)
    if location:
        return location.latitude, location.longitude
    return None, None

def map_bbox_choice(choice):
    return {"City-Wide (0.025°)": 0.025, "Block-Level (0.01°)": 0.01, "Zoomed-In (0.005°)": 0.005}[choice]

def map_resolution_choice(choice):
    return {"Coarse (10m)": 10, "Standard (5m)": 5, "Fine (2.5m)": 2.5}[choice]

def get_two_zero_cloud_dates(lat, lon, buffer):
    config = SHConfig()
    config.sh_client_id = CLIENT_ID
    config.sh_client_secret = CLIENT_SECRET

    bbox = BBox([lon - buffer, lat - buffer, lon + buffer, lat + buffer], crs=CRS.WGS84)
    catalog = SentinelHubCatalog(config=config)

    start_date = datetime(2017, 3, 28)
    end_date = datetime.now()

    search_iterator = catalog.search(
        DataCollection.SENTINEL2_L2A,
        bbox=bbox,
        time=(start_date, end_date),
        filter={
            "op": "=",
            "args": [
                {"property": "eo:cloud_cover"},
                0.0
            ]
        },
        filter_lang="cql2-json",
        fields={
            "include": ["id", "properties.datetime", "properties.eo:cloud_cover"],
            "exclude": []
        }
    )

    results = list(search_iterator)
    if len(results) < 2:
        return None, None

    sorted_results = sorted(results, key=lambda r: r["properties"]["datetime"])
    date1 = sorted_results[0]["properties"]["datetime"][:10]
    date2 = sorted_results[-1]["properties"]["datetime"][:10]
    return date1, date2

def normalize_image(data):
    p2 = np.percentile(data, 2)
    p98 = np.percentile(data, 98)
    scaled = np.clip((data - p2) / (p98 - p2), 0, 1)
    return (scaled * 255).astype(np.uint8)

def fetch_sentinel_image(lat, lon, date, buffer, resolution):
    config = SHConfig()
    config.sh_client_id = CLIENT_ID
    config.sh_client_secret = CLIENT_SECRET

    bbox = BBox([lon - buffer, lat - buffer, lon + buffer, lat + buffer], crs=CRS.WGS84)
    size = bbox_to_dimensions(bbox, resolution=resolution)

    request = SentinelHubRequest(
        evalscript="""
        //VERSION=3
        function setup() {
          return {
            input: ["B04", "B03", "B02"],
            output: { bands: 3, sampleType: "AUTO" }
          };
        }
        function evaluatePixel(sample) {
          return [sample.B04, sample.B03, sample.B02];
        }
        """,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=DataCollection.SENTINEL2_L2A,
                time_interval=(date, date)
            )
        ],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        bbox=bbox,
        size=size,
        config=config
    )

    try:
        data = request.get_data()[0]
        image = normalize_image(data)
        return Image.fromarray(image)
    except Exception as e:
        print(f"[ERROR] Image fetch failed: {e}")
        return None

def predict_change_mask(before_img, after_img):
    before_resized = before_img.resize((128, 128))
    after_resized = after_img.resize((128, 128))

    before_array = np.array(before_resized) / 255.0
    after_array = np.array(after_resized) / 255.0

    combined = np.concatenate([before_array, after_array], axis=-1)
    input_tensor = np.expand_dims(combined, axis=0)

    prediction = model.predict(input_tensor)[0, :, :, 0]
    binary_mask = (prediction > 0.5).astype(np.uint8) * 255
    return Image.fromarray(binary_mask).resize(before_img.size)

def overlay_mask_on_image(base_img, mask_img, color=(255, 0, 0), alpha=0.4):
    base = np.array(base_img.convert("RGB")).astype(np.uint8)
    mask = np.array(mask_img.resize(base_img.size)).astype(np.uint8)

    overlay = np.zeros_like(base)
    overlay[mask > 0] = color

    blended = (base * (1 - alpha) + overlay * alpha).astype(np.uint8)

    # Add contours for clear boundaries
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(blended, contours, -1, (255, 255, 0), thickness=2)  # yellow borders

    return Image.fromarray(blended)

def image_to_base64(image: Image.Image) -> str:
    """Convert PIL Image to base64 string"""
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode()

def image_to_base64_with_prefix(image: Image.Image) -> str:
    """Convert PIL Image to base64 string with data URL prefix"""
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two coordinates in kilometers."""
    from math import radians, cos, sin, asin, sqrt

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r

def get_available_dates(lat: float, lon: float, buffer: float = 0.025) -> List[str]:
    """Get available satellite imagery dates for a location."""
    try:
        config = SHConfig()
        config.sh_client_id = CLIENT_ID
        config.sh_client_secret = CLIENT_SECRET

        bbox = BBox([lon - buffer, lat - buffer, lon + buffer, lat + buffer], crs=CRS.WGS84)
        catalog = SentinelHubCatalog(config=config)

        start_date = datetime(2017, 3, 28)
        end_date = datetime.now()

        search_iterator = catalog.search(
            DataCollection.SENTINEL2_L2A,
            bbox=bbox,
            time=(start_date, end_date),
            filter={
                "op": "<=",
                "args": [
                    {"property": "eo:cloud_cover"},
                    20.0
                ]
            },
            filter_lang="cql2-json",
            fields={
                "include": ["id", "properties.datetime", "properties.eo:cloud_cover"],
                "exclude": []
            }
        )

        results = list(search_iterator)
        dates = [r["properties"]["datetime"][:10] for r in results]
        return sorted(list(set(dates)))
    except Exception as e:
        print(f"Error getting available dates: {e}")
        return []

def search_locations(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search for locations and return detailed information."""
    try:
        geolocator = Nominatim(user_agent="unified_change_detector_app")
        locations = []
        geocode_results = geolocator.geocode(query, exactly_one=False, limit=limit)

        if geocode_results:
            for result in geocode_results[:limit]:
                location_info = {
                    "name": result.address,
                    "display_name": result.address,
                    "coordinates": {
                        "lat": result.latitude,
                        "lon": result.longitude
                    },
                    "bbox": result.raw.get("boundingbox", None) if hasattr(result, 'raw') else None,
                    "place_type": result.raw.get("type", "unknown") if hasattr(result, 'raw') else "unknown",
                    "country": result.raw.get("display_name", "").split(", ")[-1] if hasattr(result, 'raw') else "unknown"
                }
                locations.append(location_info)

        return locations
    except Exception as e:
        print(f"Location search error: {e}")
        return []

# ===== API ENDPOINTS =====

@app.get("/")
async def root():
    return {
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

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "sentinel_hub_configured": CLIENT_ID is not None and CLIENT_SECRET is not None
    }

# ===== SIMPLE API ENDPOINTS (Original from api_service.py) =====

@app.post("/detect-change", response_model=ChangeDetectionResponse)
async def detect_change(request: ChangeDetectionRequest):
    """
    Simple change detection analysis for a given location name
    """
    try:
        # Get coordinates from location name
        lat, lon = get_coordinates(request.location)
        if lat is None:
            return ChangeDetectionResponse(
                success=False,
                message="Location not found"
            )

        # Map parameters
        buffer = map_bbox_choice(request.zoom_level)
        resolution = map_resolution_choice(request.resolution)

        # Get satellite imagery dates
        date1, date2 = get_two_zero_cloud_dates(lat, lon, buffer)
        if not date1 or not date2:
            return ChangeDetectionResponse(
                success=False,
                message="Not enough 0% cloud images found for this location"
            )

        # Fetch satellite images
        before_img = fetch_sentinel_image(lat, lon, date1, buffer, resolution)
        after_img = fetch_sentinel_image(lat, lon, date2, buffer, resolution)

        if not before_img or not after_img:
            return ChangeDetectionResponse(
                success=False,
                message="Failed to fetch satellite images"
            )

        # Perform change detection
        mask = predict_change_mask(before_img, after_img)
        overlayed = overlay_mask_on_image(after_img, mask, alpha=request.alpha)

        # Calculate statistics
        mask_array = np.array(mask)
        changed_pixels = int(np.sum(mask_array > 0))
        total_pixels = mask_array.size
        change_percentage = (changed_pixels / total_pixels) * 100

        # Convert images to base64
        images = {
            "before": image_to_base64(before_img),
            "after": image_to_base64(after_img),
            "mask": image_to_base64(mask),
            "overlay": image_to_base64(overlayed)
        }

        return ChangeDetectionResponse(
            success=True,
            message="Change detection completed successfully",
            coordinates={"latitude": lat, "longitude": lon},
            dates={"before": date1, "after": date2},
            statistics={
                "changed_pixels": changed_pixels,
                "total_pixels": total_pixels,
                "change_percentage": round(change_percentage, 2)
            },
            images=images
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/detect-change/{location}/images/{image_type}")
async def get_change_image(location: str, image_type: str, zoom_level: str = "City-Wide (0.025°)",
                          resolution: str = "Standard (5m)", alpha: float = 0.4):
    """
    Get a specific image from change detection analysis as a PNG response
    """
    if image_type not in ['before', 'after', 'mask', 'overlay']:
        raise HTTPException(status_code=400, detail="Invalid image type")

    try:
        lat, lon = get_coordinates(location)
        if lat is None:
            raise HTTPException(status_code=404, detail="Location not found")

        buffer = map_bbox_choice(zoom_level)
        resolution_val = map_resolution_choice(resolution)

        date1, date2 = get_two_zero_cloud_dates(lat, lon, buffer)
        if not date1 or not date2:
            raise HTTPException(status_code=404, detail="No suitable satellite images found")

        before_img = fetch_sentinel_image(lat, lon, date1, buffer, resolution_val)
        after_img = fetch_sentinel_image(lat, lon, date2, buffer, resolution_val)

        if not before_img or not after_img:
            raise HTTPException(status_code=500, detail="Failed to fetch satellite images")

        # Get the requested image
        if image_type == "before":
            image = before_img
        elif image_type == "after":
            image = after_img
        elif image_type == "mask":
            image = predict_change_mask(before_img, after_img)
        elif image_type == "overlay":
            mask = predict_change_mask(before_img, after_img)
            image = overlay_mask_on_image(after_img, mask, alpha=alpha)

        # Convert to bytes and return as streaming response
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='PNG')
        img_buffer.seek(0)

        return StreamingResponse(
            io.BytesIO(img_buffer.getvalue()),
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename={location}_{image_type}.png"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")

@app.get("/locations/{location}/coordinates")
async def get_location_coordinates(location: str):
    """Get coordinates for a location name"""
    lat, lon = get_coordinates(location)
    if lat is None:
        raise HTTPException(status_code=404, detail="Location not found")

    return {
        "location": location,
        "latitude": lat,
        "longitude": lon
    }

# ===== ADVANCED API ENDPOINTS (From geospatial agent) =====

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest):
    """
    Advanced geospatial analysis with detailed response format
    """
    try:
        # Extract coordinates
        if "lat" not in request.location or "lon" not in request.location:
            raise HTTPException(status_code=400, detail="Location must contain 'lat' and 'lon' fields")

        lat = request.location["lat"]
        lon = request.location["lon"]

        # Map parameters
        buffer = map_bbox_choice(request.zoom_level)
        resolution = map_resolution_choice(request.resolution)

        # Get satellite imagery dates
        date1, date2 = get_two_zero_cloud_dates(lat, lon, buffer)
        if not date1 or not date2:
            raise HTTPException(status_code=404, detail="Not enough suitable satellite images found")

        # Fetch satellite images
        before_img = fetch_sentinel_image(lat, lon, date1, buffer, resolution)
        after_img = fetch_sentinel_image(lat, lon, date2, buffer, resolution)

        if not before_img or not after_img:
            raise HTTPException(status_code=500, detail="Failed to fetch satellite images")

        # Perform change detection
        mask = predict_change_mask(before_img, after_img)
        overlayed = overlay_mask_on_image(after_img, mask, alpha=request.overlay_alpha)

        # Calculate statistics
        mask_array = np.array(mask)
        changed_pixels = int(np.sum(mask_array > 0))
        total_pixels = mask_array.size
        change_percentage = (changed_pixels / total_pixels) * 100

        # Generate job ID
        job_id = str(uuid.uuid4())

        # Convert to the advanced API format
        response_data = {
            "jobId": job_id,
            "status": "COMPLETE",
            "progress": "Analysis complete",
            "elapsedTime": 30000,
            "data": {
                "type": "change_detection_analysis",
                "intent": {
                    "intent": "CHANGE_DETECTION",
                    "location": f"Lat: {lat}, Lon: {lon}",
                    "dateRange": [date1, date2],
                    "confidence": 95,
                    "extractedParams": {
                        "priceThreshold": None,
                        "riskCriteria": True,
                        "timeFrame": None
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
                                    "coordinates": [[
                                        [lon - buffer, lat - buffer],
                                        [lon + buffer, lat - buffer],
                                        [lon + buffer, lat + buffer],
                                        [lon - buffer, lat + buffer],
                                        [lon - buffer, lat - buffer]
                                    ]]
                                },
                                "properties": {
                                    "changeType": "land_use_change",
                                    "confidence": 0.85,
                                    "area": changed_pixels,
                                    "detectionMethod": "satellite_analysis"
                                }
                            }
                        ]
                    },
                    "statistics": {
                        "totalChangeArea": changed_pixels,
                        "changePercentage": change_percentage,
                        "changedPixels": changed_pixels,
                        "totalPixels": total_pixels
                    },
                    "images": {
                        "beforeImage": image_to_base64_with_prefix(before_img),
                        "afterImage": image_to_base64_with_prefix(after_img),
                        "overlayImage": image_to_base64_with_prefix(overlayed),
                        "maskImage": image_to_base64_with_prefix(mask)
                    },
                    "metadata": {
                        "location": f"Lat: {lat}, Lon: {lon}",
                        "dateRange": [date1, date2],
                        "resolution": request.resolution or "Standard (5m)",
                        "algorithm": "U-Net Change Detection",
                        "analysisDate": datetime.now().isoformat()
                    }
                },
                "placeholder": False
            }
        }

        # Store analysis in history
        analysis_record = {
            "id": job_id,
            "timestamp": datetime.now().isoformat(),
            "location": request.location,
            "parameters": {
                "zoom_level": request.zoom_level,
                "resolution": request.resolution,
                "overlay_alpha": request.overlay_alpha
            },
            "result": {
                "coordinates": {"lat": lat, "lon": lon},
                "dates": {"before": date1, "after": date2},
                "statistics": {
                    "changed_pixels": changed_pixels,
                    "total_pixels": total_pixels,
                    "change_percentage": round(change_percentage, 2)
                },
                "images": {
                    "before": image_to_base64(before_img),
                    "after": image_to_base64(after_img),
                    "overlay": image_to_base64(overlayed),
                    "mask": image_to_base64(mask)
                }
            }
        }
        analysis_history.append(analysis_record)

        return response_data

    except Exception as e:
        job_id = str(uuid.uuid4())
        return {
            "jobId": job_id,
            "status": "ERROR",
            "progress": f"Analysis failed: {str(e)}",
            "elapsedTime": 0,
            "data": {
                "type": "change_detection_analysis",
                "intent": {
                    "intent": "CHANGE_DETECTION",
                    "location": "Unknown",
                    "dateRange": ["", ""],
                    "confidence": 0,
                    "extractedParams": {
                        "priceThreshold": None,
                        "riskCriteria": False,
                        "timeFrame": None
                    }
                },
                "data": {
                    "changePolygons": {"type": "FeatureCollection", "features": []},
                    "statistics": {"totalChangeArea": 0, "changePercentage": 0, "changedPixels": 0, "totalPixels": 0},
                    "images": {"beforeImage": "", "afterImage": "", "overlayImage": "", "maskImage": ""},
                    "metadata": {
                        "location": "Unknown",
                        "dateRange": ["", ""],
                        "resolution": "Unknown",
                        "algorithm": "U-Net Change Detection",
                        "analysisDate": datetime.now().isoformat(),
                        "error": str(e)
                    }
                },
                "placeholder": True
            }
        }

@app.post("/analyze/location")
async def analyze_by_location_name(request: dict):
    """
    Perform geospatial analysis using a location name instead of coordinates
    """
    try:
        location_name = request.get("location_name")
        if not location_name:
            raise HTTPException(status_code=400, detail="location_name is required")

        lat, lon = get_coordinates(location_name)
        if lat is None or lon is None:
            raise HTTPException(status_code=404, detail="Location not found")

        analysis_request = AnalysisRequest(
            location={"lat": lat, "lon": lon},
            zoom_level=request.get("zoom_level", "City-Wide (0.025°)"),
            resolution=request.get("resolution", "Standard (5m)"),
            overlay_alpha=request.get("overlay_alpha", 0.4)
        )

        return await analyze(analysis_request)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/locations/search", response_model=LocationSearchResponse)
async def search_locations_endpoint(request: LocationSearchRequest):
    """
    Search for locations by name or address
    """
    try:
        locations = search_locations(request.query, request.limit)
        return LocationSearchResponse(
            status="success",
            locations=locations
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Location search failed: {str(e)}")

@app.get("/analyze/history", response_model=AnalysisHistoryResponse)
async def get_analysis_history(limit: int = 50, offset: int = 0):
    """
    Get analysis history with pagination
    """
    try:
        sorted_history = sorted(analysis_history, key=lambda x: x["timestamp"], reverse=True)
        paginated_history = sorted_history[offset:offset + limit]

        return AnalysisHistoryResponse(
            status="success",
            analyses=paginated_history
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve history: {str(e)}")

@app.get("/analyze/history/{analysis_id}")
async def get_analysis_by_id(analysis_id: str):
    """
    Get a specific analysis by ID
    """
    analysis = next((a for a in analysis_history if a["id"] == analysis_id), None)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return AnalysisResponse(
        status="success",
        data=analysis
    )

@app.delete("/analyze/history/{analysis_id}")
async def delete_analysis(analysis_id: str):
    """
    Delete a specific analysis from history
    """
    global analysis_history
    analysis_history = [a for a in analysis_history if a["id"] != analysis_id]
    return {"status": "success", "message": "Analysis deleted"}

@app.get("/system/info")
async def get_system_info():
    """
    Get system information and available options
    """
    return {
        "status": "success",
        "system_info": {
            "api_version": "2.0.0",
            "model_loaded": model is not None,
            "available_zoom_levels": [
                "City-Wide (0.025°)",
                "Block-Level (0.01°)",
                "Zoomed-In (0.005°)"
            ],
            "available_resolutions": [
                "Coarse (10m)",
                "Standard (5m)",
                "Fine (2.5m)"
            ],
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

@app.get("/locations/dates")
async def get_available_dates_endpoint(lat: float, lon: float, zoom_level: str = "City-Wide (0.025°)"):
    """
    Get available satellite imagery dates for a location
    """
    try:
        buffer = map_bbox_choice(zoom_level)
        dates = get_available_dates(lat, lon, buffer)
        return {
            "status": "success",
            "available_dates": dates,
            "total_dates": len(dates)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get available dates: {str(e)}")

@app.get("/stats/summary")
async def get_analysis_summary():
    """
    Get summary statistics of all analyses
    """
    try:
        if not analysis_history:
            return {
                "status": "success",
                "summary": {
                    "total_analyses": 0,
                    "average_change_percentage": 0,
                    "recent_analyses": 0
                }
            }

        total_analyses = len(analysis_history)
        change_percentages = [a["result"]["statistics"]["change_percentage"] for a in analysis_history]
        avg_change = sum(change_percentages) / len(change_percentages) if change_percentages else 0

        from datetime import timedelta
        recent_date = datetime.now() - timedelta(days=7)
        recent_analyses = sum(1 for a in analysis_history
                            if datetime.fromisoformat(a["timestamp"]) > recent_date)

        return {
            "status": "success",
            "summary": {
                "total_analyses": total_analyses,
                "average_change_percentage": round(avg_change, 2),
                "max_change_percentage": max(change_percentages) if change_percentages else 0,
                "min_change_percentage": min(change_percentages) if change_percentages else 0,
                "recent_analyses": recent_analyses
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get summary: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)