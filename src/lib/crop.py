"""Resize-to-cover with face-aware positioning.

When a portrait source is cropped onto a landscape target, the face joint-span
centre lands on the top third of the crop window instead of the middle, so the
eyes sit on the upper-third line where landscape composition naturally reads.
"""

import math

from PIL import Image

# Face boxes end at the hairline; extend each box upward by this fraction of
# its own height so the joint-span midpoint lands closer to the eyes than the
# bare face centre.
HEAD_EXTENSION = 0.4


def face_aware_crop(
    image: Image.Image, target_w: int, target_h: int, faces: list[dict]
) -> Image.Image:
    """Resize to cover (target_w, target_h), then crop biased toward face boxes.

    Joint-span midpoint of the head-extended boxes sets the crop centre. For
    portrait sources rendered on a landscape target, the centre is placed at
    the top third of the crop window (rule of thirds) instead of the middle.
    Plain centre crop when no faces.
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
            boxes.append((x1, y1, x2, y2))
        cx = (min(b[0] for b in boxes) + max(b[2] for b in boxes)) / 2
        y_lo_ext = min(b[1] - (b[3] - b[1]) * HEAD_EXTENSION for b in boxes)
        y_hi = max(b[3] for b in boxes)
        cy = (y_lo_ext + y_hi) / 2

    y_anchor = target_h / 3 if img_h > img_w and target_w > target_h else target_h / 2
    x_off = max(0, min(int(cx - target_w / 2), new_w - target_w))
    y_off = max(0, min(int(cy - y_anchor), new_h - target_h))
    return resized.crop((x_off, y_off, x_off + target_w, y_off + target_h))
