"""
Dithering algorithms for 6-color e-ink display testing.

Includes multiple error-diffusion and ordered dithering algorithms
for comparison testing.
"""

import numpy as np
from numba import jit
from PIL import Image

# 6-color ACeP palette (RGB format)
PALETTE_RGB = [
    (0, 0, 0),  # BLACK
    (255, 255, 255),  # WHITE
    (255, 255, 0),  # YELLOW
    (255, 0, 0),  # RED
    (0, 0, 255),  # BLUE
    (0, 255, 0),  # GREEN
]

PALETTE_NAMES = ["Black", "White", "Yellow", "Red", "Blue", "Green"]


def create_pil_palette_image() -> Image.Image:
    """Create a PIL palette image for quantization."""
    pal_image = Image.new("P", (1, 1))
    flat_palette = []
    for color in PALETTE_RGB:
        flat_palette.extend(color)
    # Pad to 256 colors (768 values)
    flat_palette.extend([0] * (768 - len(flat_palette)))
    pal_image.putpalette(flat_palette)
    return pal_image


def find_nearest_color(pixel: np.ndarray, palette: np.ndarray) -> tuple[int, np.ndarray]:
    """Find the nearest palette color using Euclidean distance."""
    distances = np.sqrt(np.sum((palette - pixel) ** 2, axis=1))
    idx = np.argmin(distances)
    return idx, palette[idx]


def find_nearest_color_weighted(pixel: np.ndarray, palette: np.ndarray) -> tuple[int, np.ndarray]:
    """Find nearest color using perceptually-weighted distance (human eye sensitivity)."""
    # Weights based on human perception: Green > Red > Blue
    weights = np.array([0.299, 0.587, 0.114])
    diff = palette - pixel
    weighted_diff = diff * weights
    distances = np.sqrt(np.sum(weighted_diff**2, axis=1))
    idx = np.argmin(distances)
    return idx, palette[idx]


# =============================================================================
# Error Diffusion Dithering Algorithms
# =============================================================================


def dither_floyd_steinberg(image: Image.Image, weighted: bool = False) -> Image.Image:
    """
    Floyd-Steinberg dithering (1976).

    Classic error diffusion algorithm with distribution:
        * 7/16
    3/16 5/16 1/16
    """
    img = np.array(image.convert("RGB"), dtype=np.float64)
    height, width = img.shape[:2]
    palette = np.array(PALETTE_RGB, dtype=np.float64)
    find_fn = find_nearest_color_weighted if weighted else find_nearest_color

    for y in range(height):
        for x in range(width):
            old_pixel = img[y, x].copy()
            _, new_pixel = find_fn(old_pixel, palette)
            img[y, x] = new_pixel
            error = old_pixel - new_pixel

            if x + 1 < width:
                img[y, x + 1] += error * 7 / 16
            if y + 1 < height:
                if x > 0:
                    img[y + 1, x - 1] += error * 3 / 16
                img[y + 1, x] += error * 5 / 16
                if x + 1 < width:
                    img[y + 1, x + 1] += error * 1 / 16

    img = np.clip(img, 0, 255).astype(np.uint8)
    return Image.fromarray(img, "RGB")


def dither_jarvis_judice_ninke(image: Image.Image, weighted: bool = False) -> Image.Image:
    """
    Jarvis, Judice, and Ninke dithering (1976).

    Spreads error over a larger area (12 pixels):
            * 7 5
    3 5 7 5 3
    1 3 5 3 1
    All divided by 48.
    """
    img = np.array(image.convert("RGB"), dtype=np.float64)
    height, width = img.shape[:2]
    palette = np.array(PALETTE_RGB, dtype=np.float64)
    find_fn = find_nearest_color_weighted if weighted else find_nearest_color

    for y in range(height):
        for x in range(width):
            old_pixel = img[y, x].copy()
            _, new_pixel = find_fn(old_pixel, palette)
            img[y, x] = new_pixel
            error = old_pixel - new_pixel

            # Row 0 (current row)
            if x + 1 < width:
                img[y, x + 1] += error * 7 / 48
            if x + 2 < width:
                img[y, x + 2] += error * 5 / 48

            # Row 1
            if y + 1 < height:
                for dx, w in [(-2, 3), (-1, 5), (0, 7), (1, 5), (2, 3)]:
                    if 0 <= x + dx < width:
                        img[y + 1, x + dx] += error * w / 48

            # Row 2
            if y + 2 < height:
                for dx, w in [(-2, 1), (-1, 3), (0, 5), (1, 3), (2, 1)]:
                    if 0 <= x + dx < width:
                        img[y + 2, x + dx] += error * w / 48

    img = np.clip(img, 0, 255).astype(np.uint8)
    return Image.fromarray(img, "RGB")


