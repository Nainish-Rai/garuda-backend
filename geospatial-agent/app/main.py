from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn
import os
import sys
import base64
from io import BytesIO

from geospatial_service import GeospatialService

app = FastAPI(
    title="Geospatial Agent API",
    description="Urban change detection using satellite imagery and deep learning",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the geospatial service
geospatial_service = GeospatialService()

class AnalysisRequest(BaseModel):
    location: Dict[str, float]  # {"lat": 25.2048, "lon": 55.2708}
    time_range: Optional[Dict[str, str]] = None  # {"start": "2020-01-01", "end": "2023-12-31"}
    analysis_type: str = "urban_change"
    zoom_level: Optional[str] = "City-Wide (0.025°)"  # "City-Wide (0.025°)", "Block-Level (0.01°)", "Zoomed-In (0.005°)"
    resolution: Optional[str] = "Standard (5m)"  # "Coarse (10m)", "Standard (5m)", "Fine (2.5m)"
    overlay_alpha: Optional[float] = 0.4

class AnalysisResponse(BaseModel):
    status: str
    data: Dict[str, Any]

@app.get("/")
async def root():
    return {"message": "Geospatial Agent API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest):
    """
    Perform geospatial analysis on satellite imagery for urban change detection.
    """
    try:
        # Extract coordinates
        if "lat" not in request.location or "lon" not in request.location:
            raise HTTPException(status_code=400, detail="Location must contain 'lat' and 'lon' fields")

        lat = request.location["lat"]
        lon = request.location["lon"]

        # Perform the analysis
        result = await geospatial_service.analyze_urban_change(
            lat=lat,
            lon=lon,
            zoom_level=request.zoom_level,
            resolution=request.resolution,
            overlay_alpha=request.overlay_alpha
        )

        return AnalysisResponse(
            status="success",
            data=result
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/analyze/location")
async def analyze_by_location_name(request: dict):
    """
    Perform geospatial analysis using a location name instead of coordinates.
    """
    try:
        location_name = request.get("location_name")
        if not location_name:
            raise HTTPException(status_code=400, detail="location_name is required")

        # Convert location name to coordinates
        lat, lon = geospatial_service.get_coordinates(location_name)
        if lat is None or lon is None:
            raise HTTPException(status_code=404, detail="Location not found")

        # Create analysis request
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)