# Raster2CAD

## LLM-First Hybrid Vectorization Engine for Architectural Drawings

Convert architectural drawings (scans, blueprints, floor plans) to production-ready DXF files using a combination of multimodal LLMs and hybrid computer vision techniques.

```
Scan → Plan.JSON → DXF
```

**Key Features:**
- 🤖 **LLM-Powered Analysis**: Uses Claude 3.5 Sonnet or GPT-4V for intelligent architectural drawing recognition
- 🎯 **Hybrid CV Engine**: Combines computer vision (OpenCV LSD) with structural understanding for accurate vectorization
- 🏗️ **CAD Output**: Generates production-ready DXF files with layers, blocks, and standards-compliant geometry
- 🚀 **Multiple Interfaces**: REST API, CLI tool, interactive web viewer, and programmatic Python API
- 🔌 **Mock Mode**: Full offline functionality without API keys (great for testing!)
- 📦 **Docker Support**: Easy deployment with Docker and Docker Compose
- ✅ **Fully Tested**: Comprehensive test suite (179 tests) with CI/CD
- ⚙️ **Advanced Preprocessing**: Automatic image cleaning, contrast enhancement, and noise removal
- 📐 **Scale Inference**: Automatic DPI/scale detection from dimension lines
- 🔍 **Smart Geometry Cleanup**: Point snapping, endpoint welding, colinear merging, orthogonalization
- 🏛️ **Room Detection**: Automated room identification with area calculation and topology analysis
- 📊 **Spatial Intelligence**: Building connectivity graphs, room clustering, pathfinding algorithms

---

## Architecture

```
┌─────────────────┐
│ Input: Scan     │ (JPG, PNG, PDF)
│ (Raster image)  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│ LLM Analyzer                │ (Claude API)
│ → Detect features           │ or Mock (offline)
│ → Generate plan.json        │
└────────┬────────────────────┘
         │
         ▼
┌──────────────────┐
│ plan.json        │
│ - Wall regions   │
│ - Text labels    │
│ - Symbols        │
│ - Dimensions     │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────┐
│ Hybrid CV Vectorizer         │
│ - LSD line detection         │
│ - Segment merging            │
│ - Endpoint snapping          │
│ - Thickness estimation       │
└────────┬─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ Output: DXF File    │
│ (CAD-ready vectors) │
└─────────────────────┘
```

---

## Advanced Modules

### Image Preprocessing (`noise_cleaning.py`)
Sophisticated image preprocessing pipeline to improve line detection quality:
- **Adaptive Thresholding**: THRESH_GAUSSIAN_C for uneven lighting handling
- **Fold Line Removal**: Detects and reduces scan fold artifacts (yellowish scan marks)
- **CLAHE Contrast Enhancement**: Contrast-Limited Adaptive Histogram Equalization for dark/light regions
- **Non-Local Means Denoising**: Advanced noise reduction while preserving edges
- **Morphological Cleanup**: Opening operations to remove small noise components

### Scale Inference (`scale_inference.py`)
Automatic pixel-to-millimeter scale detection from architectural dimensions:
- **Multi-Format Parsing**: Handles Dutch/English dimension formats (mm, m, cm with comma/dot decimals)
- **Median-Based Robustness**: Uses median of all detected dimensions for outlier resistance
- **Consistency Validation**: Checks scale uniformity across plan to catch measurement errors
- **Fallback Support**: Uses DPI-based default if no dimensions detected

### Geometry Postprocessing (`geometry_postprocess.py`)
Advanced CAD-quality segment cleaning and merging:
- **Point Clustering**: Snaps endpoints within tolerance (defaul 5px) to eliminate gaps
- **Colinear Segment Merging**: Fuses adjacent parallel segments to create continuous lines
- **Orthogonalization**: Snaps nearly-horizontal/vertical segments to perfect cardinal directions
- **Duplicate Removal**: Eliminates exact and reversed-direction duplicate segments
- **Pipeline**: Deduplicate → Snap → Merge → Orthogonalize → Deduplicate (applied twice for robustness)

### Room Detection (`rooms.py`)
Automated room/space identification from wall geometry:
- **Flood-Fill Algorithm**: Identifies enclosed connected regions in binary wall image
- **Text Label Association**: Matches detected room names and areas to rooms by proximity
- **Area Calculation**: Converts pixel areas to real-world square meters using scale
- **Downsampling Support**: Optional processing downsampling for large drawings
- **DXF Integration**: Creates LWPOLYLINE boundaries and HATCH fills in output

### Dimension Extraction (`dimensions.py`)
Architectural dimension reconstruction and validation:
- **Text Parsing**: Extracts dimension values from detected text features
- **Orientation Detection**: Classifies dimensions as horizontal, vertical, or diagonal
- **Deviation Analysis**: Calculates actual vs. expected dimension lengths
- **Quality Assurance**: Validates dimensions and flags suspicious outliers
- **DXF Output**: Creates dimension entities with text labels in DXF

