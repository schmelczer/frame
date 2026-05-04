"""Shared helpers for the frame project notebooks.

Each notebook should call `bootstrap()` first. It puts `src/lib/` on the import
path and stubs `waveshare_epd.epdconfig` so the production helpers can be
imported without trying to claim GPIO pins.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parent.parent
PHOTOS_DIR = REPO / "photos"
FACES_FILE = PHOTOS_DIR / "faces.json"


def bootstrap() -> None:
    """Make production lib + the migrated dither module importable, off-Pi safe."""
    for p in (REPO / "src" / "lib", REPO / "notebooks"):
        sp = str(p)
        if sp not in sys.path:
            sys.path.insert(0, sp)
    sys.modules.setdefault("waveshare_epd.epdconfig", ModuleType("waveshare_epd.epdconfig"))


def center_crop(image, target_w: int, target_h: int):
    """Resize-to-cover then centre-crop. Used as the baseline in crop_compare."""
    import math

    from PIL import Image

    iw, ih = image.size
    if iw / ih < target_w / target_h:
        new_w, new_h = target_w, math.ceil(target_w * ih / iw)
    else:
        new_w, new_h = math.ceil(target_h * iw / ih), target_h
    resized = image.resize((new_w, new_h), Image.LANCZOS)
    x = max(0, (new_w - target_w) // 2)
    y = max(0, (new_h - target_h) // 2)
    return resized.crop((x, y, x + target_w, y + target_h))


def local_pool(
    filter_fn: Callable[[dict], bool] | None = None,
) -> list[dict]:
    """Pool of bundled CC-licensed photos under photos/.

    Face boxes from photos/faces.json are attached as `_faces` when present.
    """
    from PIL import Image

    faces_by_filename = {}
    if FACES_FILE.exists():
        raw = json.loads(FACES_FILE.read_text())
        faces_by_filename = {k: v for k, v in raw.items() if not k.startswith("_")}

    out = []
    for path in sorted(PHOTOS_DIR.glob("*.jpg")):
        if path.name == "frame.jpg":
            continue
        with Image.open(path) as im:
            w, h = im.size
        out.append(
            {
                "id": path.stem,
                "originalFileName": path.name,
                "_local_path": str(path),
                "_faces": faces_by_filename.get(path.name, []),
                "exifInfo": {"exifImageWidth": w, "exifImageHeight": h},
            }
        )
    if filter_fn is not None:
        out = [a for a in out if filter_fn(a)]
    return out


def image_faces(asset: dict) -> list[dict]:
    """Face boxes attached to a bundled photo asset."""
    return asset.get("_faces", [])


def open_image(asset: dict):
    """Open a bundled photo asset as PIL RGB."""
    from PIL import Image

    return Image.open(asset["_local_path"]).convert("RGB")


@contextlib.contextmanager
def silenced():
    """Suppress the production code's print() chatter during batch loops."""
    with contextlib.redirect_stdout(io.StringIO()):
        yield
