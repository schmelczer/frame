"""Text overlay rendering for the e-ink frame.

Paints aliased white-on-black-stroke text into the dithered palette index
array; black/white survive Atkinson dithering so edges stay crisp on e-ink.
"""

import os
from datetime import UTC, datetime

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
)

PALETTE_BLACK = 0
PALETTE_WHITE = 1


def _load_font(size: int) -> ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def format_age(asset: dict) -> str | None:
    """Photo capture age as 'N days/weeks/months/years ago'."""
    exif = asset.get("exifInfo") or {}
    date_str = exif.get("dateTimeOriginal") or asset.get("fileCreatedAt")
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    days = (datetime.now(UTC) - dt).days
    if days < 0:
        return None
    if days == 0:
        return "Today"
    if days == 1:
        return "Yesterday"
    if days < 7:
        return f"{days} days ago"
    for n, unit in ((12 * 30, "year"), (30, "month"), (7, "week")):
        if days >= n:
            count = max(1, days // n)
            if count == 1:
                return f"A {unit} ago"
            return f"{count} {unit}s ago"


def format_location(asset: dict) -> str | None:
    """Most specific location available from EXIF."""
    exif = asset.get("exifInfo") or {}
    return exif.get("city") or exif.get("state") or exif.get("country") or None


def render_text_into_indices(
    indices: np.ndarray, left_text: str | None, right_text: str | None, orientation: int = 0
) -> None:
    """Paint white-on-black-stroke text into a (height, width) palette-index array.

    Text is laid out viewer-bottom-left/right, then rotated by `orientation`
    so labels land at the viewer's bottom regardless of frame mounting.
    """
    font_size, margin, stroke_width = 20, 18, 2
    buffer_h, buffer_w = indices.shape
    if orientation in (90, 270):
        view_w, view_h = buffer_h, buffer_w
    else:
        view_w, view_h = buffer_w, buffer_h

    fill_layer = Image.new("L", (view_w, view_h), 0)
    full_layer = Image.new("L", (view_w, view_h), 0)
    fill_draw = ImageDraw.Draw(fill_layer)
    full_draw = ImageDraw.Draw(full_layer)
    font = _load_font(font_size)
    baseline = view_h - margin

    if left_text:
        pos = (margin, baseline)
        fill_draw.text(pos, left_text, font=font, fill=255, anchor="lb")
        full_draw.text(
            pos,
            left_text,
            font=font,
            fill=255,
            anchor="lb",
            stroke_width=stroke_width,
            stroke_fill=255,
        )

    if right_text:
        pos = (view_w - margin, baseline)
        fill_draw.text(pos, right_text, font=font, fill=255, anchor="rb")
        full_draw.text(
            pos,
            right_text,
            font=font,
            fill=255,
            anchor="rb",
            stroke_width=stroke_width,
            stroke_fill=255,
        )

    if orientation:
        fill_layer = fill_layer.rotate(orientation, expand=True)
        full_layer = full_layer.rotate(orientation, expand=True)

    fill_mask = np.asarray(fill_layer) >= 128
    stroke_mask = (np.asarray(full_layer) >= 128) & ~fill_mask
    indices[stroke_mask] = PALETTE_BLACK
    indices[fill_mask] = PALETTE_WHITE