### Spatial Topology Analysis (`plan_graph.py`)
Building intelligence and room relationship mapping:
- **Graph Construction**: Creates nodes (rooms) and edges (doors/openings) network
- **Room Classification**: Categorizes rooms (wet, kitchen, living, sleeping) by name
- **Connectivity Analysis**: Calculates connectivity metrics and identifies isolated areas
- **Pathfinding**: BFS-based shortest path finding between rooms
- **Clustering**: DFS-based identification of room groups and zones
- **Bidirectional Analysis**: Understands door directionality and room transitions

### Debug Visualization (`overlay.py`)
Feature verification and QA visualization:
- **Color-Coded Boxes**: Different colors for walls, text, symbols, dimensions, regions
- **Label Overlay**: Shows feature IDs, confidence scores, and content
- **Category Summary**: Panel showing feature counts by type
- **Comparison**: Side-by-side visualization of different detection models
- **Batch Processing**: Full pipeline or categorized overlays for comprehensive review

---

## Installation

### Option 1: Using pip

```bash
git clone https://github.com/yourusername/raster2cad.git
cd raster2cad
pip install -e .
```

### Option 2: Using Docker

```bash
docker build -t raster2cad:latest .
docker run -it raster2cad:latest
```

### Option 3: Using Docker Compose

```bash
docker-compose up raster2cad-api
```

---

## Quick Start

### CLI Usage

#### 1. Full Pipeline (Analyze + Vectorize)

```bash
raster2cad --in blueprint.jpg --out output.dxf --dpi 300
```

#### 2. With Pre-Generated Plan

```bash
raster2cad --in blueprint.jpg --out output.dxf --plan plan.json
```

#### 3. Analyze Only (Generate plan.json)

```bash
raster2cad --in blueprint.jpg --analyze-only --output-plan plan.json
```

#### 4. From PDF

```bash
raster2cad --in blueprint.pdf --out output.dxf --dpi 300
```

#### 5. With API Key

```bash
raster2cad --in blueprint.jpg --out output.dxf --api-key sk_live_...
```

### API Usage

#### Start Server

```bash
python -m app.api
# or with uvicorn
uvicorn app.api:app --reload
```

#### Analyze Endpoint

```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@blueprint.jpg" \
  -F "dpi=300" \
  | jq . > plan.json
```

#### Vectorize Endpoint

```bash
curl -X POST http://localhost:8000/vectorize \
  -F "file=@blueprint.jpg" \
  -F "dpi=300" \
  --output output.dxf
```

#### Vectorize with Plan

```bash
curl -X POST http://localhost:8000/vectorize \
  -F "file=@blueprint.jpg" \
  -F "plan=@plan.json" \
  --output output.dxf
```

### Programmatic Usage

```python
from app.llm_analyzer import analyze_image, mock_analyze
from app.vectorize import process_plan

# Read image
with open("blueprint.jpg", "rb") as f:
    image_bytes = f.read()

# Analyze (with API key or mock)
plan = analyze_image(image_bytes, dpi=300, api_key="sk_live_...")
# or offline: plan = mock_analyze(image_bytes, dpi=300)

# Vectorize
process_plan(plan, "blueprint.jpg", "output.dxf", dpi=300)
```

---

## API Endpoints

### `POST /analyze`

Analyze an architectural drawing image.

**Request:**
```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@drawing.jpg" \
  -F "dpi=300" \
  -F "api_key=sk_live_..."
```

**Response:** `plan.json` conforming to `plan.schema.json`

---

### `POST /vectorize`

Convert image to DXF (with optional pre-generated plan).

**Request:**
```bash
curl -X POST http://localhost:8000/vectorize \
  -F "file=@drawing.jpg" \
  -F "plan=@plan.json" \
  -F "dpi=300" \
  --output output.dxf
```

**Response:** DXF file (MIME type: `application/dxf`)

---

### `POST /plan`

Analyze and return plan without vectorization.

**Request:**
```bash
curl -X POST http://localhost:8000/plan \
  -F "file=@drawing.jpg" \
  -F "dpi=300"
```

**Response:** `plan.json`

---

### `GET /schema`

Get the plan JSON schema.

**Request:**
```bash
curl http://localhost:8000/schema
```

**Response:** JSON Schema for `plan.json`

---

### `GET /healthz`

Health check endpoint.

**Request:**
```bash
curl http://localhost:8000/healthz
```

**Response:**
```json
{"status": "ok", "service": "raster2cad"}
```

---

### `POST /overlay` (Advanced Analysis)

Create debug overlay visualization showing detected features on the original image.

**Request:**
```bash
curl -X POST http://localhost:8000/overlay \
  -F "file=@drawing.jpg" \
  -F "plan=@plan.json" \
  --output overlay.png
```

