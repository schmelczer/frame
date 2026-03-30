#!/usr/bin/env python3
"""
Dithering Comparison Tool for 6-Color E-Ink Display

Generates side-by-side comparisons of different dithering algorithms
to help select the best option for your images.

Usage:
    python compare.py image.jpg                    # Compare all algorithms
    python compare.py image.jpg -a floyd_steinberg atkinson  # Compare specific
    python compare.py image.jpg --grid             # Generate grid comparison
    python compare.py image.jpg --html             # Generate HTML report
    python compare.py --list                       # List available algorithms
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

from PIL import Image

from dither_algorithms import (
    DITHER_ALGORITHMS,
    apply_dithering,
    get_algorithm_names,
    PALETTE_RGB,
)

# Display dimensions
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480


def prepare_image(image_path: str, orientation: int = 0) -> Image.Image:
    """Load and prepare image for the display dimensions."""
    img = Image.open(image_path).convert('RGB')

    # Apply rotation
    if orientation == 90:
        img = img.transpose(Image.Transpose.ROTATE_270)
    elif orientation == 180:
        img = img.transpose(Image.Transpose.ROTATE_180)
    elif orientation == 270:
        img = img.transpose(Image.Transpose.ROTATE_90)

    # Calculate scaling to fit display
    target_w, target_h = DISPLAY_WIDTH, DISPLAY_HEIGHT
    scale = min(target_w / img.width, target_h / img.height)
    new_w = int(img.width * scale)
    new_h = int(img.height * scale)

    # Resize with high-quality resampling
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Center on white canvas
    canvas = Image.new('RGB', (target_w, target_h), (255, 255, 255))
    x = (target_w - new_w) // 2
    y = (target_h - new_h) // 2
    canvas.paste(img, (x, y))

    return canvas


def run_comparison(
    image_path: str,
    algorithms: Optional[List[str]] = None,
    output_dir: str = 'dither_output',
    orientation: int = 0,
) -> dict:
    """
    Run dithering comparison and save results.

    Returns dict with algorithm names as keys and tuples of (output_path, duration) as values.
    """
    if algorithms is None:
        algorithms = get_algorithm_names()

    # Prepare output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Get base name for outputs
    base_name = Path(image_path).stem

    # Load and prepare source image
    print(f"Loading and preparing: {image_path}")
    source = prepare_image(image_path, orientation)

    # Save prepared source for reference
    source_out = output_path / f"{base_name}_source.png"
    source.save(source_out)
    print(f"  Saved prepared source: {source_out}")

    results = {}

    for algo_name in algorithms:
        if algo_name not in DITHER_ALGORITHMS:
            print(f"  Warning: Unknown algorithm '{algo_name}', skipping")
            continue

        algo_info = DITHER_ALGORITHMS[algo_name]
        print(f"  Processing: {algo_info['name']}...", end=' ', flush=True)

        start_time = time.time()
        dithered = apply_dithering(source, algo_name)
        duration = time.time() - start_time

        out_file = output_path / f"{base_name}_{algo_name}.png"
        dithered.save(out_file)

        results[algo_name] = (str(out_file), duration)
        print(f"{duration:.2f}s -> {out_file}")

    return results


def create_comparison_grid(
    image_path: str,
    algorithms: Optional[List[str]] = None,
    output_dir: str = 'dither_output',
    orientation: int = 0,
    cols: int = 3,
) -> str:
    """Create a single image with all algorithms in a grid layout."""
    if algorithms is None:
        algorithms = get_algorithm_names()

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    base_name = Path(image_path).stem
    source = prepare_image(image_path, orientation)

    # Calculate grid dimensions
    n_images = len(algorithms) + 1  # +1 for source
    rows = (n_images + cols - 1) // cols

    # Thumbnail size (scaled down for grid)
    thumb_w = DISPLAY_WIDTH // 2
    thumb_h = DISPLAY_HEIGHT // 2
    padding = 10
    label_height = 30

    # Create grid canvas
    grid_w = cols * (thumb_w + padding) + padding
    grid_h = rows * (thumb_h + label_height + padding) + padding
    grid = Image.new('RGB', (grid_w, grid_h), (240, 240, 240))

    # Import for text rendering
    try:
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(grid)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except:
            font = ImageFont.load_default()
    except ImportError:
        draw = None
        font = None

    def add_to_grid(img: Image.Image, label: str, idx: int):
        row = idx // cols
        col = idx % cols
        x = padding + col * (thumb_w + padding)
        y = padding + row * (thumb_h + label_height + padding)

        # Resize for thumbnail
        thumb = img.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        grid.paste(thumb, (x, y + label_height))

        # Add label
        if draw:
            draw.text((x + 5, y + 5), label, fill=(0, 0, 0), font=font)

    # Add source image first
    add_to_grid(source, "Original (Prepared)", 0)

    # Process and add each algorithm
    for i, algo_name in enumerate(algorithms, 1):
        if algo_name not in DITHER_ALGORITHMS:
            continue
        algo_info = DITHER_ALGORITHMS[algo_name]
        print(f"  Grid: {algo_info['name']}...")
        dithered = apply_dithering(source, algo_name)
        add_to_grid(dithered, algo_info['name'], i)

    # Save grid
    grid_file = output_path / f"{base_name}_grid.png"
    grid.save(grid_file)
    print(f"Grid saved: {grid_file}")

    return str(grid_file)


def create_side_by_side(
    image_path: str,
    algo1: str,
    algo2: str,
    output_dir: str = 'dither_output',
    orientation: int = 0,
) -> str:
    """Create a side-by-side comparison of two algorithms."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    base_name = Path(image_path).stem
    source = prepare_image(image_path, orientation)

    info1 = DITHER_ALGORITHMS[algo1]
    info2 = DITHER_ALGORITHMS[algo2]

    print(f"  Processing {info1['name']}...")
    img1 = apply_dithering(source, algo1)

    print(f"  Processing {info2['name']}...")
    img2 = apply_dithering(source, algo2)

    # Create side-by-side
    padding = 20
    label_h = 40
    width = DISPLAY_WIDTH * 2 + padding * 3
    height = DISPLAY_HEIGHT + padding * 2 + label_h

    canvas = Image.new('RGB', (width, height), (240, 240, 240))
    canvas.paste(img1, (padding, padding + label_h))
    canvas.paste(img2, (DISPLAY_WIDTH + padding * 2, padding + label_h))

    # Add labels
    try:
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(canvas)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except:
            font = ImageFont.load_default()

        draw.text((padding + 10, padding + 5), info1['name'], fill=(0, 0, 0), font=font)
        draw.text((DISPLAY_WIDTH + padding * 2 + 10, padding + 5), info2['name'], fill=(0, 0, 0), font=font)
    except ImportError:
        pass

    out_file = output_path / f"{base_name}_{algo1}_vs_{algo2}.png"
    canvas.save(out_file)
    print(f"Side-by-side saved: {out_file}")

    return str(out_file)


