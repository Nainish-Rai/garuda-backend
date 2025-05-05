import gradio as gr
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

# Load .env
load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# Load the TensorFlow model
model = load_model("unet_model.h5")

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

def detect_change_from_location(location, zoom_option, resolution_option, alpha=0.4):
    lat, lon = get_coordinates(location)
    if lat is None:
        return "❌ Location not found", None, None, None, None

    buffer = map_bbox_choice(zoom_option)
    resolution = map_resolution_choice(resolution_option)

    date1, date2 = get_two_zero_cloud_dates(lat, lon, buffer)
    if not date1 or not date2:
        return "❌ Not enough 0% cloud images found", None, None, None, None

    before_img = fetch_sentinel_image(lat, lon, date1, buffer, resolution)
    after_img = fetch_sentinel_image(lat, lon, date2, buffer, resolution)

    if not before_img or not after_img:
        return "❌ Image fetch failed", None, None, None, None

    mask = predict_change_mask(before_img, after_img)
    overlayed = overlay_mask_on_image(after_img, mask, alpha=alpha)

    mask_array = np.array(mask)
    changed_pixels = int(np.sum(mask_array > 0))
    total_pixels = mask_array.size
    percent = (changed_pixels / total_pixels) * 100

    stats = f"🔴 Changed Pixels: {changed_pixels} / {total_pixels} ({percent:.2f}%)"

    return (
        f"📍 Coordinates: ({lat:.4f}, {lon:.4f})\n📅 Date 1: {date1}\n📅 Date 2: {date2}",
        before_img,
        after_img,
        overlayed,
        stats
    )

def build_interface():
    with gr.Blocks(title="🌍 Urban Change Detection: Sentinel-2 + Deep Learning") as demo:
        gr.Markdown("""### 📡 Satellite Change Detection Tool\nSelect a region and zoom level. Customize image sharpness and mask overlay. Detect changes over time using Sentinel-2 and your CNN model.""")
        with gr.Row():
            location = gr.Textbox(label="Enter Location (e.g., 'San Francisco')")
            zoom = gr.Radio(choices=["City-Wide (0.025°)", "Block-Level (0.01°)", "Zoomed-In (0.005°)"], label="Zoom Level")
            resolution = gr.Radio(choices=["Coarse (10m)", "Standard (5m)", "Fine (2.5m)"], label="Image Resolution")
            alpha = gr.Slider(minimum=0.1, maximum=1.0, value=0.4, step=0.1, label="Overlay Transparency")

        btn = gr.Button("Detect Change")

        details = gr.Textbox(label="Details")
        with gr.Row():
            before = gr.Image(label="Before Image (0% Cloud)")
            after = gr.Image(label="After Image (0% Cloud)")
            overlayed = gr.Image(label="Overlayed Prediction")
        stats = gr.Textbox(label="Change Statistics")

        btn.click(fn=detect_change_from_location,
                  inputs=[location, zoom, resolution, alpha],
                  outputs=[details, before, after, overlayed, stats])
    return demo

if __name__ == "__main__":
    app = build_interface()
    app.launch()