def dither_stucki(image: Image.Image, weighted: bool = False) -> Image.Image:
    """
    Stucki dithering (1981).

    Similar to JJN but with different weights:
            * 8 4
    2 4 8 4 2
    1 2 4 2 1
    All divided by 42.
    """
    img = np.array(image.convert("RGB"), dtype=np.float64)
    height, width = img.shape[:2]
    palette = np.array(PALETTE_RGB, dtype=np.float64)
    find_fn = find_nearest_color_weighted if weighted else find_nearest_color

    for y in range(height):
        for x in range(width):
            old_pixel = img[y, x].copy()
            _, new_pixel = find_fn(old_pixel, palette)
            img[y, x] = new_pixel
            error = old_pixel - new_pixel

            if x + 1 < width:
                img[y, x + 1] += error * 8 / 42
            if x + 2 < width:
                img[y, x + 2] += error * 4 / 42

            if y + 1 < height:
                for dx, w in [(-2, 2), (-1, 4), (0, 8), (1, 4), (2, 2)]:
                    if 0 <= x + dx < width:
                        img[y + 1, x + dx] += error * w / 42

            if y + 2 < height:
                for dx, w in [(-2, 1), (-1, 2), (0, 4), (1, 2), (2, 1)]:
                    if 0 <= x + dx < width:
                        img[y + 2, x + dx] += error * w / 42

    img = np.clip(img, 0, 255).astype(np.uint8)
    return Image.fromarray(img, "RGB")


def dither_atkinson(image: Image.Image, weighted: bool = False) -> Image.Image:
    """
    Atkinson dithering (Bill Atkinson, Apple).

    Only diffuses 6/8 of the error (loses some detail but reduces noise):
        * 1 1
    1 1 1
      1
    All divided by 8 (but only 6/8 total error diffused).
    """
    img = np.array(image.convert("RGB"), dtype=np.float64)
    height, width = img.shape[:2]
    palette = np.array(PALETTE_RGB, dtype=np.float64)
    find_fn = find_nearest_color_weighted if weighted else find_nearest_color

    for y in range(height):
        for x in range(width):
            old_pixel = img[y, x].copy()
            _, new_pixel = find_fn(old_pixel, palette)
            img[y, x] = new_pixel
            error = old_pixel - new_pixel

            # Distribute 1/8 to each of 6 neighbors
            if x + 1 < width:
                img[y, x + 1] += error / 8
            if x + 2 < width:
                img[y, x + 2] += error / 8

            if y + 1 < height:
                if x > 0:
                    img[y + 1, x - 1] += error / 8
                img[y + 1, x] += error / 8
                if x + 1 < width:
                    img[y + 1, x + 1] += error / 8

            if y + 2 < height:
                img[y + 2, x] += error / 8

    img = np.clip(img, 0, 255).astype(np.uint8)
    return Image.fromarray(img, "RGB")


