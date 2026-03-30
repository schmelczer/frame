# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

An e-ink photo frame that runs on a Raspberry Pi Zero 2W. It fetches photos from an Immich server, checks Home Assistant for presence (only displays when someone is home), and renders them on a Waveshare 7.3" 6-color e-Paper display (800x480, ACeP technology with Black/White/Yellow/Red/Blue/Green).

## Deployment

```bash
./sync.sh          # rsync src/ to andras@192.168.0.81:~/frame/
```

On the Pi:
```bash
cd ~/frame
python3 display.py                          # default: photos of Me,Ruby
python3 display.py --album "Album Name"     # from specific album
python3 display.py -o 90                    # portrait mode (90° or 270°)
python3 display.py --saturation 1.5 --contrast 1.1 --gamma 0.85
```

## Architecture

**`src/display.py`** — Entry point. Orchestrates the pipeline:
1. Checks time (skips between midnight–7am)
2. Checks Home Assistant presence (skips if nobody home)
3. Fetches a random photo from Immich (by people or album)
4. Sends to e-ink display driver

**`src/lib/immich.py`** — Immich API client. Key behaviors:
- `PhotoHistory` tracks displayed photos in `photo_history.json` to avoid repeats (resets after 7 days)
- `_pick_weighted_random()` biases selection: 50% chance favorites, 50% chance recent (last 7 days), otherwise random
- Filters photos by orientation (portrait/landscape) based on EXIF data including rotation tags
- Downloads preview-size thumbnails, not originals

**`src/lib/homeassistant.py`** — Simple Home Assistant REST client for presence detection.

**`src/lib/waveshare_epd/epd7in3e.py`** — Modified Waveshare driver. The `getbuffer()` method handles the full image pipeline:
- Center-crops to 800x480 (or 480x800)
- Enhances saturation/contrast/gamma for e-ink (defaults: saturation=1.4, contrast=1.2, gamma=0.9)
- Atkinson dithering to 6-color palette using numba JIT
- Packs into 4-bit-per-pixel buffer (two pixels per byte)

**`src/lib/waveshare_epd/epdconfig.py`** — GPIO/SPI hardware config. **Critical: PWR pin is BCM 27** (not default 18).

**`src/lib/progress.py`** — Simple terminal progress bar.

## Key Constraints

- **Always call `epd.sleep()` after display** — the driver uses a try/finally pattern for this
- **Display refresh takes 12-15 seconds** — the BUSY pin polling handles this
- **No test suite** — this is a hardware project; test by deploying to the Pi
- **Dependencies on Pi**: `python3-pil python3-opencv python3-numba python3-smbus spidev gpiozero`
- **Config via environment variables**: `IMMICH_URL`, `IMMICH_API_KEY`, `HA_URL`, `HA_TOKEN` (with hardcoded defaults in display.py)
- **Uses only stdlib `urllib`** — no requests library; the Immich client uses `urllib.request` directly
- `sys.path.append` is used to add `lib/` to the path from display.py