def generate_html_report(
    image_path: str,
    results: dict,
    output_dir: str = 'dither_output',
) -> str:
    """Generate an HTML report for easy comparison."""
    output_path = Path(output_dir)
    base_name = Path(image_path).stem

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Dithering Comparison: {base_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            margin: 0;
            padding: 20px;
        }}
        h1 {{ color: #00d9ff; margin-bottom: 10px; }}
        .subtitle {{ color: #888; margin-bottom: 30px; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
            gap: 20px;
        }}
        .card {{
            background: #16213e;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }}
        .card img {{
            width: 100%;
            height: auto;
            display: block;
            cursor: pointer;
            transition: transform 0.2s;
        }}
        .card img:hover {{ transform: scale(1.02); }}
        .card-info {{
            padding: 15px;
        }}
        .card-title {{
            font-size: 18px;
            font-weight: 600;
            color: #00d9ff;
            margin-bottom: 5px;
        }}
        .card-desc {{
            font-size: 13px;
            color: #888;
            margin-bottom: 8px;
        }}
        .card-time {{
            font-size: 12px;
            color: #666;
        }}
        .source-card {{
            grid-column: 1 / -1;
            max-width: 850px;
        }}
        .source-card img {{ max-width: 800px; }}
        .palette {{
            display: flex;
            gap: 10px;
            margin: 20px 0;
            padding: 15px;
            background: #16213e;
            border-radius: 8px;
            width: fit-content;
        }}
        .color-swatch {{
            width: 40px;
            height: 40px;
            border-radius: 6px;
            border: 2px solid #333;
        }}
        .fullscreen {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.95);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }}
        .fullscreen img {{
            max-width: 95%;
            max-height: 95%;
        }}
        .fullscreen.active {{ display: flex; }}
    </style>
</head>
<body>
    <h1>Dithering Algorithm Comparison</h1>
    <p class="subtitle">Source: {image_path}</p>

    <h3>6-Color Palette</h3>
    <div class="palette">
"""

    for i, (color, name) in enumerate(zip(PALETTE_RGB, ['Black', 'White', 'Yellow', 'Red', 'Blue', 'Green'])):
        r, g, b = color
        html += f'        <div class="color-swatch" style="background: rgb({r},{g},{b});" title="{name}"></div>\n'

    html += """    </div>

    <h3>Results</h3>
    <div class="grid">
        <div class="card source-card">
            <img src="{base_name}_source.png" alt="Prepared Source" onclick="showFullscreen(this)">
            <div class="card-info">
                <div class="card-title">Original (Prepared)</div>
                <div class="card-desc">Source image resized to 800x480 with LANCZOS resampling</div>
            </div>
        </div>
"""

    for algo_name, (out_path, duration) in results.items():
        algo_info = DITHER_ALGORITHMS[algo_name]
        filename = Path(out_path).name
        html += f"""
        <div class="card">
            <img src="{filename}" alt="{algo_info['name']}" onclick="showFullscreen(this)">
            <div class="card-info">
                <div class="card-title">{algo_info['name']}</div>
                <div class="card-desc">{algo_info['description']}</div>
                <div class="card-time">Processing time: {duration:.2f}s</div>
            </div>
        </div>
"""

    html += """
    </div>

    <div class="fullscreen" onclick="hideFullscreen()">
        <img src="" id="fullscreen-img">
    </div>

    <script>
        function showFullscreen(img) {
            document.getElementById('fullscreen-img').src = img.src;
            document.querySelector('.fullscreen').classList.add('active');
        }
        function hideFullscreen() {
            document.querySelector('.fullscreen').classList.remove('active');
        }
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') hideFullscreen();
        });
    </script>