def dither_sierra(image: Image.Image, weighted: bool = False) -> Image.Image:
    """
    Sierra dithering (Frankie Sierra).

    Full Sierra (Sierra-3):
            * 5 3
    2 4 5 4 2
      2 3 2
    All divided by 32.
    """
    img = np.array(image.convert("RGB"), dtype=np.float64)
    height, width = img.shape[:2]
    palette = np.array(PALETTE_RGB, dtype=np.float64)
    find_fn = find_nearest_color_weighted if weighted else find_nearest_color

    for y in range(height):
        for x in range(width):
            old_pixel = img[y, x].copy()
            _, new_pixel = find_fn(old_pixel, palette)
            img[y, x] = new_pixel
            error = old_pixel - new_pixel

            if x + 1 < width:
                img[y, x + 1] += error * 5 / 32
            if x + 2 < width:
                img[y, x + 2] += error * 3 / 32

            if y + 1 < height:
                for dx, w in [(-2, 2), (-1, 4), (0, 5), (1, 4), (2, 2)]:
                    if 0 <= x + dx < width:
                        img[y + 1, x + dx] += error * w / 32

            if y + 2 < height:
                for dx, w in [(-1, 2), (0, 3), (1, 2)]:
                    if 0 <= x + dx < width:
                        img[y + 2, x + dx] += error * w / 32

    img = np.clip(img, 0, 255).astype(np.uint8)
    return Image.fromarray(img, "RGB")


def dither_sierra_lite(image: Image.Image, weighted: bool = False) -> Image.Image:
    """
    Sierra Lite (Sierra-2-4A) - faster variant.

        * 2
    1 1
    All divided by 4.
    """
    img = np.array(image.convert("RGB"), dtype=np.float64)
    height, width = img.shape[:2]
    palette = np.array(PALETTE_RGB, dtype=np.float64)
    find_fn = find_nearest_color_weighted if weighted else find_nearest_color

    for y in range(height):
        for x in range(width):
            old_pixel = img[y, x].copy()
            _, new_pixel = find_fn(old_pixel, palette)
            img[y, x] = new_pixel
            error = old_pixel - new_pixel

            if x + 1 < width:
                img[y, x + 1] += error * 2 / 4

            if y + 1 < height:
                if x > 0:
                    img[y + 1, x - 1] += error * 1 / 4
                img[y + 1, x] += error * 1 / 4

    img = np.clip(img, 0, 255).astype(np.uint8)
    return Image.fromarray(img, "RGB")


def dither_burkes(image: Image.Image, weighted: bool = False) -> Image.Image:
    """
    Burkes dithering.

        * 8 4
    2 4 8 4 2
    All divided by 32.
    """
    img = np.array(image.convert("RGB"), dtype=np.float64)
    height, width = img.shape[:2]
    palette = np.array(PALETTE_RGB, dtype=np.float64)
    find_fn = find_nearest_color_weighted if weighted else find_nearest_color

    for y in range(height):
        for x in range(width):
            old_pixel = img[y, x].copy()
            _, new_pixel = find_fn(old_pixel, palette)
            img[y, x] = new_pixel
            error = old_pixel - new_pixel

            if x + 1 < width:
                img[y, x + 1] += error * 8 / 32
            if x + 2 < width:
                img[y, x + 2] += error * 4 / 32

            if y + 1 < height:
                for dx, w in [(-2, 2), (-1, 4), (0, 8), (1, 4), (2, 2)]:
                    if 0 <= x + dx < width:
                        img[y + 1, x + dx] += error * w / 32

    img = np.clip(img, 0, 255).astype(np.uint8)
    return Image.fromarray(img, "RGB")


# =============================================================================
# Ordered Dithering Algorithms
# =============================================================================


def get_bayer_matrix(n: int) -> np.ndarray:
    """Generate a Bayer matrix of size 2^n x 2^n."""
    if n == 0:
        return np.array([[0]])
    smaller = get_bayer_matrix(n - 1)
    size = 2 ** (n - 1)
    result = np.zeros((2**n, 2**n))
    result[:size, :size] = 4 * smaller
    result[:size, size:] = 4 * smaller + 2
    result[size:, :size] = 4 * smaller + 3
    result[size:, size:] = 4 * smaller + 1
    return result


