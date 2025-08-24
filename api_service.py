from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn
import io
import base64
from datetime import datetime
import numpy as np
from PIL import Image
import cv2
import pandas as pd
from data_service import data_service

# Import the functions from your existing app.py
from geopy.geocoders import Nominatim
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import img_to_array
from sentinelhub import (
    SHConfig, BBox, CRS, SentinelHubRequest, MimeType,
    DataCollection, bbox_to_dimensions, SentinelHubCatalog
)
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# Load the TensorFlow model
model = load_model("unet_model.h5")

app = FastAPI(
    title="Change Detection API",
    description="Satellite-based urban change detection API",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class ChangeDetectionRequest(BaseModel):
    location: str
    zoom_level: str = "City-Wide (0.025°)"  # "City-Wide (0.025°)", "Block-Level (0.01°)", "Zoomed-In (0.005°)"
    resolution: str = "Standard (5m)"  # "Coarse (10m)", "Standard (5m)", "Fine (2.5m)"
    alpha: float = 0.4  # Overlay transparency

class ChangeDetectionResponse(BaseModel):
    success: bool
    message: str
    coordinates: Optional[Dict[str, float]] = None
    dates: Optional[Dict[str, str]] = None
    statistics: Optional[Dict[str, Any]] = None
    images: Optional[Dict[str, str]] = None  # Base64 encoded images
    socioeconomic_data: Optional[Dict[str, Any]] = None  # Added for datasets
    real_estate_data: Optional[Dict[str, Any]] = None    # Added for datasets
    comprehensive_analysis: Optional[Dict[str, Any]] = None  # Added for analysis

# Copy utility functions from app.py
def get_coordinates(location_name):
    geolocator = Nominatim(user_agent="change_detector_app")
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

# API Endpoints
@app.get("/")
async def root():
    return {"message": "Change Detection API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "model_loaded": model is not None}

@app.post("/detect-change", response_model=ChangeDetectionResponse)
async def detect_change(request: ChangeDetectionRequest):
    """
    Perform change detection analysis for a given location
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

        # Get comprehensive socioeconomic and real estate analysis
        comprehensive_data = data_service.get_comprehensive_analysis(lat, lon, request.location)

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
            images=images,
            socioeconomic_data=comprehensive_data.get("census_data"),
            real_estate_data=comprehensive_data.get("real_estate_data"),
            comprehensive_analysis=comprehensive_data.get("analysis")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/detect-change/{location}/images/{image_type}")
async def get_change_image(location: str, image_type: str, zoom_level: str = "City-Wide (0.025°)",
                          resolution: str = "Standard (5m)", alpha: float = 0.4):
    """
    Get a specific image from change detection analysis as a PNG response
    image_type: 'before', 'after', 'mask', or 'overlay'
    """
    if image_type not in ['before', 'after', 'mask', 'overlay']:
        raise HTTPException(status_code=400, detail="Invalid image type")

    try:
        # Perform the same analysis
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

@app.get("/locations/{location}/socioeconomic")
async def get_socioeconomic_data(location: str):
    """Get comprehensive socioeconomic and real estate data for a location"""
    try:
        lat, lon = get_coordinates(location)
        if lat is None:
            raise HTTPException(status_code=404, detail="Location not found")

        comprehensive_data = data_service.get_comprehensive_analysis(lat, lon, location)

        if comprehensive_data.get("error"):
            raise HTTPException(status_code=404, detail=comprehensive_data["error"])

        return {
            "location": location,
            "coordinates": {"latitude": lat, "longitude": lon},
            "zip_code": comprehensive_data.get("zip_code"),
            "census_data": comprehensive_data.get("census_data"),
            "real_estate_data": comprehensive_data.get("real_estate_data"),
            "analysis": comprehensive_data.get("analysis")
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/zip-codes/{zip_code}/analysis")
async def get_zip_code_analysis(zip_code: str):
    """Get analysis for a specific ZIP code"""
    try:
        census_data = data_service.get_census_data(zip_code)
        real_estate_data = data_service.get_real_estate_data(zip_code)

        if not census_data or not real_estate_data:
            raise HTTPException(status_code=404, detail="No data available for this ZIP code")

        analysis = data_service._generate_analysis(census_data, real_estate_data)

        return {
            "zip_code": zip_code,
            "census_data": census_data,
            "real_estate_data": real_estate_data,
            "analysis": analysis
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/datasets/info")
async def get_dataset_info():
    """Get information about available datasets"""
    return {
        "census_data": {
            "description": "US Census demographic and socioeconomic data by ZIP code",
            "fields": [
                "population", "median_income", "poverty_rate", "unemployment_rate",
                "education_bachelor_plus", "median_age", "housing_units",
                "owner_occupied_rate", "median_home_value"
            ]
        },
        "real_estate_data": {
            "description": "Real estate market data and trends by ZIP code",
            "fields": [
                "avg_home_price", "price_per_sqft", "inventory_months", "days_on_market",
                "new_construction_permits", "foreclosure_rate", "rent_median",
                "rent_growth_yoy", "commercial_vacancy_rate"
            ]
        },
        "geographic_mapping": {
            "description": "Geographic location mappings with coordinates",
            "fields": ["city", "state", "zip_code", "latitude", "longitude", "region", "metro_area"]
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)