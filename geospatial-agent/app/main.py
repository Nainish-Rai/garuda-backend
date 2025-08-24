from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uvicorn
import os
import sys
import base64
from io import BytesIO
import json
from datetime import datetime
import uuid

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

# In-memory storage for analysis history (use database in production)
analysis_history = []
active_analyses = {}

class ImageData(BaseModel):
    before: str  # base64 encoded image
    after: str   # base64 encoded image
    overlay: str # base64 encoded overlay image
    mask: str    # base64 encoded mask image

class AnalysisRequest(BaseModel):
    location: Dict[str, float]  # {"lat": 25.2048, "lon": 55.2708}
    time_range: Optional[Dict[str, str]] = None  # {"start": "2020-01-01", "end": "2023-12-31"}
    analysis_type: str = "urban_change"
    zoom_level: Optional[str] = "City-Wide (0.025°)"  # "City-Wide (0.025°)", "Block-Level (0.01°)", "Zoomed-In (0.005°)"
    resolution: Optional[str] = "Standard (5m)"  # "Coarse (10m)", "Standard (5m)", "Fine (2.5m)"
    overlay_alpha: Optional[float] = 0.4
    include_images: Optional[bool] = True  # Whether to include base64 images in response

class BatchAnalysisRequest(BaseModel):
    locations: List[Dict[str, Any]]  # List of locations with names and coordinates
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

        # Generate job ID
        job_id = str(uuid.uuid4())

        # Convert to the expected format
        response_data = {
            "jobId": job_id,
            "status": "COMPLETE",
            "progress": "Analysis complete",
            "elapsedTime": 30000,  # Mock elapsed time
            "data": {
                "type": "change_detection_analysis",
                "intent": {
                    "intent": "CHANGE_DETECTION",
                    "location": f"Lat: {lat}, Lon: {lon}",
                    "dateRange": [
                        result["dates"]["before"],
                        result["dates"]["after"]
                    ],
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
                                        [lon - 0.01, lat - 0.01],
                                        [lon + 0.01, lat - 0.01],
                                        [lon + 0.01, lat + 0.01],
                                        [lon - 0.01, lat + 0.01],
                                        [lon - 0.01, lat - 0.01]
                                    ]]
                                },
                                "properties": {
                                    "changeType": "land_use_change",
                                    "confidence": 0.85,
                                    "area": result["statistics"]["changed_pixels"],
                                    "detectionMethod": "satellite_analysis"
                                }
                            }
                        ]
                    },
                    "statistics": {
                        "totalChangeArea": result["statistics"]["changed_pixels"],
                        "changePercentage": result["statistics"]["change_percentage"],
                        "changedPixels": result["statistics"]["changed_pixels"],
                        "totalPixels": result["statistics"]["total_pixels"]
                    },
                    "images": {
                        "beforeImage": result["images"]["before"],
                        "afterImage": result["images"]["after"],
                        "overlayImage": result["images"]["overlay"],
                        "maskImage": result["images"]["mask"]
                    },
                    "metadata": {
                        "location": f"Lat: {lat}, Lon: {lon}",
                        "dateRange": [
                            result["dates"]["before"],
                            result["dates"]["after"]
                        ],
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
            "result": result
        }
        analysis_history.append(analysis_record)

        return response_data

    except Exception as e:
        # Return error in expected format
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
                    "changePolygons": {
                        "type": "FeatureCollection",
                        "features": []
                    },
                    "statistics": {
                        "totalChangeArea": 0,
                        "changePercentage": 0,
                        "changedPixels": 0,
                        "totalPixels": 0
                    },
                    "images": {
                        "beforeImage": "",
                        "afterImage": "",
                        "overlayImage": "",
                        "maskImage": ""
                    },
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