def dither_ordered_bayer(
    image: Image.Image, matrix_size: int = 4, strength: float = 1.0
) -> Image.Image:
    """
    Ordered dithering using Bayer matrix.

    Args:
        image: Input image
        matrix_size: Size of Bayer matrix (2, 4, 8, or 16)
        strength: Dithering strength multiplier (0.0-2.0)
    """
    img = np.array(image.convert("RGB"), dtype=np.float64)
    height, width = img.shape[:2]
    palette = np.array(PALETTE_RGB, dtype=np.float64)

    # Get appropriate Bayer matrix
    n = {2: 1, 4: 2, 8: 3, 16: 4}.get(matrix_size, 2)
    bayer = get_bayer_matrix(n)
    bayer_size = bayer.shape[0]

    # Normalize Bayer matrix to -0.5 to 0.5 range, then scale
    bayer_normalized = (bayer / (bayer_size**2) - 0.5) * strength * 128

    result = np.zeros_like(img)

    for y in range(height):
        for x in range(width):
            threshold = bayer_normalized[y % bayer_size, x % bayer_size]
            adjusted_pixel = img[y, x] + threshold
            adjusted_pixel = np.clip(adjusted_pixel, 0, 255)
            _, new_pixel = find_nearest_color(adjusted_pixel, palette)
            result[y, x] = new_pixel

    return Image.fromarray(result.astype(np.uint8), "RGB")


_NUMBA_PALETTE = np.array(
    [
        [0, 0, 0],
        [255, 255, 255],
        [255, 255, 0],
        [255, 0, 0],
        [0, 0, 255],
        [0, 255, 0],
    ],
    dtype=np.float64,
)
_NUMBA_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float64)


@jit(nopython=True)
def _numba_find_nearest(r, g, b, palette, weights):
    best_idx = 0
    best_dist = 1e10
    for i in range(palette.shape[0]):
        dr = (palette[i, 0] - r) * weights[0]
        dg = (palette[i, 1] - g) * weights[1]
        db = (palette[i, 2] - b) * weights[2]
        dist = dr * dr + dg * dg + db * db
        if dist < best_dist:
            best_dist = dist
            best_idx = i
    return best_idx


@jit(nopython=True)
def _numba_atkinson(img, palette, weights):
    height, width = img.shape[0], img.shape[1]
    for y in range(height):
        for x in range(width):
            old_r, old_g, old_b = img[y, x, 0], img[y, x, 1], img[y, x, 2]
            idx = _numba_find_nearest(old_r, old_g, old_b, palette, weights)
            new_r, new_g, new_b = palette[idx, 0], palette[idx, 1], palette[idx, 2]
            img[y, x, 0], img[y, x, 1], img[y, x, 2] = new_r, new_g, new_b
            err_r = (old_r - new_r) / 8.0
            err_g = (old_g - new_g) / 8.0
            err_b = (old_b - new_b) / 8.0
            if x + 1 < width:
                img[y, x + 1, 0] += err_r
                img[y, x + 1, 1] += err_g
                img[y, x + 1, 2] += err_b
            if x + 2 < width:
                img[y, x + 2, 0] += err_r
                img[y, x + 2, 1] += err_g
                img[y, x + 2, 2] += err_b
            if y + 1 < height:
                if x > 0:
                    img[y + 1, x - 1, 0] += err_r
                    img[y + 1, x - 1, 1] += err_g
                    img[y + 1, x - 1, 2] += err_b
                img[y + 1, x, 0] += err_r
                img[y + 1, x, 1] += err_g
                img[y + 1, x, 2] += err_b
                if x + 1 < width:
                    img[y + 1, x + 1, 0] += err_r
                    img[y + 1, x + 1, 1] += err_g
                    img[y + 1, x + 1, 2] += err_b
            if y + 2 < height:
                img[y + 2, x, 0] += err_r
                img[y + 2, x, 1] += err_g
                img[y + 2, x, 2] += err_b
    return img


def dither_atkinson_numba(image: Image.Image) -> Image.Image:
    """Numba-accelerated Atkinson dithering with perceptual weighting (~150x faster)."""
    img = np.array(image.convert("RGB"), dtype=np.float64)
    img = _numba_atkinson(img, _NUMBA_PALETTE, _NUMBA_WEIGHTS)
    img = np.clip(img, 0, 255).astype(np.uint8)
    return Image.fromarray(img, "RGB")


# =============================================================================
# PIL Built-in (for comparison)
# =============================================================================


def dither_pil_floyd_steinberg(image: Image.Image) -> Image.Image:
    """PIL's built-in Floyd-Steinberg dithering for comparison."""
    pal_image = create_pil_palette_image()
    img = image.convert("RGB")
    quantized = img.quantize(dither=Image.Dither.FLOYDSTEINBERG, palette=pal_image)
    return quantized.convert("RGB")


