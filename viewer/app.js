/**
 * Raster2CAD Interactive Viewer
 * Frontend application for visualizing and exporting vectorized floor plans
 */

const API_URL = 'http://localhost:8000';

// State
let currentImage = null;
let currentPlan = null;
let imageWidth = 0;
let imageHeight = 0;
let selectedFeatureId = null;
let editedPlan = null; // Track if plan has been edited

// DOM Elements
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const analyzeBtn = document.getElementById('analyzeBtn');
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const statusLog = document.getElementById('statusLog');
const featureStats = document.getElementById('featureStats');
const featureList = document.getElementById('featureList');
const editPanelContent = document.getElementById('editPanelContent');
const exportDxfBtn = document.getElementById('exportDxfBtn');
const vectorizeWithPlanBtn = document.getElementById('vectorizeWithPlanBtn');
const exportJsonBtn = document.getElementById('exportJsonBtn');
const exportOverlayBtn = document.getElementById('exportOverlayBtn');

// Feature visibility checkboxes
const showWalls = document.getElementById('showWalls');
const showText = document.getElementById('showText');
const showSymbols = document.getElementById('showSymbols');
const showDimensions = document.getElementById('showDimensions');
const showNoise = document.getElementById('showNoise');

// Color mapping for features
const FEATURE_COLORS = {
    wall_structure: '#3498db',
    text: '#27ae60',
    symbol: '#e74c3c',
    dimension_line: '#f39c12',
    region: '#c0392b',
    noise: '#95a5a6',
    elevation: '#e67e22',
    section: '#9b59b6',
    north_arrow: '#16a085',
};

// ===== Event Listeners =====

uploadArea.addEventListener('click', () => fileInput.click());
uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});
uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));
uploadArea.addEventListener('drop', handleFileDrop);

fileInput.addEventListener('change', handleFileSelect);
analyzeBtn.addEventListener('click', analyzeImage);
exportDxfBtn.addEventListener('click', exportDxf);
vectorizeWithPlanBtn.addEventListener('click', vectorizeWithPlan);
exportJsonBtn.addEventListener('click', exportJson);
exportOverlayBtn.addEventListener('click', exportOverlay);
canvas.addEventListener('click', handleCanvasClick);

// Redraw on checkbox changes
showWalls.addEventListener('change', () => drawOverlay());
showText.addEventListener('change', () => drawOverlay());
showSymbols.addEventListener('change', () => drawOverlay());
showDimensions.addEventListener('change', () => drawOverlay());
showNoise.addEventListener('change', () => drawOverlay());

// ===== File Handling =====

function handleFileDrop(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        fileInput.files = files;
        handleFileSelect();
    }
}

function handleFileSelect() {
    const file = fileInput.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
            currentImage = img;
            imageWidth = img.width;
            imageHeight = img.height;
            canvas.width = img.width;
            canvas.height = img.height;
            ctx.drawImage(img, 0, 0);

            uploadArea.textContent = `✓ Loaded: ${file.name} (${img.width}x${img.height})`;
            analyzeBtn.disabled = false;
            logMessage(`Loaded image: ${file.name}`, 'success');
        };
        img.src = e.target.result;
    };
    reader.readAsDataURL(file);
}

// ===== API Calls =====

