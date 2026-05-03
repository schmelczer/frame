"""Resize-to-cover then crop, biased toward Immich-detected face boxes."""

import math

from PIL import Image

# Face boxes end at the hairline; extend each box upward by this fraction of
# its own height so the fit-check considers the head, not just the face.
HEAD_EXTENSION = 0.4


def face_aware_crop(
    image: Image.Image, target_w: int, target_h: int, faces: list[dict]
) -> Image.Image:
    """Resize to cover (target_w, target_h), then crop to keep faces in frame.

    Each face dict has imageWidth/imageHeight (the coord-space dims) and
    boundingBoxX1/Y1/X2/Y2. Per axis: if every (head-extended) face fits in
    the crop we centre on the joint span so all faces are included with hair
    clearance on top. If the span doesn't fit, we fall back to the
    area-weighted centroid of the unextended boxes — that biases toward the
    biggest, presumably foreground, face. Plain center crop when no faces.
    """
    img_w, img_h = image.size
    img_aspect = img_w / img_h
    target_aspect = target_w / target_h
    if img_aspect < target_aspect:
        new_w = target_w
        new_h = math.ceil(target_w / img_aspect)
    else:
        new_w = math.ceil(target_h * img_aspect)
        new_h = target_h

    resized = image.resize((new_w, new_h), Image.LANCZOS)

    cx, cy = new_w / 2, new_h / 2
    if faces:
        boxes = []
        for f in faces:
            sx = new_w / (f.get("imageWidth") or img_w)
            sy = new_h / (f.get("imageHeight") or img_h)
            x1 = f["boundingBoxX1"] * sx
            y1 = f["boundingBoxY1"] * sy
            x2 = f["boundingBoxX2"] * sx
            y2 = f["boundingBoxY2"] * sy
            area = max(0.0, (x2 - x1) * (y2 - y1))
            boxes.append((x1, y1, x2, y2, area))

        x_lo = min(b[0] for b in boxes)
        x_hi = max(b[2] for b in boxes)
        cx = (x_lo + x_hi) / 2 if x_hi - x_lo <= target_w else _weighted_center(boxes, 0, 2)

        y_lo_ext = min(b[1] - (b[3] - b[1]) * HEAD_EXTENSION for b in boxes)
        y_hi = max(b[3] for b in boxes)
        cy = (y_lo_ext + y_hi) / 2 if y_hi - y_lo_ext <= target_h else _weighted_center(boxes, 1, 3)

    x_off = max(0, min(int(cx - target_w / 2), new_w - target_w))
    y_off = max(0, min(int(cy - target_h / 2), new_h - target_h))
    return resized.crop((x_off, y_off, x_off + target_w, y_off + target_h))


def _weighted_center(boxes: list[tuple], lo: int, hi: int) -> float:
    total = sum(b[4] for b in boxes) or 1.0
    return sum((b[lo] + b[hi]) / 2 * b[4] for b in boxes) / total