@app.post("/analyze/batch", response_model=BatchAnalysisResponse)
async def batch_analyze(request: BatchAnalysisRequest, background_tasks: BackgroundTasks):
    """
    Perform batch analysis on multiple locations.
    """
    try:
        batch_id = str(uuid.uuid4())
        total_locations = len(request.locations)

        # Initialize batch analysis record
        batch_record = {
            "batch_id": batch_id,
            "status": "processing",
            "total_locations": total_locations,
            "completed": 0,
            "results": [],
            "started_at": datetime.now().isoformat()
        }
        active_analyses[batch_id] = batch_record

        # Start background processing
        background_tasks.add_task(
            process_batch_analysis,
            batch_id,
            request.locations,
            request.zoom_level,
            request.resolution,
            request.overlay_alpha
        )

        return BatchAnalysisResponse(
            status="processing",
            batch_id=batch_id,
            total_locations=total_locations,
            completed=0,
            results=[]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch analysis failed: {str(e)}")

@app.get("/analyze/batch/{batch_id}")
async def get_batch_status(batch_id: str):
    """
    Get the status of a batch analysis.
    """
    if batch_id not in active_analyses:
        raise HTTPException(status_code=404, detail="Batch analysis not found")

    batch_data = active_analyses[batch_id]
    return BatchAnalysisResponse(
        status=batch_data["status"],
        batch_id=batch_id,
        total_locations=batch_data["total_locations"],
        completed=batch_data["completed"],
        results=batch_data["results"]
    )

@app.post("/locations/search", response_model=LocationSearchResponse)
async def search_locations(request: LocationSearchRequest):
    """
    Search for locations by name or address.
    """
    try:
        locations = await geospatial_service.search_locations(request.query, request.limit)
        return LocationSearchResponse(
            status="success",
            locations=locations
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Location search failed: {str(e)}")

@app.get("/analyze/history", response_model=AnalysisHistoryResponse)
async def get_analysis_history(limit: int = 50, offset: int = 0):
    """
    Get analysis history with pagination.
    """
    try:
        # Sort by timestamp descending and apply pagination
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
    Get a specific analysis by ID.
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
    Delete a specific analysis from history.
    """
    global analysis_history
    analysis_history = [a for a in analysis_history if a["id"] != analysis_id]
    return {"status": "success", "message": "Analysis deleted"}

@app.get("/system/info")
async def get_system_info():
    """
    Get system information and available options.
    """
    return {
        "status": "success",
        "system_info": {
            "api_version": "1.0.0",
            "model_loaded": geospatial_service.model is not None,
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
            "supported_image_formats": ["PNG", "JPEG", "TIFF"]
        }
    }

@app.get("/locations/coordinates/{location_name}")
async def get_coordinates(location_name: str):
    """
    Get coordinates for a location name.
    """
    try:
        lat, lon = geospatial_service.get_coordinates(location_name)
        if lat is None or lon is None:
            raise HTTPException(status_code=404, detail="Location not found")

        return {
            "status": "success",
            "location_name": location_name,
            "coordinates": {"lat": lat, "lon": lon}
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Geocoding failed: {str(e)}")

@app.post("/analyze/preview")
async def preview_analysis_area(request: dict):
    """
    Preview the analysis area without performing the full analysis.
    """
    try:
        lat = request.get("lat")
        lon = request.get("lon")
        zoom_level = request.get("zoom_level", "City-Wide (0.025°)")

        if lat is None or lon is None:
            raise HTTPException(status_code=400, detail="lat and lon are required")

        buffer = geospatial_service._map_bbox_choice(zoom_level)
        bbox = {
            "north": lat + buffer,
            "south": lat - buffer,
            "east": lon + buffer,
            "west": lon - buffer
        }

        return {
            "status": "success",
            "preview": {
                "center": {"lat": lat, "lon": lon},
                "bbox": bbox,
                "zoom_level": zoom_level,
                "area_km2": round((buffer * 2 * 111) ** 2, 2)  # Approximate area in km²
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")

@app.get("/locations/info")
async def get_location_info(lat: float, lon: float):
    """
    Get detailed information about a location using coordinates.
    """
    try:
        info = geospatial_service.get_location_info(lat, lon)
        return {
            "status": "success",
            "location_info": info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get location info: {str(e)}")

@app.get("/locations/dates")
async def get_available_dates(lat: float, lon: float, zoom_level: str = "City-Wide (0.025°)"):
    """
    Get available satellite imagery dates for a location.
    """
    try:
        buffer = geospatial_service._map_bbox_choice(zoom_level)
        dates = geospatial_service.get_available_dates(lat, lon, buffer)
        return {
            "status": "success",
            "available_dates": dates,
            "total_dates": len(dates)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get available dates: {str(e)}")

@app.post("/export/analysis")
async def export_analysis(request: dict):
    """
    Export analysis results in different formats.
    """
    try:
        analysis_id = request.get("analysis_id")
        export_format = request.get("format", "json")  # json, csv, geojson

        if not analysis_id:
            raise HTTPException(status_code=400, detail="analysis_id is required")

        analysis = next((a for a in analysis_history if a["id"] == analysis_id), None)
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")

        if export_format.lower() == "json":
            return {
                "status": "success",
                "format": "json",
                "data": analysis
            }
        elif export_format.lower() == "csv":
            # Create CSV-friendly format
            csv_data = {
                "analysis_id": analysis["id"],
                "timestamp": analysis["timestamp"],
                "latitude": analysis["location"]["lat"],
                "longitude": analysis["location"]["lon"],
                "change_percentage": analysis["result"]["statistics"]["change_percentage"],
                "changed_pixels": analysis["result"]["statistics"]["changed_pixels"],
                "total_pixels": analysis["result"]["statistics"]["total_pixels"],
                "before_date": analysis["result"]["dates"]["before"],
                "after_date": analysis["result"]["dates"]["after"],
                "zoom_level": analysis["parameters"]["zoom_level"],
                "resolution": analysis["parameters"]["resolution"]
            }
            return {
                "status": "success",
                "format": "csv",
                "data": csv_data
            }
        else:
            raise HTTPException(status_code=400, detail="Unsupported export format")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@app.get("/stats/summary")
async def get_analysis_summary():
    """
    Get summary statistics of all analyses.
    """
    try:
        if not analysis_history:
            return {
                "status": "success",
                "summary": {
                    "total_analyses": 0,
                    "average_change_percentage": 0,
                    "most_analyzed_locations": [],
                    "recent_analyses": 0
                }
            }

        total_analyses = len(analysis_history)
        change_percentages = [a["result"]["statistics"]["change_percentage"] for a in analysis_history]
        avg_change = sum(change_percentages) / len(change_percentages) if change_percentages else 0

        # Get recent analyses (last 7 days)
        from datetime import datetime, timedelta
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

@app.post("/images/download")
async def download_analysis_images(request: dict):
    """
    Download individual images from an analysis result.
    """
    try:
        analysis_id = request.get("analysis_id")
        image_type = request.get("image_type", "overlay")  # before, after, overlay, mask

        if not analysis_id:
            raise HTTPException(status_code=400, detail="analysis_id is required")

        analysis = next((a for a in analysis_history if a["id"] == analysis_id), None)
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")

        if "images" not in analysis["result"]:
            raise HTTPException(status_code=404, detail="Images not found in analysis")

        if image_type not in analysis["result"]["images"]:
            raise HTTPException(status_code=400, detail=f"Image type '{image_type}' not available")

        return {
            "status": "success",
            "image": {
                "type": image_type,
                "data": analysis["result"]["images"][image_type],
                "analysis_id": analysis_id,
                "metadata": {
                    "coordinates": analysis["result"]["coordinates"],
                    "dates": analysis["result"]["dates"],
                    "statistics": analysis["result"]["statistics"]
                }
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image download failed: {str(e)}")

@app.post("/images/compare")
async def compare_images(request: dict):
    """
    Compare two analysis results side by side.
    """
    try:
        analysis_id_1 = request.get("analysis_id_1")
        analysis_id_2 = request.get("analysis_id_2")

        if not analysis_id_1 or not analysis_id_2:
            raise HTTPException(status_code=400, detail="Both analysis_id_1 and analysis_id_2 are required")

        analysis_1 = next((a for a in analysis_history if a["id"] == analysis_id_1), None)
        analysis_2 = next((a for a in analysis_history if a["id"] == analysis_id_2), None)

        if not analysis_1:
            raise HTTPException(status_code=404, detail="Analysis 1 not found")
        if not analysis_2:
            raise HTTPException(status_code=404, detail="Analysis 2 not found")

        comparison = {
            "analysis_1": {
                "id": analysis_id_1,
                "location": analysis_1["location"],
                "images": analysis_1["result"]["images"],
                "statistics": analysis_1["result"]["statistics"],
                "dates": analysis_1["result"]["dates"]
            },
            "analysis_2": {
                "id": analysis_id_2,
                "location": analysis_2["location"],
                "images": analysis_2["result"]["images"],
                "statistics": analysis_2["result"]["statistics"],
                "dates": analysis_2["result"]["dates"]
            },
            "comparison_metrics": {
                "change_difference": abs(
                    analysis_1["result"]["statistics"]["change_percentage"] -
                    analysis_2["result"]["statistics"]["change_percentage"]
                ),
                "distance_km": calculate_distance(
                    analysis_1["location"]["lat"], analysis_1["location"]["lon"],
                    analysis_2["location"]["lat"], analysis_2["location"]["lon"]
                )
            }
        }

        return {
            "status": "success",
            "comparison": comparison
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")

@app.post("/analyze/custom-dates")
async def analyze_custom_dates(request: dict):
    """
    Perform analysis with user-specified dates (if available).
    """
    try:
        lat = request.get("lat")
        lon = request.get("lon")
        before_date = request.get("before_date")
        after_date = request.get("after_date")
        zoom_level = request.get("zoom_level", "City-Wide (0.025°)")
        resolution = request.get("resolution", "Standard (5m)")
        overlay_alpha = request.get("overlay_alpha", 0.4)

        if not all([lat, lon, before_date, after_date]):
            raise HTTPException(status_code=400, detail="lat, lon, before_date, and after_date are required")

        # This would require modifying the geospatial service to accept custom dates
        # For now, we'll return the available dates for the location
        buffer = geospatial_service._map_bbox_choice(zoom_level)
        available_dates = geospatial_service.get_available_dates(lat, lon, buffer)

        if before_date not in available_dates or after_date not in available_dates:
            return {
                "status": "error",
                "message": "Requested dates not available",
                "available_dates": available_dates,
                "requested_dates": {
                    "before": before_date,
                    "after": after_date
                }
            }

        # If dates are available, perform regular analysis
        analysis_request = AnalysisRequest(
            location={"lat": lat, "lon": lon},
            zoom_level=zoom_level,
            resolution=resolution,
            overlay_alpha=overlay_alpha
        )

        return await analyze(analysis_request)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Custom date analysis failed: {str(e)}")

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two coordinates in kilometers."""
    from math import radians, cos, sin, asin, sqrt

    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r

async def process_batch_analysis(batch_id: str, locations: List[Dict], zoom_level: str, resolution: str, overlay_alpha: float):
    """
    Background task to process batch analysis.
    """
    batch_data = active_analyses[batch_id]

    for i, location_data in enumerate(locations):
        try:
            # Extract coordinates
            if "coordinates" in location_data:
                lat, lon = location_data["coordinates"]["lat"], location_data["coordinates"]["lon"]
            elif "lat" in location_data and "lon" in location_data:
                lat, lon = location_data["lat"], location_data["lon"]
            else:
                # Try to geocode if location name is provided
                location_name = location_data.get("name", location_data.get("location_name"))
                if location_name:
                    lat, lon = geospatial_service.get_coordinates(location_name)
                    if lat is None or lon is None:
                        continue
                else:
                    continue

            # Perform analysis
            result = await geospatial_service.analyze_urban_change(
                lat=lat,
                lon=lon,
                zoom_level=zoom_level,
                resolution=resolution,
                overlay_alpha=overlay_alpha
            )

            # Add location info to result
            result["location_info"] = location_data
            batch_data["results"].append(result)
            batch_data["completed"] += 1

        except Exception as e:
            # Add error result
            error_result = {
                "location_info": location_data,
                "error": str(e),
                "status": "failed"
            }
            batch_data["results"].append(error_result)
            batch_data["completed"] += 1

    # Mark as completed
    batch_data["status"] = "completed"
    batch_data["completed_at"] = datetime.now().isoformat()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)