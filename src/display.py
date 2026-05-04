#!/usr/bin/env python3
import argparse
import fcntl
import os
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image

sys.path.append(str(Path(__file__).parent / "lib"))
from crop import face_aware_crop
from env import load_env, require
from homeassistant import HomeAssistantClient
from immich import ImmichClient, get_random_photo_from_album, get_random_photo_of_people
from overlay import format_age, format_location

# waveshare_epd is imported lazily only when a render will actually happen.
# Its epdconfig claims GPIO pins at import time, so skip paths should not touch it.


def _parse_presence(spec: str) -> list[str]:
    """Parse comma-separated Home Assistant entity IDs."""
    return [entity_id.strip() for entity_id in spec.split(",") if entity_id.strip()]


def main() -> None:
    load_env()
    immich_url = require("IMMICH_URL")
    immich_api_key = require("IMMICH_API_KEY")
    ha_url = require("HA_URL")
    ha_token = require("HA_TOKEN")
    ha_presence = _parse_presence(require("HA_PRESENCE"))

    parser = argparse.ArgumentParser(description="Display image on e-ink frame")
    parser.add_argument(
        "--people",
        default=os.environ.get("IMMICH_PEOPLE", ""),
        help="Comma-separated names for Immich search (default from IMMICH_PEOPLE env var)",
    )
    parser.add_argument("--album", help="Fetch from album (overrides --people)")
    parser.add_argument(
        "-o",
        "--orientation",
        type=int,
        choices=[0, 90, 180, 270],
        default=0,
        help="Rotation in degrees",
    )
    parser.add_argument("--saturation", type=float, default=1.3)
    parser.add_argument("--contrast", type=float, default=1.05)
    parser.add_argument("--gamma", type=float, default=0.90)
    args = parser.parse_args()

    lock_fd = open("/tmp/frame.lock", "w")  # noqa: SIM115 — held for process lifetime
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Another instance running, skipping")
        sys.exit(0)

    now = datetime.now()
    print(f"Time: {now.strftime('%H:%M')}")
    if now.hour < 7:
        print("Night time, skipping")
        sys.exit(0)

    ha = HomeAssistantClient(ha_url, ha_token)
    home = [entity_id for entity_id in ha_presence if ha.is_person_home(entity_id)]
    if not home:
        print("No one home, skipping")
        sys.exit(0)
    print(f"Home: {', '.join(home)}")

    client = ImmichClient(immich_url, immich_api_key)
    if args.album:
        image_path, asset = get_random_photo_from_album(client, args.album, args.orientation)
        print(f"Album: {args.album}")
    else:
        names = [n.strip() for n in args.people.split(",") if n.strip()]
        if not names:
            sys.exit("Specify --people or --album, or set IMMICH_PEOPLE in .env")
        image_path, asset = get_random_photo_of_people(client, names, args.orientation)
        print(f"People: {', '.join(names)}")

    asset_id = asset.get("id")
    print(f"Immich image: {client.base_url}/photos/{asset_id}")
    left_text = format_age(asset)
    right_text = format_location(asset)
    if left_text or right_text:
        print(f"Overlay: {left_text or '-'} | {right_text or '-'}")

    try:
        from waveshare_epd import epd7in3e

        epd = epd7in3e.EPD()
        try:
            epd.init()
            img = Image.open(image_path).convert("RGB")
            faces = client.get_asset_faces(asset["id"])
            print(f"Faces: {len(faces)}")
            target_w, target_h = (480, 800) if args.orientation in (90, 270) else (800, 480)
            img = face_aware_crop(img, target_w, target_h, faces)
            if args.orientation:
                img = img.rotate(args.orientation, expand=True)
            buf = epd.getbuffer(
                img,
                saturation=args.saturation,
                contrast=args.contrast,
                gamma=args.gamma,
                left_text=left_text,
                right_text=right_text,
                orientation=args.orientation,
            )
            epd.display(buf)
        finally:
            epd.sleep()
    finally:
        image_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