**Response:** PNG image with color-coded feature boxes and labels

**Features:**
- Color-coded bounding boxes for different feature types (walls, text, symbols, dimensions)
- Feature IDs and confidence scores
- Summary panel showing feature counts by category
- Useful for manual inspection and QA

---

### `POST /analyze-rooms` (Advanced Analysis)

Analyze room configuration from wall segments and building spatial topology.

**Request:**
```bash
curl -X POST http://localhost:8000/analyze-rooms \
  -F "file=@drawing.jpg" \
  -F "plan=@plan.json" \
  -F "dpi=300"
```

**Response:**
```json
{
  "rooms": [
    {
      "id": "room_000",
      "name": "Woonkamer",
      "area_m2": 25.5,
      "centroid": [100.0, 150.0]
    }
  ],
  "statistics": {
    "total_rooms": 3,
    "named_rooms": 3,
    "total_area_m2": 75.5
  },
  "connectivity": {
    "total_connections": 2,
    "avg_connectivity": 1.33,
    "isolated_rooms": []
  }
}
```

**Features:**
- Detects enclosed rooms using flood-fill algorithm
- Associates room names and areas from text labels
- Calculates room centroids and polygons
- Analyzes spatial connectivity and adjacency
- Identifies isolated rooms

---

### `POST /export-graph` (Advanced Analysis)

Export spatial topology graph showing room relationships and building logic.

**Request:**
```bash
curl -X POST http://localhost:8000/export-graph \
  -F "plan=@plan.json"
```

**Response:**
```json
{
  "graph": {
    "nodes": [
      {"id": "room_001", "type": "room", "name": "Woonkamer", "area_m2": 25.5}
    ],
    "edges": [
      {"from": "room_001", "to": "room_002", "type": "door", "bidirectional": true}
    ]
  },
  "analysis": {
    "total_rooms": 3,
    "total_connections": 2,
    "wet_rooms": 1,
    "living_spaces": 1,
    "sleeping_spaces": 1
  }
}
```

**Features:**
- Builds room graph with connectivity edges
- Classifies rooms (wet rooms, kitchens, living/sleeping spaces)
- Uses graph algorithms for pathfinding and clustering
- Analyzes building topology and layout logic

---

## Plan Schema

The `plan.json` file follows this schema (see `plan.schema.json`):

```json
{
  "image_source": "drawing.jpg",
  "image_dims": [1024, 768],
  "dpi": 300,
  "features": [
    {
      "id": "unique_id",
      "label": "wall_structure | elevation | section | text | symbol | dimension_line | north_arrow | noise | floorplan",
      "box": [x1, y1, x2, y2],
      "conf": 0.0,
      "metadata": {
        "content": "Room label",
        "rotation_deg": 0,
        "symbol_type": "door"
      }
    }
  ]
}
```

### Feature Labels

| Label | Description | Vectorization |
|-------|-------------|---|
| `wall_structure` | Structural walls | ✅ LSD line detection + merging |
| `text` | Text annotations | ✅ Added to TEXTS layer |
| `symbol` | Doors, windows, fixtures | ✅ Block references |
| `elevation` / `section` | Elevation/section views | ✅ Lines on dedicated layers |
| `dimension_line` | Measurement annotations | ⏭️ Skipped (informational) |
| `north_arrow` | Orientation indicator | ⏭️ Skipped |
| `noise` | Background elements | ⏭️ Ignored |
| `floorplan` | Complete floor plan | 📊 Analyzed but not directly vectorized |

---

## DXF Output

Generated DXF files include:

| Layer | Contents |
|-------|----------|
| `WALLS` | Structural walls (with thickness) |
| `LINES` | General line geometry |
| `TEXTS` | Text annotations |
| `SYMBOLS` | Block references (doors, windows, etc.) |
| `ELEV_LINES` | Elevation view lines |
| `SECTION_LINES` | Section view lines |
| `DIMENSIONS` | Dimension annotations |
| `CONSTRUCTION` | Construction/reference geometry |

### Block Definitions

Standard architectural blocks included:
- `DOOR` - Door swing arc
- `WINDOW` - Window pattern
- `STAIRCASE` - Staircase symbol
- `FIXTURE` - Generic fixture (circle + cross)
- `WALL_HATCH` - Wall fill pattern

---

## Configuration

### Environment Variables

```bash
# Anthropic API key (for Claude analysis)
export ANTHROPIC_API_KEY=sk_live_...

# Optional: OpenAI API key (for GPT-4V analysis)
export OPENAI_API_KEY=sk-proj-...

# Optional: Logging level
export LOG_LEVEL=INFO
```

### Default Settings