def dither_pil_none(image: Image.Image) -> Image.Image:
    """PIL quantization with no dithering (nearest color only)."""
    pal_image = create_pil_palette_image()
    img = image.convert("RGB")
    quantized = img.quantize(dither=Image.Dither.NONE, palette=pal_image)
    return quantized.convert("RGB")


# =============================================================================
# Algorithm Registry
# =============================================================================

DITHER_ALGORITHMS = {
    "none": {
        "name": "No Dithering (PIL)",
        "func": dither_pil_none,
        "description": "Simple nearest-color quantization without error diffusion",
    },
    "pil_fs": {
        "name": "Floyd-Steinberg (PIL)",
        "func": dither_pil_floyd_steinberg,
        "description": "PIL built-in Floyd-Steinberg implementation",
    },
    "floyd_steinberg": {
        "name": "Floyd-Steinberg",
        "func": dither_floyd_steinberg,
        "description": "Classic error diffusion (1976), good balance of speed and quality",
    },
    "floyd_steinberg_weighted": {
        "name": "Floyd-Steinberg (Weighted)",
        "func": lambda img: dither_floyd_steinberg(img, weighted=True),
        "description": "Floyd-Steinberg with perceptual color weighting",
    },
    "atkinson": {
        "name": "Atkinson",
        "func": dither_atkinson,
        "description": "Bill Atkinson (Apple), diffuses only 75% of error for cleaner results",
    },
    "atkinson_weighted": {
        "name": "Atkinson (Weighted)",
        "func": lambda img: dither_atkinson(img, weighted=True),
        "description": "Atkinson with perceptual color weighting",
    },
    "atkinson_fast": {
        "name": "Atkinson (Numba Fast)",
        "func": dither_atkinson_numba,
        "description": "Numba-accelerated Atkinson (~150x faster, requires numba)",
    },
    "jarvis": {
        "name": "Jarvis-Judice-Ninke",
        "func": dither_jarvis_judice_ninke,
        "description": "Larger diffusion kernel (1976), smoother gradients but slower",
    },
    "stucki": {
        "name": "Stucki",
        "func": dither_stucki,
        "description": "Similar to JJN with modified weights (1981)",
    },
    "sierra": {
        "name": "Sierra",
        "func": dither_sierra,
        "description": "Full Sierra dithering, balanced results",
    },
    "sierra_lite": {
        "name": "Sierra Lite",
        "func": dither_sierra_lite,
        "description": "Faster Sierra variant with smaller kernel",
    },
    "burkes": {
        "name": "Burkes",
        "func": dither_burkes,
        "description": "Simplified two-row error diffusion",
    },
    "bayer2": {
        "name": "Ordered (Bayer 2x2)",
        "func": lambda img: dither_ordered_bayer(img, matrix_size=2),
        "description": "Ordered dithering with 2x2 Bayer matrix",
    },
    "bayer4": {
        "name": "Ordered (Bayer 4x4)",
        "func": lambda img: dither_ordered_bayer(img, matrix_size=4),
        "description": "Ordered dithering with 4x4 Bayer matrix",
    },
    "bayer8": {
        "name": "Ordered (Bayer 8x8)",
        "func": lambda img: dither_ordered_bayer(img, matrix_size=8),
        "description": "Ordered dithering with 8x8 Bayer matrix",
    },
    "bayer4_strong": {
        "name": "Ordered (Bayer 4x4 Strong)",
        "func": lambda img: dither_ordered_bayer(img, matrix_size=4, strength=1.5),
        "description": "Bayer 4x4 with increased dithering strength",
    },
}


def get_algorithm_names() -> list[str]:
    """Return list of available algorithm names."""
    return list(DITHER_ALGORITHMS.keys())


def apply_dithering(image: Image.Image, algorithm: str) -> Image.Image:
    """Apply the specified dithering algorithm to an image."""
    if algorithm not in DITHER_ALGORITHMS:
        raise ValueError(f"Unknown algorithm: {algorithm}. Available: {get_algorithm_names()}")
    return DITHER_ALGORITHMS[algorithm]["func"](image)
