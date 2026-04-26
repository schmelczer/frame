#!/usr/bin/env python3
import argparse
import fcntl
import os
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.append(str(Path(__file__).parent / "lib"))
from waveshare_epd import epd7in3e
from immich import ImmichClient, get_random_photo_of_people, get_random_photo_from_album
from homeassistant import HomeAssistantClient

LOCK_FILE = "/tmp/frame.lock"

IMMICH_URL = os.environ.get("IMMICH_URL", "https://immich.example.com")
IMMICH_API_KEY = os.environ.get("IMMICH_API_KEY", "REDACTED_IMMICH_API_KEY")

HA_URL = os.environ.get("HA_URL", "https://homeassistant.example.com")
HA_TOKEN = os.environ.get("HA_TOKEN", "REDACTED_HA_TOKEN")
HA_PRESENCE_ENTITIES = ["person.andras", "person.ruby"]

DEFAULT_SATURATION = 1.3
DEFAULT_CONTRAST = 1.05
DEFAULT_GAMMA = 0.90

def display_image(image_path: Path, orientation: int, saturation: float,
                  contrast: float, gamma: float, enhance: bool) -> None:
    epd = epd7in3e.EPD()
    try:
        epd.init()
        img = Image.open(image_path).convert("RGB")
        if orientation:
            img = img.rotate(orientation, expand=True)
        buf = epd.getbuffer(img, saturation=saturation, contrast=contrast,
                            gamma=gamma, enhance=enhance)
        epd.display(buf)
    finally:
        epd.sleep()


def main() -> None:
    parser = argparse.ArgumentParser(description="Display image on e-ink frame")
    parser.add_argument("--people", default="Me,Ruby",
                        help="Comma-separated names for Immich search")
    parser.add_argument("--album", help="Fetch from album (overrides --people)")
    parser.add_argument("-o", "--orientation", type=int, choices=[0, 90, 180, 270],
                        default=0, help="Rotation in degrees")
    parser.add_argument("--saturation", type=float, default=DEFAULT_SATURATION)
    parser.add_argument("--contrast", type=float, default=DEFAULT_CONTRAST)
    parser.add_argument("--gamma", type=float, default=DEFAULT_GAMMA)
    parser.add_argument("--no-enhance", action="store_true")
    args = parser.parse_args()

    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Another instance running, skipping")
        sys.exit(0)

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
        image_path = get_random_photo_from_album(client, args.album, args.orientation)
        print(f"Album: {args.album}")
    else:
        names = [n.strip() for n in args.people.split(",")]
        image_path = get_random_photo_of_people(client, names, args.orientation)
        print(f"People: {', '.join(names)}")

    try:
        display_image(image_path, args.orientation, args.saturation,
                      args.contrast, args.gamma, not args.no_enhance)
    finally:
        image_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