| Setting | Default | Notes |
|---------|---------|-------|
| DPI | 300 | Can be overridden per request |
| Snap Tolerance | 5.0 px | Endpoint snapping threshold |
| Model | claude-3-5-sonnet-20241022 | Claude model for analysis |

---

## Testing

### Run Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=app --cov-report=html

# Specific test
pytest tests/test_vectorize.py -v
```

### Docker Test Runner

```bash
docker-compose --profile test run raster2cad-test
```

### Demo Script

```bash
cd examples
bash demo.sh
```

---

## Examples

### Example 1: Floor Plan Analysis

Input: `floor_plan.jpg` (1200×900 pixels)

```bash
raster2cad --in floor_plan.jpg --out floor_plan.dxf --dpi 300
```

Output: `floor_plan.dxf` with:
- Outer walls (WALLS layer)
- Interior walls
- Doors/windows (SYMBOLS layer)
- Room labels (TEXTS layer)
- Dimension lines (DIMENSIONS layer)

### Example 2: Elevation View

Input: `elevation.jpg` + `elevation_plan.json`

```bash
raster2cad --in elevation.jpg --out elevation.dxf --plan elevation_plan.json
```

Output: `elevation.dxf` with vertical section lines on ELEV_LINES layer

### Example 3: Batch Processing

```bash
for f in scans/*.jpg; do
  raster2cad --in "$f" --out "output/$(basename "$f" .jpg).dxf"
done
```

---

## Troubleshooting

### "No module named 'app'"

Make sure you're running from the repository root:
```bash
cd raster2cad
python -m cli.raster2cad --in scan.jpg --out output.dxf
```

### "Failed to load image"

- Verify file exists and is readable
- Check file format (JPG, PNG, PDF)
- Try with `--verbose` flag for more details

### "API call failed"

- Check API key is valid: `echo $ANTHROPIC_API_KEY`
- Verify network connectivity
- Use `--verbose` for detailed error messages
- Falls back to mock analyzer if API unavailable

### DXF file won't open in AutoCAD

- Ensure DXF is valid: `dxflint output.dxf`
- Check layer names don't contain invalid characters
- Try opening in online viewer: https://www.autodesk.com/viewer

### Walls are broken/fragmented

- Increase snap tolerance: `snap_tolerance_px=10.0`
- Check input image quality (high DPI recommended)
- Verify plan.json feature boxes are accurate

---

## Performance Tips

1. **Image Quality**: Use high-DPI scans (300 DPI minimum)
2. **Pre-process**: Enhance contrast before analysis
3. **Batch Operations**: Use parallel processing for multiple files
4. **Caching**: Cache plan.json if analyzing same image multiple times
5. **Docker**: Use Docker for consistent, fast performance

---

## Architecture Decisions

### Why Hybrid CV?

- **Pure LLM**: Fast but may miss structural accuracy
- **Pure CV**: Accurate but brittle on varied inputs
- **Hybrid**: LLM provides intelligent region detection + CV handles precise vectorization

### Why Two-Stage Pipeline?

1. **Separation of Concerns**: Analysis and vectorization are independent
2. **Reusability**: Same plan.json can be re-vectorized with different parameters
3. **Debuggability**: Can inspect plan.json to verify feature detection
4. **Extensibility**: Easy to add new vectorization strategies

### Why Mock Analyzer?

- **Offline Testing**: No API calls needed for development
- **Cost Savings**: Reduce API usage during testing
- **Reliability**: Works without network/API key
- **Educational**: See example structure without real LLM

---

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for new functionality
4. Ensure tests pass: `pytest tests/ -v`
5. Format code: `black app cli blocks tests`
6. Create a Pull Request

---

## Development Setup

```bash
# Clone and install
git clone https://github.com/yourusername/raster2cad.git
cd raster2cad
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Format code
black app cli blocks tests

# Type checking
mypy app --ignore-missing-imports

# Start dev API server
python -m app.api --reload
```

---

## License

MIT License - See LICENSE file for details

---

## Citation

If you use Raster2CAD in your research, please cite:

```bibtex
@software{raster2cad2024,
  title={Raster2CAD: LLM-First Hybrid Vectorization Engine},
  author={Contributors},
  year={2024},
  url={https://github.com/yourusername/raster2cad}
}
```

---

## Support

- 📖 **Documentation**: See README.md and inline code comments
- 🐛 **Issues**: Report bugs on GitHub Issues
- 💬 **Discussions**: Ask questions in GitHub Discussions
- 📧 **Email**: Contact maintainers

---

## Roadmap

- [ ] Support for multiple page PDFs
- [ ] Real-time streaming API
- [ ] Web UI dashboard
- [ ] Advanced symbol library
- [ ] Layout optimization (minimal line count)
- [ ] Automatic layer classification
- [ ] Integration with CAD software plugins
- [ ] Multi-language support for text extraction
- [ ] Performance benchmarking suite

---

**Built with ❤️ for architects and engineers**
