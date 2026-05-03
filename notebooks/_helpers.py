"""Shared helpers for the frame project notebooks.

Each notebook should call `bootstrap()` first — it puts `src/lib/` on the import
path and stubs `waveshare_epd.epdconfig` so the production helpers can be
imported without trying to claim GPIO pins.
"""

from __future__ import annotations

import contextlib
import io
import os
import random
import sys
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(tempfile.gettempdir()) / "frame_notebook"

DEFAULT_PEOPLE = ("Me", "Ruby")
DEFAULT_IMMICH_URL = "https://immich.example.com"
DEFAULT_IMMICH_API_KEY = "REDACTED_IMMICH_API_KEY"


def bootstrap() -> None:
    """Make production lib + the migrated dither module importable, off-Pi safe."""
    for p in (REPO / "src" / "lib", REPO / "notebooks"):
        sp = str(p)
        if sp not in sys.path:
            sys.path.insert(0, sp)
    sys.modules.setdefault("waveshare_epd.epdconfig", ModuleType("waveshare_epd.epdconfig"))


def immich_client():
    from immich import ImmichClient

    return ImmichClient(
        os.environ.get("IMMICH_URL", DEFAULT_IMMICH_URL),
        os.environ.get("IMMICH_API_KEY", DEFAULT_IMMICH_API_KEY),
    )


def is_landscape(asset: dict) -> bool:
    exif = asset.get("exifInfo") or {}
    w, h = exif.get("exifImageWidth") or 0, exif.get("exifImageHeight") or 0
    if exif.get("orientation") in (6, 8, "6", "8"):
        w, h = h, w
    return w > h > 0


def fetch_pool(
    client,
    names: Iterable[str] = DEFAULT_PEOPLE,
    pool_size: int = 500,
    seed: int = 7,
    filter_fn: Callable[[dict], bool] = is_landscape,
) -> list[dict]:
    person_ids = [pid for n in names if (pid := client.get_person_id(n))]
    if not person_ids:
        raise ValueError(f"no people found: {list(names)}")
    assets = client.search_assets_by_people(person_ids)
    filtered = [a for a in assets if filter_fn(a)]
    rng = random.Random(seed)
    return rng.sample(filtered, min(pool_size, len(filtered)))


def download_image(client, asset: dict):
    """Download (cached) and open as PIL RGB Image."""
    from PIL import Image

    CACHE_DIR.mkdir(exist_ok=True)
    dest = CACHE_DIR / f"{asset['id']}.jpg"
    if not dest.exists():
        client.download_asset(asset["id"], dest)
    return Image.open(dest).convert("RGB")


@contextlib.contextmanager
def silenced():
    """Suppress the production code's print() chatter during batch loops."""
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def show_grid(
    rows: list[list], titles: list[list[str]], figsize_scale=(4.4, 3.0), suptitle: str | None = None
):
    """Render a 2-D image grid with matplotlib. `rows` is list-of-lists of PIL/np images."""
    import matplotlib.pyplot as plt

    n_rows, n_cols = len(rows), max(len(r) for r in rows)
    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=(figsize_scale[0] * n_cols, figsize_scale[1] * n_rows)
    )
    if n_rows == 1:
        axes = [axes] if n_cols == 1 else [list(axes)]
    elif n_cols == 1:
        axes = [[ax] for ax in axes]
    for i, (row, row_titles) in enumerate(zip(rows, titles, strict=True)):
        for j in range(n_cols):
            ax = axes[i][j]
            if j < len(row) and row[j] is not None:
                ax.imshow(row[j])
                ax.set_title(row_titles[j], fontsize=10)
            ax.axis("off")
    if suptitle:
        fig.suptitle(suptitle, fontsize=12)
    plt.tight_layout()
    return fig
