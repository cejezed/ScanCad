# ScanCad - Test Je Eigen Plattegrond

Deze gids helpt je om je eigen oude plattegronden te testen met de ScanCad wall detection.

## Snelle Start

### 1. Basis Gebruik

```bash
cd /home/user/ScanCad
python tests/test_custom_floor_plan.py /pad/naar/jouw/plattegrond.pdf
```

### 2. Met Custom Parameters

Voor oude, dunne lijntekeningen:
```bash
python tests/test_custom_floor_plan.py oude_tekening.jpg \
  --min-thickness 3 \
  --max-thickness 20 \
  --min-length 50
```

Voor moderne, dikke CAD tekeningen:
```bash
python tests/test_custom_floor_plan.py modern_plan.pdf \
  --min-thickness 15 \
  --max-thickness 60 \
  --min-length 100
```

## Ondersteunde Formaten

- ✅ **PDF** - Eerste pagina wordt geconverteerd (300 DPI)
- ✅ **JPG/JPEG** - Foto's of scans
- ✅ **PNG** - Lossless afbeeldingen

## Parameters

| Parameter | Default | Beschrijving |
|-----------|---------|--------------|
| `--min-thickness` | 8.0 | Minimale muurdikte in pixels |
| `--max-thickness` | 50.0 | Maximale muurdikte in pixels |
| `--min-length` | 80.0 | Minimale muurlengte in pixels |
| `--min-line-length` | 80.0 | Hough detectie: min lijn lengte |
| `--max-line-gap` | 15.0 | Hough detectie: max gap tussen segmenten |
| `--output` | `tests/output` | Output directory voor resultaten |

## Output

Het script genereert 3 afbeeldingen:

1. **`_original.png`** - Originele afbeelding
2. **`_all_segments.png`** - Alle gedetecteerde lijnsegmenten (rood)
3. **`_walls_detected.png`** - Alleen muren met kleurcodering:
   - 🟢 **Groen** = Horizontale muren
   - 🔵 **Blauw** = Verticale muren
   - 🟡 **Geel** = Diagonale muren

## Tips voor Oude Tekeningen

### Probleem: Geen muren gedetecteerd

**Oplossing 1**: Verlaag de minimum dikte
```bash
python tests/test_custom_floor_plan.py oude_tekening.jpg --min-thickness 2
```

**Oplossing 2**: Verlaag de minimum lengte
```bash
python tests/test_custom_floor_plan.py oude_tekening.jpg --min-length 40
```

**Oplossing 3**: Verhoog de max gap (voor onderbroken lijnen)
```bash
python tests/test_custom_floor_plan.py oude_tekening.jpg --max-line-gap 25
```

### Probleem: Te veel "muren" gedetecteerd (ook annotaties)

**Oplossing**: Verhoog de minimum dikte
```bash
python tests/test_custom_floor_plan.py tekening.jpg --min-thickness 12
```

### Probleem: Slechte scan kwaliteit

Voor gescande tekeningen met ruis:
```bash
python tests/test_custom_floor_plan.py scan.jpg \
  --min-thickness 5 \
  --max-thickness 40 \
  --max-line-gap 20 \
  --min-line-length 60
```

## Voorbeelden

### Test met sample image
```bash
cd /home/user/ScanCad
python tests/test_custom_floor_plan.py raster2cad/examples/sample.jpg
```

### Test met PDF
```bash
python tests/test_custom_floor_plan.py mijn_plattegrond.pdf --output results/
```

### Gedetailleerde analyse met lage tolerantie
```bash
python tests/test_custom_floor_plan.py detail_plan.png \
  --min-thickness 2 \
  --max-thickness 15 \
  --min-length 30
```

## Verwachte Output

```
######################################################################
# ScanCad Wall Detection - Custom Floor Plan Test
######################################################################

Input file: old_drawing.jpg
✓ Loaded image: 2400x1800 pixels

======================================================================
WALL DETECTION ANALYSIS
======================================================================

Image statistics:
  Mean pixel value: 242.3 (0=black, 255=white)
  Size: 2400x1800 pixels
  Background: WHITE (inverted for processing)

--- Line Detection ---
Parameters: min_length=80px, max_gap=15px
✓ Hough detected: 156 total line segments

--- Wall Filtering ---
Parameters: thickness=8.0-50.0px, length>=80.0px
✓ Wall filter kept: 24 wall segments
✗ Filtered out: 132 non-wall segments
  Retention rate: 15.4%

--- Wall Analysis ---

Wall orientation distribution:
  Horizontal: 12 walls
  Vertical:   10 walls
  Diagonal:   2 walls

Wall thickness statistics:
  Minimum:  12.5 pixels
  Maximum:  28.0 pixels
  Average:  18.3 pixels
  Median:   17.5 pixels

--- Output Files ---
✓ tests/output/old_drawing_original.png
✓ tests/output/old_drawing_all_segments.png (all 156 segments)
✓ tests/output/old_drawing_walls_detected.png (24 walls)

======================================================================
SUMMARY
======================================================================
✓ Successfully detected 24 walls
  Horizontal: 12
  Vertical:   10
  Diagonal:   2
  Avg thickness: 18.3px
```

## Hoe Je Eigen Bestand Uploaden

### Optie 1: Kopieer naar de container
Als je een lokaal bestand hebt op Windows:
```bash
# In PowerShell (op je Windows machine):
docker cp "E:\Mijn Documenten\plattegrond.pdf" scancad:/home/user/ScanCad/my_plan.pdf

# Dan in de container:
python tests/test_custom_floor_plan.py my_plan.pdf
```

### Optie 2: Gebruik een URL (indien het bestand online staat)
```bash
# Download eerst
wget https://example.com/floor_plan.pdf -O my_plan.pdf

# Dan testen
python tests/test_custom_floor_plan.py my_plan.pdf
```

### Optie 3: Mount een volume
Bij het starten van de container:
```bash
docker run -v "E:\Mijn Tekeningen:/data" -it scancad
python tests/test_custom_floor_plan.py /data/plattegrond.pdf
```

## Troubleshooting

### PDF Foutmelding
Als je `pdf2image not installed` ziet:
```bash
pip install pdf2image
```

### Geen lijnen gedetecteerd
- Controleer of de afbeelding goed leesbaar is
- Probeer de resolutie te verhogen (scan met minimaal 200 DPI)
- Zorg dat er voldoende contrast is

### Te veel kleine segmenten
- Verhoog `--min-length` naar 100 of hoger
- Verhoog `--min-thickness` naar 10 of hoger

## Meer Hulp

Zie de volledige opties:
```bash
python tests/test_custom_floor_plan.py --help
```