async function analyzeImage() {
    if (!currentImage) {
        logMessage('No image loaded', 'error');
        return;
    }

    analyzeBtn.disabled = true;
    logMessage('Analyzing image with LLM...', 'info');

    try {
        const formData = new FormData();
        formData.append('image', fileInput.files[0]);
        formData.append('dpi', 300);

        const response = await fetch(`${API_URL}/analyze`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        currentPlan = await response.json();
        logMessage(`Analysis complete: ${currentPlan.features.length} features detected`, 'success');

        drawOverlay();
        updateFeatureStats();
        updateFeatureList();

        exportDxfBtn.disabled = false;
        exportJsonBtn.disabled = false;
        exportOverlayBtn.disabled = false;

    } catch (error) {
        logMessage(`Analysis failed: ${error.message}`, 'error');
    } finally {
        analyzeBtn.disabled = false;
    }
}

async function exportDxf() {
    if (!currentPlan) return;

    try {
        logMessage('Generating DXF...', 'info');

        const formData = new FormData();
        formData.append('image', fileInput.files[0]);
        formData.append('plan', JSON.stringify(currentPlan));

        const response = await fetch(`${API_URL}/vectorize`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const blob = await response.blob();
        downloadFile(blob, 'output.dxf', 'application/dxf');
        logMessage('DXF exported successfully', 'success');

    } catch (error) {
        logMessage(`Export failed: ${error.message}`, 'error');
    }
}

function exportJson() {
    if (!currentPlan) return;

    const json = JSON.stringify(currentPlan, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    downloadFile(blob, 'plan.json', 'application/json');
    logMessage('JSON exported successfully', 'success');
}

async function exportOverlay() {
    if (!currentPlan || !currentImage) return;

    try {
        logMessage('Creating overlay image...', 'info');

        // Draw overlay to canvas
        canvas.width = imageWidth;
        canvas.height = imageHeight;
        ctx.drawImage(currentImage, 0, 0);
        drawFeaturesOnCanvas(currentPlan.features);

        // Download canvas as PNG
        canvas.toBlob((blob) => {
            downloadFile(blob, 'overlay.png', 'image/png');
            logMessage('Overlay exported successfully', 'success');
        });

    } catch (error) {
        logMessage(`Overlay export failed: ${error.message}`, 'error');
    }
}

function downloadFile(blob, filename, mimeType) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

// ===== Feature Editing =====

function handleCanvasClick(e) {
    if (!currentPlan) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = imageWidth / rect.width;
    const scaleY = imageHeight / rect.height;

    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;

    // Find clicked feature
    for (const feature of currentPlan.features) {
        const [x1, y1, x2, y2] = feature.box;
        if (x >= x1 && x <= x2 && y >= y1 && y <= y2) {
            selectFeature(feature.id);
            return;
        }
    }

    // Click outside features
    deselectFeature();
}

function selectFeature(featureId) {
    selectedFeatureId = featureId;
    const feature = currentPlan.features.find(f => f.id === featureId);
    if (!feature) return;

    renderEditForm(feature);
    updateFeatureListSelection();
    drawOverlay();
}

function deselectFeature() {
    selectedFeatureId = null;
    editPanelContent.innerHTML = '<p class="edit-hint">Click on a feature to edit it</p>';
    updateFeatureListSelection();
    drawOverlay();
}

function renderEditForm(feature) {
    const labels = ['region', 'floorplan', 'wall_structure', 'symbol', 'text', 'dimension_line', 'north_arrow', 'elevation', 'section'];

    let metadataFields = '';
    if (feature.label === 'text') {
        const content = feature.metadata?.content || '';
        metadataFields = `
            <div class="form-group">
                <label for="contentInput">Text Content</label>
                <textarea id="contentInput" placeholder="Enter text content">${content}</textarea>
            </div>
        `;
    } else if (feature.label === 'symbol') {
        const symbolType = feature.metadata?.symbol_type || '';
        metadataFields = `
            <div class="form-group">
                <label for="symbolInput">Symbol Type</label>
                <input type="text" id="symbolInput" placeholder="e.g., door, window, toilet" value="${symbolType}">
            </div>
        `;
    }

    const confidence = (feature.conf * 100).toFixed(1);
    const [x1, y1, x2, y2] = feature.box;
    const width = Math.round(x2 - x1);
    const height = Math.round(y2 - y1);

    const html = `
        <div class="edit-form">
            <div class="form-group">
                <label>Feature ID</label>
                <input type="text" value="${feature.id}" disabled style="background: #ecf0f1;">
            </div>

            <div class="form-group">
                <label for="labelSelect">Label</label>
                <select id="labelSelect">
                    ${labels.map(l => `<option value="${l}" ${l === feature.label ? 'selected' : ''}>${l}</option>`).join('')}
                </select>
            </div>

            <div class="form-group">
                <label>Confidence</label>
                <input type="text" value="${confidence}%" disabled style="background: #ecf0f1;">
            </div>

            <div class="form-group">
                <label>Bounding Box</label>
                <input type="text" value="[${x1}, ${y1}, ${x2}, ${y2}] (${width}×${height}px)" disabled style="background: #ecf0f1;">
            </div>

            ${metadataFields}

            <div class="form-actions">
                <button class="button-edit" onclick="saveFeatureChanges()">Save</button>
                <button class="button-delete" onclick="deleteFeature('${feature.id}')">Delete</button>
            </div>
        </div>
    `;

    editPanelContent.innerHTML = html;
}

function saveFeatureChanges() {
    if (!selectedFeatureId || !currentPlan) return;

    const feature = currentPlan.features.find(f => f.id === selectedFeatureId);
    if (!feature) return;

    const labelSelect = document.getElementById('labelSelect');
    const newLabel = labelSelect.value;

    // Update label
    if (newLabel !== feature.label) {
        feature.label = newLabel;
        editedPlan = JSON.parse(JSON.stringify(currentPlan)); // Mark as edited
    }

    // Update metadata based on label
    if (newLabel === 'text') {
        const contentInput = document.getElementById('contentInput');
        if (contentInput) {
            if (!feature.metadata) feature.metadata = {};
            feature.metadata.content = contentInput.value;
            editedPlan = JSON.parse(JSON.stringify(currentPlan));
        }
    } else if (newLabel === 'symbol') {
        const symbolInput = document.getElementById('symbolInput');
        if (symbolInput) {
            if (!feature.metadata) feature.metadata = {};
            feature.metadata.symbol_type = symbolInput.value;
            editedPlan = JSON.parse(JSON.stringify(currentPlan));
        }
    }

    logMessage(`Saved changes to feature ${selectedFeatureId}`, 'success');
    renderEditForm(feature); // Re-render to show updated state
    updateFeatureList();
    drawOverlay();
    vectorizeWithPlanBtn.disabled = false;
}

function deleteFeature(featureId) {
    if (!currentPlan) return;

    const index = currentPlan.features.findIndex(f => f.id === featureId);
    if (index === -1) return;

    currentPlan.features.splice(index, 1);
    editedPlan = JSON.parse(JSON.stringify(currentPlan)); // Mark as edited

    logMessage(`Deleted feature ${featureId}`, 'success');
    deselectFeature();
    updateFeatureStats();
    updateFeatureList();
    drawOverlay();
    vectorizeWithPlanBtn.disabled = false;
}

function updateFeatureListSelection() {
    const items = document.querySelectorAll('.feature-item');
    items.forEach(item => {
        if (item.dataset.featureId === selectedFeatureId) {
            item.classList.add('selected');
        } else {
            item.classList.remove('selected');
        }
    });
}

async function vectorizeWithPlan() {
    if (!editedPlan || !fileInput.files[0]) {
        logMessage('No edited plan to vectorize', 'error');
        return;
    }

    vectorizeWithPlanBtn.disabled = true;
    logMessage('Vectorizing with edited plan...', 'info');

    try {
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('plan_json', JSON.stringify(editedPlan));
        formData.append('dpi', 300);

        const response = await fetch(`${API_URL}/vectorize-with-plan`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const blob = await response.blob();
        downloadFile(blob, 'output_edited.dxf', 'application/dxf');
        logMessage('DXF exported successfully from edited plan', 'success');

    } catch (error) {
        logMessage(`Vectorization failed: ${error.message}`, 'error');
    } finally {
        vectorizeWithPlanBtn.disabled = false;
    }
}

// ===== Drawing =====

function drawOverlay() {
    if (!currentPlan || !currentImage) return;

    canvas.width = imageWidth;
    canvas.height = imageHeight;
    ctx.drawImage(currentImage, 0, 0);

    const visibilityMap = {
        wall_structure: showWalls.checked,
        text: showText.checked,
        symbol: showSymbols.checked,
        dimension_line: showDimensions.checked,
        noise: showNoise.checked,
    };

    drawFeaturesOnCanvas(currentPlan.features, visibilityMap);
}

function drawFeaturesOnCanvas(features, visibilityMap = null) {
    if (!visibilityMap) {
        visibilityMap = {
            wall_structure: true,
            text: true,
            symbol: true,
            dimension_line: true,
            noise: false,
        };
    }

    ctx.font = '14px Arial';
    ctx.lineWidth = 2;

    for (const feature of features) {
        const label = feature.label;
        if (!visibilityMap[label]) continue;

        const [x1, y1, x2, y2] = feature.box;
        const color = FEATURE_COLORS[label] || '#95a5a6';
        const conf = (feature.conf * 100).toFixed(0);
        const isSelected = feature.id === selectedFeatureId;

        // Draw box
        ctx.strokeStyle = isSelected ? '#fff000' : color;
        ctx.lineWidth = isSelected ? 4 : 2;
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
        ctx.lineWidth = 2;

        // Draw filled background for label
        const labelText = `${label} (${conf}%)`;
        const textMetrics = ctx.measureText(labelText);
        const textWidth = textMetrics.width + 8;
        const textHeight = 20;

        ctx.fillStyle = isSelected ? '#fff000' : color;
        ctx.fillRect(x1, y1 - textHeight, textWidth, textHeight);

        // Draw text
        ctx.fillStyle = isSelected ? '#000' : 'white';
        ctx.fillText(labelText, x1 + 4, y1 - 5);

        // Draw additional content for text features
        if (label === 'text') {
            const content = feature.metadata?.content || '';
            if (content) {
                ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
                ctx.fillText(`"${content}"`, x1 + 4, y2 + 20);
            }
        }
    }
}

// ===== UI Updates =====

function updateFeatureStats() {
    if (!currentPlan) return;

    const features = currentPlan.features;
    const categories = {};

    for (const feature of features) {
        const label = feature.label;
        categories[label] = (categories[label] || 0) + 1;
    }

    let html = '<div class="feature-stats">';
    html += `<p><strong>${features.length}</strong><br>Total Features</p>`;
    html += `<p><strong>${categories.wall_structure || 0}</strong><br>Walls</p>`;
    html += `<p><strong>${categories.text || 0}</strong><br>Text</p>`;
    html += `<p><strong>${categories.symbol || 0}</strong><br>Symbols</p>`;
    html += '</div>';

    featureStats.innerHTML = html;
}

function updateFeatureList() {
    if (!currentPlan) return;

    const features = currentPlan.features.slice(0, 20); // Show first 20
    let html = '';

    for (const feature of features) {
        const label = feature.label;
        const color = FEATURE_COLORS[label] || '#95a5a6';
        const conf = (feature.conf * 100).toFixed(0);
        const isSelected = feature.id === selectedFeatureId ? 'selected' : '';

        let content = feature.metadata?.content || feature.metadata?.symbol_type || '';
        if (content) content = ` - "${content}"`;

        html += `
            <div class="feature-item ${isSelected}" data-feature-id="${feature.id}" onclick="selectFeature('${feature.id}')">
                <span class="feature-item-label" style="background: ${color};">${label}</span>
                ${feature.id} (${conf}%)${content}
            </div>
        `;
    }

    if (currentPlan.features.length > 20) {
        html += `<div class="feature-item"><em>... and ${currentPlan.features.length - 20} more</em></div>`;
    }

    featureList.innerHTML = html;
}

// ===== Logging =====

function logMessage(message, level = 'info') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${level}`;
    const timestamp = new Date().toLocaleTimeString();
    entry.textContent = `[${timestamp}] ${message}`;
    statusLog.appendChild(entry);
    statusLog.scrollTop = statusLog.scrollHeight;

    // Keep only last 100 entries
    while (statusLog.children.length > 100) {
        statusLog.removeChild(statusLog.firstChild);
    }
}

// Initial message
logMessage('Raster2CAD Viewer ready. Upload an image to begin.', 'info');
