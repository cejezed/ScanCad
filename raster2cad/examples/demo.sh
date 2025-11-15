#!/bin/bash

# Raster2CAD Demo Script
# Demonstrates usage of the CLI and API

set -e

echo "=== Raster2CAD Demo ==="

# Ensure we're in the right directory
cd "$(dirname "$0")/.."

# Create a simple test image if it doesn't exist
if [ ! -f examples/sample.jpg ]; then
    echo "Generating sample image..."
    python3 -c "
import numpy as np
import cv2
img = np.ones((400, 600, 3), dtype=np.uint8) * 255
cv2.line(img, (100, 150), (500, 150), (0, 0, 0), 3)  # top wall
cv2.line(img, (100, 150), (100, 350), (0, 0, 0), 3)  # left wall
cv2.line(img, (500, 150), (500, 350), (0, 0, 0), 3)  # right wall
cv2.line(img, (100, 350), (500, 350), (0, 0, 0), 3)  # bottom wall
cv2.line(img, (300, 150), (300, 350), (0, 0, 0), 2)  # interior wall
cv2.circle(img, (250, 250), 20, (0, 0, 255), -1)     # fixture
cv2.putText(img, 'LIVING ROOM', (150, 250), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
cv2.imwrite('examples/sample.jpg', img)
print('✓ Sample image created: examples/sample.jpg')
"
fi

echo ""
echo "1. Analyze image and save plan (mock mode, no API key needed)"
python3 -m cli.raster2cad --in examples/sample.jpg --analyze-only --output-plan /tmp/analyzed_plan.json --verbose
echo "✓ Plan saved to /tmp/analyzed_plan.json"

echo ""
echo "2. Vectorize using analyzed plan"
python3 -m cli.raster2cad --in examples/sample.jpg --out /tmp/output_analyzed.dxf --plan /tmp/analyzed_plan.json --verbose
echo "✓ DXF saved to /tmp/output_analyzed.dxf"

echo ""
echo "3. Vectorize using sample plan"
python3 -m cli.raster2cad --in examples/sample.jpg --out /tmp/output_sample.dxf --plan examples/plan.sample.json --verbose
echo "✓ DXF saved to /tmp/output_sample.dxf"

echo ""
echo "4. Full pipeline: analyze + vectorize (single command)"
python3 -m cli.raster2cad --in examples/sample.jpg --out /tmp/output_full.dxf --verbose
echo "✓ DXF saved to /tmp/output_full.dxf"

echo ""
echo "5. API Demo (if running server)"
echo "   Start server in another terminal:"
echo "   $ python3 -m app.api"
echo ""
echo "   Then test endpoints:"
echo "   $ curl -F 'file=@examples/sample.jpg' http://localhost:8000/analyze"
echo "   $ curl -F 'file=@examples/sample.jpg' http://localhost:8000/vectorize --output output.dxf"

echo ""
echo "=== Demo Complete ==="
echo "Generated DXF files:"
ls -lh /tmp/output*.dxf 2>/dev/null || echo "No DXF files found (run vectorization first)"
