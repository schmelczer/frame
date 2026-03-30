# Dithering Test Suite

Local testing suite for comparing dithering algorithms on the 6-color e-ink display.

## Setup

```bash
cd dither_test
pip install pillow numpy
```

For the interactive preview (optional):
```bash
# Tkinter is usually included with Python
# On Debian/Ubuntu if missing:
sudo apt-get install python3-tk
```

## Quick Start

### Compare all algorithms
```bash
python compare.py photo.jpg --html
# Open dither_output/photo_report.html in browser
```

### Interactive preview
```bash
python preview.py photo.jpg
# Use arrow keys to cycle through algorithms
```

## Tools

### `compare.py` - Batch Comparison Tool

Generate comparison outputs for multiple dithering algorithms.

```bash
# Compare all algorithms, save individual images
python compare.py image.jpg

# Compare specific algorithms only
python compare.py image.jpg -a floyd_steinberg atkinson jarvis

# Generate visual grid comparison
python compare.py image.jpg --grid

# Generate HTML report (recommended)
python compare.py image.jpg --html

# Side-by-side comparison of two algorithms
python compare.py image.jpg --side-by-side atkinson pil_fs

# With rotation
python compare.py image.jpg --html -r 90

# List available algorithms
python compare.py --list
```

### `preview.py` - Interactive Preview

Real-time preview with keyboard navigation.

```bash
python preview.py image.jpg
```

**Keyboard shortcuts:**
- `←` / `→` or `A` / `D` - Cycle through algorithms
- `R` - Rotate image (0° → 90° → 180° → 270°)
- `S` - Save current result
- `O` - Open new image
- `Q` or `Esc` - Quit

### `dither_algorithms.py` - Algorithm Library

Use in your own scripts:

```python
from dither_algorithms import apply_dithering, get_algorithm_names
from PIL import Image

img = Image.open('photo.jpg')
dithered = apply_dithering(img, 'atkinson')
dithered.save('output.png')

# List all algorithms
print(get_algorithm_names())
```

## Available Algorithms

### Error Diffusion (spread quantization error to neighbors)

| Algorithm | Description |
|-----------|-------------|
| `floyd_steinberg` | Classic (1976), good balance of speed and quality |
| `floyd_steinberg_weighted` | With perceptual color weighting |
| `atkinson` | Bill Atkinson (Apple), cleaner with 75% error diffusion |
| `atkinson_weighted` | Atkinson with perceptual weighting |
| `jarvis` | Jarvis-Judice-Ninke, smoother gradients, slower |
| `stucki` | Similar to JJN with modified weights |
| `sierra` | Full Sierra, balanced results |
| `sierra_lite` | Faster Sierra variant |
| `burkes` | Simplified two-row diffusion |

### Ordered Dithering (threshold matrix pattern)

| Algorithm | Description |
|-----------|-------------|
| `bayer2` | 2×2 Bayer matrix, visible pattern |
| `bayer4` | 4×4 Bayer matrix, common choice |
| `bayer8` | 8×8 Bayer matrix, finer pattern |
| `bayer4_strong` | 4×4 with increased strength |

### PIL Built-in (for reference)

| Algorithm | Description |
|-----------|-------------|
| `none` | No dithering, nearest color only |
| `pil_fs` | PIL's Floyd-Steinberg implementation |

## Recommendations

For **photographic images**: `atkinson` or `floyd_steinberg_weighted`
- Better color accuracy, smoother gradients

For **graphics/illustrations**: `bayer4` or `bayer8`
- Consistent patterns, no "wormy" artifacts

For **high contrast images**: `atkinson`
- Cleaner edges, less noise in solid areas

For **fastest processing**: `sierra_lite` or `pil_fs`
- Good quality with faster execution

## Output

Results are saved to `dither_output/` by default:

```
dither_output/
├── photo_source.png          # Prepared source (800×480)
├── photo_atkinson.png        # Each algorithm result
├── photo_floyd_steinberg.png
├── ...
├── photo_grid.png            # Grid comparison (--grid)
└── photo_report.html         # HTML report (--html)
```

## 6-Color Palette

The e-ink display uses these colors:

| Color  | RGB |
|--------|-----|
| Black  | (0, 0, 0) |
| White  | (255, 255, 255) |
| Yellow | (255, 255, 0) |
| Red    | (255, 0, 0) |
| Blue   | (0, 0, 255) |
| Green  | (0, 255, 0) |
