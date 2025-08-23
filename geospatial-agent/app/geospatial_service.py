import asyncio
from typing import Tuple, Optional, Dict, Any
import base64
from io import BytesIO
from geopy.geocoders import Nominatim
from PIL import Image
import numpy as np
import os
from datetime import datetime
from dotenv import load_dotenv
import cv2

from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import img_to_array

from sentinelhub import (
    SHConfig, BBox, CRS, SentinelHubRequest, MimeType,
    DataCollection, bbox_to_dimensions, SentinelHubCatalog
)

class GeospatialService:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")

        # Load the TensorFlow model - go up two directories to reach the root
        model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "unet_model.h5")
        self.model = load_model(model_path)

        # Initialize geocoder
        self.geolocator = Nominatim(user_agent="geospatial_agent")

    def get_coordinates(self, location_name: str) -> Tuple[Optional[float], Optional[float]]:
        """Get coordinates from location name."""
        try:
            location = self.geolocator.geocode(location_name)
            if location:
                return location.latitude, location.longitude
            return None, None
        except Exception as e:
            print(f"Geocoding error: {e}")
            return None, None

    def _map_bbox_choice(self, choice: str) -> float:
        """Map zoom level choice to buffer value."""
        mapping = {
            "City-Wide (0.025°)": 0.025,
            "Block-Level (0.01°)": 0.01,
            "Zoomed-In (0.005°)": 0.005
        }
        return mapping.get(choice, 0.025)

    def _map_resolution_choice(self, choice: str) -> float:
        """Map resolution choice to resolution value."""
        mapping = {
            "Coarse (10m)": 10,
            "Standard (5m)": 5,
            "Fine (2.5m)": 2.5
        }
        return mapping.get(choice, 5)

    def _get_two_zero_cloud_dates(self, lat: float, lon: float, buffer: float) -> Tuple[Optional[str], Optional[str]]:
        """Find two dates with 0% cloud coverage."""
        try:
            config = SHConfig()
            config.sh_client_id = self.client_id
            config.sh_client_secret = self.client_secret

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
        except Exception as e:
            print(f"Error finding cloud-free dates: {e}")
            return None, None

    def _normalize_image(self, data: np.ndarray) -> np.ndarray:
        """Normalize image data."""
        p2 = np.percentile(data, 2)
        p98 = np.percentile(data, 98)
        scaled = np.clip((data - p2) / (p98 - p2), 0, 1)
        return (scaled * 255).astype(np.uint8)

    def _fetch_sentinel_image(self, lat: float, lon: float, date: str, buffer: float, resolution: float) -> Optional[Image.Image]:
        """Fetch satellite image from Sentinel Hub."""
        try:
            config = SHConfig()
            config.sh_client_id = self.client_id
            config.sh_client_secret = self.client_secret

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

            data = request.get_data()[0]
            image = self._normalize_image(data)
            return Image.fromarray(image)
        except Exception as e:
            print(f"Image fetch failed: {e}")
            return None

    def _predict_change_mask(self, before_img: Image.Image, after_img: Image.Image) -> Image.Image:
        """Predict change mask using the U-Net model."""
        before_resized = before_img.resize((128, 128))
        after_resized = after_img.resize((128, 128))

        before_array = np.array(before_resized) / 255.0
        after_array = np.array(after_resized) / 255.0

        combined = np.concatenate([before_array, after_array], axis=-1)
        input_tensor = np.expand_dims(combined, axis=0)

        prediction = self.model.predict(input_tensor)[0, :, :, 0]
        binary_mask = (prediction > 0.5).astype(np.uint8) * 255
        return Image.fromarray(binary_mask).resize(before_img.size)

    def _overlay_mask_on_image(self, base_img: Image.Image, mask_img: Image.Image,
                              color: Tuple[int, int, int] = (255, 0, 0), alpha: float = 0.4) -> Image.Image:
        """Overlay change mask on the base image."""
        base = np.array(base_img.convert("RGB")).astype(np.uint8)
        mask = np.array(mask_img.resize(base_img.size)).astype(np.uint8)

        overlay = np.zeros_like(base)
        overlay[mask > 0] = color

        blended = (base * (1 - alpha) + overlay * alpha).astype(np.uint8)

        # Add contours for clear boundaries
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(blended, contours, -1, (255, 255, 0), thickness=2)  # yellow borders

        return Image.fromarray(blended)

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string."""
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"

    async def analyze_urban_change(self, lat: float, lon: float, zoom_level: str = "City-Wide (0.025°)",
                                 resolution: str = "Standard (5m)", overlay_alpha: float = 0.4) -> Dict[str, Any]:
        """
        Perform urban change detection analysis.
        """
        try:
            buffer = self._map_bbox_choice(zoom_level)
            resolution_val = self._map_resolution_choice(resolution)

            # Find dates with 0% cloud coverage
            date1, date2 = self._get_two_zero_cloud_dates(lat, lon, buffer)
            if not date1 or not date2:
                raise Exception("Not enough 0% cloud images found")

            # Fetch before and after images
            before_img = self._fetch_sentinel_image(lat, lon, date1, buffer, resolution_val)
            after_img = self._fetch_sentinel_image(lat, lon, date2, buffer, resolution_val)

            if not before_img or not after_img:
                raise Exception("Image fetch failed")

            # Predict changes
            mask = self._predict_change_mask(before_img, after_img)
            overlayed = self._overlay_mask_on_image(after_img, mask, alpha=overlay_alpha)

            # Calculate statistics
            mask_array = np.array(mask)
            changed_pixels = int(np.sum(mask_array > 0))
            total_pixels = mask_array.size
            change_percentage = (changed_pixels / total_pixels) * 100

            # Convert images to base64 for API response
            result = {
                "coordinates": {"lat": lat, "lon": lon},
                "dates": {"before": date1, "after": date2},
                "analysis_parameters": {
                    "zoom_level": zoom_level,
                    "resolution": resolution,
                    "overlay_alpha": overlay_alpha
                },
                "images": {
                    "before": self._image_to_base64(before_img),
                    "after": self._image_to_base64(after_img),
                    "overlay": self._image_to_base64(overlayed),
                    "mask": self._image_to_base64(mask)
                },
                "statistics": {
                    "changed_pixels": changed_pixels,
                    "total_pixels": total_pixels,
                    "change_percentage": round(change_percentage, 2)
                },
                "summary": f"Urban change detected: {change_percentage:.2f}% of the analyzed area shows changes between {date1} and {date2}"
            }

            return result

        except Exception as e:
            raise Exception(f"Urban change analysis failed: {str(e)}")