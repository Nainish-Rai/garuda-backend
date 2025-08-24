# Geospatial Agent API Documentation

## Base URL

```
http://localhost:8001
```

## Image Response Format

All analysis endpoints return images in base64 format within the response:

```json
{
  "status": "success",
  "data": {
    "coordinates": { "lat": 25.2048, "lon": 55.2708 },
    "dates": { "before": "2020-03-15", "after": "2023-08-10" },
    "images": {
      "before": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
      "after": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
      "overlay": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
      "mask": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
    },
    "statistics": {
      "changed_pixels": 15420,
      "total_pixels": 128000,
      "change_percentage": 12.05
    },
    "summary": "Urban change detected: 12.05% of the analyzed area shows changes between 2020-03-15 and 2023-08-10"
  }
}
```

## Core Analysis Endpoints

### 1. Single Location Analysis

```javascript
// POST /analyze
const response = await fetch("http://localhost:8001/analyze", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    location: { lat: 25.2048, lon: 55.2708 },
    zoom_level: "City-Wide (0.025°)", // or "Block-Level (0.01°)", "Zoomed-In (0.005°)"
    resolution: "Standard (5m)", // or "Coarse (10m)", "Fine (2.5m)"
    overlay_alpha: 0.4,
    include_images: true,
  }),
});
```

### 2. Analysis by Location Name

```javascript
// POST /analyze/location
const response = await fetch("http://localhost:8001/analyze/location", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    location_name: "Dubai",
    zoom_level: "City-Wide (0.025°)",
    resolution: "Standard (5m)",
    overlay_alpha: 0.4,
  }),
});
```

### 3. Batch Analysis

```javascript
// POST /analyze/batch
const response = await fetch("http://localhost:8001/analyze/batch", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    locations: [
      { name: "Dubai", lat: 25.2048, lon: 55.2708 },
      { name: "Abu Dhabi", lat: 24.4539, lon: 54.3773 },
    ],
    zoom_level: "City-Wide (0.025°)",
    resolution: "Standard (5m)",
    include_images: true,
  }),
});

// Check batch status
// GET /analyze/batch/{batch_id}
const statusResponse = await fetch(
  `http://localhost:8001/analyze/batch/${batch_id}`
);
```

## Image-Specific Endpoints

### 4. Download Individual Images

```javascript
// POST /images/download
const response = await fetch("http://localhost:8001/images/download", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    analysis_id: "your-analysis-id",
    image_type: "overlay", // or "before", "after", "mask"
  }),
});
```

### 5. Compare Two Analyses

```javascript
// POST /images/compare
const response = await fetch("http://localhost:8001/images/compare", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    analysis_id_1: "first-analysis-id",
    analysis_id_2: "second-analysis-id",
  }),
});
```

## Location Services

### 6. Search Locations

```javascript
// POST /locations/search
const response = await fetch("http://localhost:8001/locations/search", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    query: "Dubai",
    limit: 10,
  }),
});
```

### 7. Get Coordinates

```javascript
// GET /locations/coordinates/{location_name}
const response = await fetch(
  "http://localhost:8001/locations/coordinates/Dubai"
);
```

### 8. Get Available Dates

```javascript
// GET /locations/dates?lat=25.2048&lon=55.2708&zoom_level=City-Wide (0.025°)
const response = await fetch(
  "http://localhost:8001/locations/dates?lat=25.2048&lon=55.2708&zoom_level=City-Wide%20(0.025°)"
);
```

## Analysis Management

### 9. Analysis History

```javascript
// GET /analyze/history?limit=50&offset=0
const response = await fetch(
  "http://localhost:8001/analyze/history?limit=50&offset=0"
);

// Get specific analysis
// GET /analyze/history/{analysis_id}
const specificAnalysis = await fetch(
  `http://localhost:8001/analyze/history/${analysisId}`
);
```

### 10. Preview Analysis Area

```javascript
// POST /analyze/preview
const response = await fetch("http://localhost:8001/analyze/preview", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    lat: 25.2048,
    lon: 55.2708,
    zoom_level: "City-Wide (0.025°)",
  }),
});
```

## System Information

### 11. System Info

```javascript
// GET /system/info
const response = await fetch("http://localhost:8001/system/info");
```

### 12. Analysis Summary

```javascript
// GET /stats/summary
const response = await fetch("http://localhost:8001/stats/summary");
```

## Next.js Image Display Example

```jsx
// Component to display analysis results with images
import Image from "next/image";

function AnalysisResults({ analysisData }) {
  const { images, statistics, dates } = analysisData;

  return (
    <div className="analysis-results">
      <div className="image-grid">
        <div className="image-container">
          <h3>Before ({dates.before})</h3>
          <img src={images.before} alt="Before satellite image" />
        </div>

        <div className="image-container">
          <h3>After ({dates.after})</h3>
          <img src={images.after} alt="After satellite image" />
        </div>

        <div className="image-container">
          <h3>Change Detection Overlay</h3>
          <img src={images.overlay} alt="Change detection overlay" />
        </div>

        <div className="image-container">
          <h3>Change Mask</h3>
          <img src={images.mask} alt="Change detection mask" />
        </div>
      </div>

      <div className="statistics">
        <h3>Analysis Statistics</h3>
        <p>Change Percentage: {statistics.change_percentage}%</p>
        <p>Changed Pixels: {statistics.changed_pixels.toLocaleString()}</p>
        <p>Total Pixels: {statistics.total_pixels.toLocaleString()}</p>
      </div>
    </div>
  );
}
```

## Image Download Helper

```javascript
// Helper function to download base64 image
function downloadImage(base64Data, filename) {
  const link = document.createElement("a");
  link.href = base64Data;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// Usage
downloadImage(analysisData.images.overlay, "change-detection-overlay.png");
```

## Error Handling

```javascript
async function performAnalysis(locationData) {
  try {
    const response = await fetch("http://localhost:8001/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(locationData),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || "Analysis failed");
    }

    const result = await response.json();
    return result.data;
  } catch (error) {
    console.error("Analysis error:", error);
    throw error;
  }
}
```

## Available Parameters

### Zoom Levels

- `"City-Wide (0.025°)"` - Large area coverage
- `"Block-Level (0.01°)"` - Medium area coverage
- `"Zoomed-In (0.005°)"` - Small area, high detail

### Resolutions

- `"Coarse (10m)"` - 10 meter per pixel
- `"Standard (5m)"` - 5 meter per pixel (recommended)
- `"Fine (2.5m)"` - 2.5 meter per pixel (high detail)

### Image Types

- `"before"` - Satellite image from earlier date
- `"after"` - Satellite image from later date
- `"overlay"` - After image with change detection overlay
- `"mask"` - Raw change detection mask (binary)
