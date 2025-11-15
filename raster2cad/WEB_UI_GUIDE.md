# Raster2CAD Web UI - Testing Guide

A complete guide to test Raster2CAD with a beautiful web interface.

## 🚀 Quick Start (30 seconds)

```bash
cd /home/user/ScanCad/raster2cad

# Terminal 1: Start the API server
python -m app.api

# Terminal 2: Open in browser
# http://localhost:8000
```

Done! 🎉

---

## 📋 Prerequisites

Make sure dependencies are installed:

```bash
pip install -r requirements.txt
```

---

## 🎯 Step-by-Step Instructions

### 1️⃣ Start the API Server

```bash
cd /home/user/ScanCad/raster2cad
python -m app.api
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### 2️⃣ Open Web Interface

**Option A: Direct URL**
```
http://localhost:8000
```

**Option B: From terminal**
```bash
# macOS
open http://localhost:8000

# Linux
xdg-open http://localhost:8000

# Windows
start http://localhost:8000
```

### 3️⃣ Test the UI

1. **Upload a drawing**
   - Drag-drop a JPG, PNG, or PDF file
   - Or click to select from file browser
   - See file preview and info

2. **Analyze the drawing**
   - Click "Analyze Drawing" button
   - Wait for analysis to complete
   - See feature counts (walls, texts, symbols)

3. **Generate DXF**
   - Click "Generate DXF" button
   - Wait for vectorization
   - Download buttons appear

4. **Download results**
   - Download DXF file
   - Optionally download plan.json
   - Click "Start Over" to test another file

---

## 🎨 Web UI Features

### Upload Section
- 📁 Drag-and-drop file upload
- 📸 Image preview (for JPG/PNG)
- 📊 File information display
  - Filename
  - File size
  - Image dimensions (for images)

### Configuration
- ⚙️ DPI setting (72-600 DPI)
- Default: 300 DPI

### Analysis Results
- 📊 Statistics display
  - Total features detected
  - Number of walls
  - Number of text labels
  - Number of symbols

### Processing
- ⏳ Progress indicator
- 📝 Status messages (success/error/info)
- 🔗 Real-time API status indicator

### Downloads
- 💾 Download plan.json
- 📥 Download DXF file
- 🔄 Start over button

---

## 📊 Test Scenarios

### Scenario 1: Mock Analysis (No API Key)
```
1. Upload any image
2. Click "Analyze Drawing"
3. See mock features generated
4. Click "Generate DXF"
5. Download the DXF file
6. Open in AutoCAD or viewer
```

**Result:** ✅ Should generate valid DXF with mock walls, doors, windows, text

### Scenario 2: Analyze Only
```
1. Upload image
2. Click "Analyze Drawing"
3. Click "Download Plan (JSON)"
4. Download plan.json
```

**Result:** ✅ JSON file contains detected features

### Scenario 3: PDF Input
```
1. Upload a PDF file
2. PDF is auto-converted to image
3. Analyze and vectorize normally
```

**Result:** ✅ First page converted and processed

### Scenario 4: Custom DPI
```
1. Upload image
2. Change DPI from 300 to 150
3. Analyze and vectorize
4. Download DXF
```

**Result:** ✅ DXF scaled according to new DPI

---

## 🔧 Advanced Usage

### Run with Uvicorn (More Control)

```bash
# With reload (development)
uvicorn app.api:app --reload --host 0.0.0.0 --port 8000

# Specific log level
uvicorn app.api:app --log-level debug

# With workers (production)
uvicorn app.api:app --workers 4
```

### API Only (No UI)

If you want to disable the web UI and run API only:

```bash
# Temporary: delete the web directory
mv web web.bak
python -m app.api
```

### Custom API Port

```bash
python -m uvicorn app.api:app --port 9000
# Then: http://localhost:9000
```

---

## 🐳 Docker Usage

### Option 1: Docker Run

```bash
# Build
docker build -t raster2cad:latest .

# Run API + UI
docker run -p 8000:8000 raster2cad:latest
# Open: http://localhost:8000
```

### Option 2: Docker Compose

```bash
# Run API service
docker-compose up raster2cad-api
# Open: http://localhost:8000

# View logs
docker-compose logs -f raster2cad-api

# Stop
docker-compose down
```

---

## 📁 Test Files

### Create a Test Drawing

```python
import cv2
import numpy as np

# Create a simple floor plan
img = np.ones((400, 600, 3), dtype=np.uint8) * 255

# Draw walls
cv2.line(img, (50, 50), (550, 50), (0, 0, 0), 3)      # top
cv2.line(img, (50, 50), (50, 350), (0, 0, 0), 3)      # left
cv2.line(img, (550, 50), (550, 350), (0, 0, 0), 3)    # right
cv2.line(img, (50, 350), (550, 350), (0, 0, 0), 3)    # bottom
cv2.line(img, (300, 50), (300, 350), (0, 0, 0), 2)    # interior