</body>
</html>
"""

    html_file = output_path / f"{base_name}_report.html"
    html_file.write_text(html.replace('{base_name}', base_name))
    print(f"HTML report saved: {html_file}")

    return str(html_file)


def list_algorithms():
    """Print available algorithms with descriptions."""
    print("\nAvailable Dithering Algorithms:")
    print("=" * 70)
    for name, info in DITHER_ALGORITHMS.items():
        print(f"\n  {name}")
        print(f"    Name: {info['name']}")
        print(f"    {info['description']}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Compare dithering algorithms for 6-color e-ink display',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python compare.py photo.jpg                     # Compare all algorithms
  python compare.py photo.jpg -a atkinson pil_fs  # Compare specific algorithms
  python compare.py photo.jpg --grid              # Generate grid comparison
  python compare.py photo.jpg --html              # Generate HTML report
  python compare.py photo.jpg --side-by-side atkinson floyd_steinberg
  python compare.py --list                        # List available algorithms
        """
    )

    parser.add_argument('image', nargs='?', help='Input image file')
    parser.add_argument('-a', '--algorithms', nargs='+',
                        help='Specific algorithms to compare (default: all)')
    parser.add_argument('-o', '--output', default='dither_output',
                        help='Output directory (default: dither_output)')
    parser.add_argument('--orientation', '-r', type=int, default=0,
                        choices=[0, 90, 180, 270],
                        help='Rotate image (degrees)')
    parser.add_argument('--grid', action='store_true',
                        help='Generate grid comparison image')
    parser.add_argument('--html', action='store_true',
                        help='Generate HTML comparison report')
    parser.add_argument('--side-by-side', nargs=2, metavar=('ALGO1', 'ALGO2'),
                        help='Create side-by-side comparison of two algorithms')
    parser.add_argument('--list', action='store_true',
                        help='List available algorithms')

    args = parser.parse_args()

    if args.list:
        list_algorithms()
        return

    if not args.image:
        parser.error("Image file is required (unless using --list)")

    if not os.path.exists(args.image):
        print(f"Error: File not found: {args.image}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Dithering Comparison Test Suite")
    print(f"{'='*60}\n")

    if args.side_by_side:
        create_side_by_side(
            args.image,
            args.side_by_side[0],
            args.side_by_side[1],
            args.output,
            args.orientation
        )
    elif args.grid:
        create_comparison_grid(
            args.image,
            args.algorithms,
            args.output,
            args.orientation
        )
    else:
        results = run_comparison(
            args.image,
            args.algorithms,
            args.output,
            args.orientation
        )

        if args.html:
            generate_html_report(args.image, results, args.output)

    print(f"\n{'='*60}")
    print(f"Done! Output saved to: {args.output}/")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
