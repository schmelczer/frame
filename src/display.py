#!/usr/bin/env python3
import argparse
import fcntl
import os
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image

sys.path.append(str(Path(__file__).parent / "lib"))
from immich import ImmichClient, get_random_photo_of_people, get_random_photo_from_album
from homeassistant import HomeAssistantClient
from overlay import format_age, format_location
# waveshare_epd is imported lazily after the lock — its epdconfig claims
# GPIO pins at import time, so two overlapping invocations would both crash
# on "GPIO busy" before reaching the flock below.

IMMICH_URL = os.environ.get("IMMICH_URL", "https://immich.example.com")
IMMICH_API_KEY = os.environ.get("IMMICH_API_KEY", "REDACTED_IMMICH_API_KEY")

HA_URL = os.environ.get("HA_URL", "https://homeassistant.example.com")
HA_TOKEN = os.environ.get("HA_TOKEN", "REDACTED_HA_TOKEN")
HA_PRESENCE_ENTITIES = ["person.andras", "person.ruby"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Display image on e-ink frame")
    parser.add_argument("--people", default="Me,Ruby",
                        help="Comma-separated names for Immich search")
    parser.add_argument("--album", help="Fetch from album (overrides --people)")
    parser.add_argument("-o", "--orientation", type=int, choices=[0, 90, 180, 270],
                        default=0, help="Rotation in degrees")
    parser.add_argument("--saturation", type=float, default=1.3)
    parser.add_argument("--contrast", type=float, default=1.05)
    parser.add_argument("--gamma", type=float, default=0.90)
    args = parser.parse_args()

    lock_fd = open("/tmp/frame.lock", "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Another instance running, skipping")
        sys.exit(0)

    from waveshare_epd import epd7in3e

    now = datetime.now()
    print(f"Time: {now.strftime('%H:%M')}")
    if 0 <= now.hour < 7:
        print("Night time, skipping")
        sys.exit(0)

    ha = HomeAssistantClient(HA_URL, HA_TOKEN)
    home = [e.split(".")[-1].title() for e in HA_PRESENCE_ENTITIES if ha.is_person_home(e)]
    if not home:
        print("No one home, skipping")
        sys.exit(0)
    print(f"Home: {', '.join(home)}")

    client = ImmichClient(IMMICH_URL, IMMICH_API_KEY)
    if args.album:
        image_path, asset = get_random_photo_from_album(client, args.album, args.orientation)
        print(f"Album: {args.album}")
    else:
        names = [n.strip() for n in args.people.split(",")]
        image_path, asset = get_random_photo_of_people(client, names, args.orientation)
        print(f"People: {', '.join(names)}")

    left_text = format_age(asset)
    right_text = format_location(asset)
    if left_text or right_text:
        print(f"Overlay: {left_text or '-'} | {right_text or '-'}")

    try:
        epd = epd7in3e.EPD()
        try:
            epd.init()
            img = Image.open(image_path).convert("RGB")
            if args.orientation:
                img = img.rotate(args.orientation, expand=True)
            buf = epd.getbuffer(img, saturation=args.saturation, contrast=args.contrast,
                                gamma=args.gamma, left_text=left_text, right_text=right_text,
                                orientation=args.orientation)
            epd.display(buf)
        finally:
            epd.sleep()
    finally:
        image_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
