"""Resize-to-cover with face-aware positioning and head-fit checks.

When a portrait source is cropped onto a landscape target, the face joint-span
centre lands on the top third of the crop window instead of the middle, so the
eyes sit on the upper-third line where landscape composition naturally reads.
"""

import math
from dataclasses import dataclass

from PIL import Image

# Face boxes end at the hairline; extend each box upward by this fraction of
# its own height so the joint-span midpoint lands closer to the eyes than the
# bare face centre.
HEAD_EXTENSION = 0.4

# Extra room around the head-extended face box required before a photo is
# accepted for display.
HEAD_SAFETY_MARGIN = 0.08

_FIT_EPSILON = 1e-6


@dataclass(frozen=True)
class CropGeometry:
    """Resize-to-cover geometry used by the face-aware crop."""

    resized_size: tuple[int, int]
    crop_box: tuple[int, int, int, int]
    head_boxes: list[tuple[float, float, float, float]]


def _cover_size(img_w: int, img_h: int, target_w: int, target_h: int) -> tuple[int, int]:
    img_aspect = img_w / img_h
    target_aspect = target_w / target_h
    if img_aspect < target_aspect:
        return target_w, math.ceil(target_w / img_aspect)
    return math.ceil(target_h * img_aspect), target_h


def _head_boxes(
    faces: list[dict], img_w: int, img_h: int, new_w: int, new_h: int
) -> list[tuple[float, float, float, float]]:
    boxes = []
    for f in faces:
        sx = new_w / (f.get("imageWidth") or img_w)
        sy = new_h / (f.get("imageHeight") or img_h)
        x1 = f["boundingBoxX1"] * sx
        y1 = f["boundingBoxY1"] * sy
        x2 = f["boundingBoxX2"] * sx
        y2 = f["boundingBoxY2"] * sy
        face_w = x2 - x1
        face_h = y2 - y1
        x_margin = face_w * HEAD_SAFETY_MARGIN
        y_margin = face_h * HEAD_SAFETY_MARGIN
        boxes.append(
            (
                x1 - x_margin,
                y1 - face_h * HEAD_EXTENSION - y_margin,
                x2 + x_margin,
                y2 + y_margin,
            )
        )
    return boxes


def face_aware_crop_geometry(
    image_size: tuple[int, int], target_w: int, target_h: int, faces: list[dict]
) -> CropGeometry:
    """Return the resize size, crop box, and safety-expanded head boxes."""
    img_w, img_h = image_size
    new_w, new_h = _cover_size(img_w, img_h, target_w, target_h)

    cx, cy = new_w / 2, new_h / 2
    boxes = _head_boxes(faces, img_w, img_h, new_w, new_h) if faces else []
    if boxes:
        cx = (min(b[0] for b in boxes) + max(b[2] for b in boxes)) / 2
        cy = (min(b[1] for b in boxes) + max(b[3] for b in boxes)) / 2

    y_anchor = target_h / 3 if img_h > img_w and target_w > target_h else target_h / 2
    x_off = max(0, min(int(cx - target_w / 2), new_w - target_w))
    y_off = max(0, min(int(cy - y_anchor), new_h - target_h))
    return CropGeometry(
        resized_size=(new_w, new_h),
        crop_box=(x_off, y_off, x_off + target_w, y_off + target_h),
        head_boxes=boxes,
    )


def heads_fit_in_crop_size(
    image_size: tuple[int, int], target_w: int, target_h: int, faces: list[dict]
) -> bool:
    """True when the face-aware crop keeps every visible head area inside."""
    if not faces:
        return True

    geometry = face_aware_crop_geometry(image_size, target_w, target_h, faces)
    new_w, new_h = geometry.resized_size
    crop_x1, crop_y1, crop_x2, crop_y2 = geometry.crop_box
    return all(
        max(0, head_x1) >= crop_x1 - _FIT_EPSILON
        and max(0, head_y1) >= crop_y1 - _FIT_EPSILON
        and min(new_w, head_x2) <= crop_x2 + _FIT_EPSILON
        and min(new_h, head_y2) <= crop_y2 + _FIT_EPSILON
        for head_x1, head_y1, head_x2, head_y2 in geometry.head_boxes
    )


def heads_fit_in_crop(image: Image.Image, target_w: int, target_h: int, faces: list[dict]) -> bool:
    """True when `face_aware_crop` would keep all heads inside the output frame."""
    return heads_fit_in_crop_size(image.size, target_w, target_h, faces)


def face_aware_crop(
    image: Image.Image, target_w: int, target_h: int, faces: list[dict]
) -> Image.Image:
    """Resize to cover (target_w, target_h), then crop biased toward face boxes.

    Joint-span midpoint of the head-extended boxes sets the crop centre. For
    portrait sources rendered on a landscape target, the centre is placed at
    the top third of the crop window (rule of thirds) instead of the middle.
    Plain centre crop when no faces.
    """
    geometry = face_aware_crop_geometry(image.size, target_w, target_h, faces)
    new_w, new_h = geometry.resized_size
    resized = image.resize((new_w, new_h), Image.LANCZOS)
    return resized.crop(geometry.crop_box)
