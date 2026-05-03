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
- `_load_history()` / `_save_history()` track displayed photos in `photo_history.json` to avoid repeats (resets after 7 days). Asset is only marked displayed after a successful download.
- `_pick_weighted_random()` picks a pool first, then a uniform random asset from it. Weights: on-this-day 0.30 (or 0.10 for the ±3-day fallback), favorites 0.18, recent-30-days 0.36, all 0.36. Empty pools are dropped before sampling.
- Filters photos by orientation (portrait/landscape) based on EXIF data including rotation tags. Raises if nothing matches the requested orientation.
- Downloads preview-size thumbnails, not originals
- Asset lists (people-search and album) are cached on disk in `/tmp/frame_cache/` for 1 hour
- `urlopen` calls retry transient failures twice (3s, 10s backoff)

**`src/lib/homeassistant.py`** — Simple Home Assistant REST client for presence detection.

**`src/lib/waveshare_epd/epd7in3e.py`** — Modified Waveshare driver. The `getbuffer()` method handles the full image pipeline:
- Falls back to a face-less center crop via `face_aware_crop` if the input isn't already at target size
- Enhances saturation/contrast/gamma for e-ink (caller passes values; CLI defaults live in `display.py`: saturation=1.3, contrast=1.05, gamma=0.90)
- Atkinson dithering to 6-color palette using numba JIT; produces palette indices directly (no Pillow quantize round-trip)
- Packs into 4-bit-per-pixel buffer (two pixels per byte) and returns `bytes`

**`src/lib/waveshare_epd/epdconfig.py`** — GPIO/SPI hardware config. **Critical: PWR pin is BCM 27** (not default 18).

**`src/lib/progress.py`** — Simple terminal progress bar.

**`notebooks/`** — Off-Pi observable comparisons covering pipeline stages. Run via the
uv-managed env (`uv run jupyter lab notebooks/...`). The notebooks share `_helpers.py`
(bootstrap, Immich client, pool fetch, image cache) and `_dither.py` (migrated from the
former `dither_test/`):
- `crop_compare.ipynb` — face-aware crop vs. centre crop on the most-divergent picks
- `dither_compare.ipynb` — error-diffusion + ordered dithering algorithms with timing

## Key Constraints

- **Always call `epd.sleep()` after display** — the driver uses a try/finally pattern for this
- **Display refresh takes 12-15 seconds** — the BUSY pin polling handles this
- **No test suite** — this is a hardware project; test by deploying to the Pi
- **Dependencies on Pi**: `python3-pil python3-numba python3-smbus spidev gpiozero`
- **Config via environment variables**: `IMMICH_URL`, `IMMICH_API_KEY`, `HA_URL`, `HA_TOKEN` (with hardcoded defaults in display.py)
- **Uses only stdlib `urllib`** — no requests library; the Immich client uses `urllib.request` directly
- **Single-instance lock** at `/tmp/frame.lock` (fcntl) — overlapping cron runs exit cleanly
- `sys.path.append` is used to add `lib/` to the path from display.py