# Add text
cv2.putText(img, 'ROOM A', (100, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

# Save
cv2.imwrite('test_drawing.jpg', img)
print("Test drawing saved: test_drawing.jpg")
```

### Use Sample Files

The repository includes example files:

```bash
cd /home/user/ScanCad/raster2cad/examples
ls -la

# Use sample data
cp examples/plan.sample.json my_plan.json
```

---

## ❌ Troubleshooting

### "Connection Refused" / "Cannot connect to server"

**Problem:** API server not running

```bash
# Check if running
lsof -i :8000

# If not running, start it
cd /home/user/ScanCad/raster2cad
python -m app.api
```

### "API Offline" Status

**Problem:** CORS or network issue

```bash
# 1. Check server is running
# 2. Check firewall allows localhost:8000
# 3. Try hard refresh: Ctrl+Shift+R (or Cmd+Shift+R)
# 4. Open developer console: F12 > Console tab
```

### File Upload Shows "Invalid File Type"

**Problem:** Wrong file format

**Solution:** Upload JPG, PNG, or PDF only

### "Analysis failed" or "Vectorization failed"

**Problem:** 1. Missing dependencies, 2. API error, 3. Invalid image

**Solutions:**
```bash
# 1. Check dependencies
pip install -r requirements.txt

# 2. View server logs
# Check the terminal running "python -m app.api"

# 3. Try a different image
# Use examples/sample.jpg
```

### DXF File Won't Open

**Problem:** Corrupted or invalid DXF

**Solutions:**
1. Try online DXF viewer: https://www.autodesk.com/viewer
2. Check server logs for errors
3. Verify image file is valid

---

## 📊 Example Workflow

### Full Test Scenario (5 minutes)

```bash
# Terminal 1: Start API
cd /home/user/ScanCad/raster2cad
python -m app.api
# Wait for "Application startup complete"

# Terminal 2 or Browser
# 1. Open http://localhost:8000
# 2. Drag-drop examples/sample.jpg (if available) or upload your image
# 3. Click "Analyze Drawing"
#    → Wait for analysis (2-3 seconds)
#    → See feature statistics
# 4. Click "Generate DXF"
#    → Wait for vectorization (2-3 seconds)
# 5. Click "Download DXF"
#    → File downloaded: drawing-TIMESTAMP.dxf
# 6. Open DXF in CAD viewer
# 7. Verify walls, text, symbols are present
# 8. Click "Start Over" to test another file
```

---

## 🔍 Monitoring & Debugging

### Server Logs

The server outputs detailed logs. Watch them in the terminal:

```
INFO:     Started server process [PID]
INFO:     Waiting for application startup.
INFO:     Application startup complete
INFO:     127.0.0.1:XXXXX - "POST /analyze HTTP/1.1" 200 OK
```

### Browser Console (F12 → Console)

```javascript
// Check API health
fetch('http://localhost:8000/healthz')
  .then(r => r.json())
  .then(d => console.log(d))

// Check CORS
fetch('http://localhost:8000/schema')
  .then(r => r.json())
  .then(d => console.log(d))
```

### Network Tab (F12 → Network)

- Monitor HTTP requests
- Check response status codes
- View request/response bodies

---

## 📝 API Endpoints (for Reference)

| Endpoint | Method | Purpose | Returns |
|----------|--------|---------|---------|
| `/` | GET | Web UI | HTML |
| `/healthz` | GET | Health check | JSON |
| `/analyze` | POST | Analyze image | plan.json |
| `/vectorize` | POST | Generate DXF | DXF file |
| `/plan` | POST | Plan only | plan.json |
| `/schema` | GET | Plan schema | JSON Schema |

---

## ✨ Tips & Tricks

### 1. Keyboard Shortcuts
- `Ctrl+Shift+R` - Hard refresh browser cache
- `F12` - Open developer tools
- `Drag file onto page` - Quick upload

### 2. Performance
- Smaller images process faster
- DPI affects processing time (300 recommended)
- Modern browsers perform better (Chrome/Firefox/Safari)

### 3. Batch Processing
```bash
# Process multiple files via CLI
for f in scans/*.jpg; do
  python -m cli.raster2cad --in "$f" --out "output/$(basename "$f" .jpg).dxf"
done
```

### 4. Debugging
```bash
# Enable debug logging
export PYTHONUNBUFFERED=1
python -m app.api --log-level debug
```

---

## 📚 Further Reading

- See `README.md` for API documentation
- See `tests/` for usage examples
- See `cli/raster2cad.py` for CLI reference

---

## 🎉 Success Checklist

- [ ] API server starts without errors
- [ ] Web UI loads in browser
- [ ] Can upload an image
- [ ] Analysis button works
- [ ] Feature statistics display
- [ ] Vectorize button works
- [ ] DXF file downloads
- [ ] DXF opens in viewer/CAD software
- [ ] Can download plan.json
- [ ] Start Over button works

---

**Happy testing!** 🚀

For issues or questions, check the server logs and browser console first.
