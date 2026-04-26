#!/usr/bin/env python3
import hashlib
import json
import random
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from progress import ProgressBar

HISTORY_FILE = Path(__file__).parent.parent / "photo_history.json"
HISTORY_MAX_AGE_DAYS = 7

CACHE_DIR = Path(tempfile.gettempdir()) / "frame_cache"
CACHE_TTL_SECONDS = 3600

RETRY_DELAYS = (3, 10)


def _urlopen_with_retry(req: Request, timeout: int = 30):
    """urlopen wrapper that retries transient network failures."""
    last_err: Exception | None = None
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            return urlopen(req, timeout=timeout)
        except (URLError, TimeoutError) as e:
            last_err = e
            if attempt < len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt])
    raise last_err


def _cache_get(key: str) -> list[dict] | None:
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > CACHE_TTL_SECONDS:
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _cache_set(key: str, value: list[dict]) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(value))


class PhotoHistory:
    """Track displayed photos to avoid repeats. Clears after 7 days."""

    def __init__(self, path: Path = HISTORY_FILE):
        self.path = path
        self.displayed: set[str] = set()
        self.created_at: datetime | None = None
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._reset()
            return
        try:
            data = json.loads(self.path.read_text())
            self.created_at = datetime.fromisoformat(data.get("created_at", ""))
            if self.created_at.tzinfo is None:
                self.created_at = self.created_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - self.created_at > timedelta(days=HISTORY_MAX_AGE_DAYS):
                print(f"Photo history expired (>{HISTORY_MAX_AGE_DAYS} days), clearing...")
                self._reset()
            else:
                self.displayed = set(data.get("displayed", []))
        except (json.JSONDecodeError, ValueError, KeyError):
            self._reset()

    def _reset(self) -> None:
        self.displayed = set()
        self.created_at = datetime.now(timezone.utc)
        self._save()

    def _save(self) -> None:
        self.path.write_text(json.dumps({
            "created_at": self.created_at.isoformat(),
            "displayed": list(self.displayed),
        }, indent=2))

    def mark_displayed(self, asset_id: str) -> None:
        self.displayed.add(asset_id)
        self._save()

    def filter_new(self, assets: list[dict]) -> list[dict]:
        return [a for a in assets if a.get("id") not in self.displayed]


_history: PhotoHistory | None = None


def get_history() -> PhotoHistory:
    global _history
    if _history is None:
        _history = PhotoHistory()
    return _history


@dataclass
class ImmichClient:
    base_url: str
    api_key: str

    def _request(self, method: str, endpoint: str, data: dict | None = None,
                 show_progress: bool = False, progress_desc: str = "Fetching") -> dict:
        url = f"{self.base_url.rstrip('/')}/api/{endpoint.lstrip('/')}"
        headers = {"x-api-key": self.api_key}
        body = None
        if data is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(data).encode()

        req = Request(url, data=body, headers=headers, method=method)
        with _urlopen_with_retry(req, timeout=30) as resp:
            total_size = resp.headers.get('Content-Length')
            if total_size and show_progress:
                total_size = int(total_size)
                progress = ProgressBar(total_size, desc=progress_desc)
                chunks = bytearray()
                while chunk := resp.read(8192):
                    chunks.extend(chunk)
                    progress.update(len(chunk))
                progress.finish()
                return json.loads(chunks.decode())
            return json.loads(resp.read().decode())

    def get_people(self) -> list[dict]:
        return self._request("GET", "/people")["people"]

    def get_person_id(self, name: str) -> str | None:
        for person in self.get_people():
            if person["name"].lower() == name.lower():
                return person["id"]
        return None

    def search_assets_by_people(self, person_ids: list[str]) -> list[dict]:
        key = "people_" + hashlib.md5("_".join(sorted(person_ids)).encode()).hexdigest()
        cached = _cache_get(key)
        if cached is not None:
            return cached

        items = []
        page = 1
        while True:
            result = self._request("POST", "/search/metadata", {
                "personIds": person_ids,
                "size": 250,
                "page": page,
                "type": "IMAGE",
                "withExif": True,
            })
            batch = result.get("assets", {}).get("items", [])
            items.extend(batch)
            if not batch or not result.get("assets", {}).get("nextPage"):
                break
            page += 1
        _cache_set(key, items)
        return items

    def download_asset(self, asset_id: str, dest: Path, show_progress: bool = True) -> Path:
        url = f"{self.base_url.rstrip('/')}/api/assets/{asset_id}/thumbnail?size=preview"
        req = Request(url, headers={"x-api-key": self.api_key})
        with _urlopen_with_retry(req, timeout=30) as resp:
            total_size = resp.headers.get('Content-Length')
            if total_size and show_progress:
                total_size = int(total_size)
                progress = ProgressBar(total_size, desc="Downloading")
                data = bytearray()
                while chunk := resp.read(8192):
                    data.extend(chunk)
                    progress.update(len(chunk))
                progress.finish()
                dest.write_bytes(bytes(data))
            else:
                dest.write_bytes(resp.read())
        return dest

    def get_album_id(self, name: str) -> str | None:
        for album in self._request("GET", "/albums"):
            if album["albumName"].lower() == name.lower():
                return album["id"]
        return None

    def get_album_assets(self, album_id: str, show_progress: bool = False) -> list[dict]:
        key = f"album_{album_id}"
        cached = _cache_get(key)
        if cached is not None:
            return cached

        album = self._request("GET", f"/albums/{album_id}",
                              show_progress=show_progress, progress_desc="Fetching album")
        assets = album.get("assets", [])
        _cache_set(key, assets)
        return assets


def _is_portrait(asset: dict) -> bool | None:
    """Check if asset displays as portrait, accounting for EXIF orientation."""
    exif = asset.get("exifInfo") or {}
    width = exif.get("exifImageWidth") or 0
    height = exif.get("exifImageHeight") or 0
    if not (width and height):
        return None
    # EXIF orientation 6 and 8 mean 90° rotation (swap dimensions)
    orientation = str(exif.get("orientation") or "1")
    if orientation in ("6", "8"):
        width, height = height, width
    return height > width


def _filter_by_orientation(assets: list[dict], portrait: bool) -> list[dict]:
    """Filter assets by orientation, accounting for EXIF rotation."""
    filtered = []
    no_dimensions = 0
    for asset in assets:
        is_portrait = _is_portrait(asset)
        if is_portrait is not None:
            if is_portrait == portrait:
                filtered.append(asset)
        else:
            no_dimensions += 1
    if no_dimensions:
        print(f"Note: {no_dimensions}/{len(assets)} photos missing dimension data")
    return filtered


def _pick_weighted_random(assets: list[dict]) -> dict:
    """Pick random asset, biased towards favorites (20%) and recently added photos (50%)."""
    if not assets:
        raise ValueError("No assets to choose from")

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    favorites = [a for a in assets if a.get("isFavorite")]
    recent = []
    for asset in assets:
        date_str = asset.get("createdAt", "")
        try:
            if datetime.fromisoformat(date_str.replace("Z", "+00:00")) >= cutoff:
                recent.append(asset)
        except (ValueError, AttributeError):
            pass

    if favorites and random.random() < 0.2:
        return random.choice(favorites)
    if recent and random.random() < 0.5:
        return random.choice(recent)
    return random.choice(assets)


def _download_random_asset(client: ImmichClient, assets: list[dict]) -> Path:
    history = get_history()
    new_assets = history.filter_new(assets)

    if new_assets:
        print(f"Photos: {len(new_assets)} new / {len(assets)} total")
        asset = _pick_weighted_random(new_assets)
    else:
        print(f"All {len(assets)} photos shown, picking from full list")
        asset = _pick_weighted_random(assets)

    dest = Path(tempfile.gettempdir()) / "immich_photo.jpg"
    path = client.download_asset(asset["id"], dest)
    history.mark_displayed(asset["id"])
    return path


def get_random_photo_of_people(client: ImmichClient, names: list[str], orientation: int = 0) -> Path:
    person_ids = [pid for name in names if (pid := client.get_person_id(name))]
    if not person_ids:
        raise ValueError(f"No people found: {names}")

    assets = client.search_assets_by_people(person_ids)

    if not assets:
        raise ValueError(f"No photos found for: {names}")

    portrait = orientation in (90, 270)
    filtered = _filter_by_orientation(assets, portrait)
    if not filtered:
        raise ValueError(f"No {'portrait' if portrait else 'landscape'} photos available")
    return _download_random_asset(client, filtered)


def get_random_photo_from_album(client: ImmichClient, album_name: str, orientation: int = 0) -> Path:
    album_id = client.get_album_id(album_name)
    if not album_id:
        raise ValueError(f"Album not found: {album_name}")

    assets = [a for a in client.get_album_assets(album_id) if a.get("type") == "IMAGE"]
    if not assets:
        raise ValueError(f"No photos in album: {album_name}")

    portrait = orientation in (90, 270)
    filtered = _filter_by_orientation(assets, portrait)
    if not filtered:
        raise ValueError(f"No {'portrait' if portrait else 'landscape'} photos in album: {album_name}")
    return _download_random_asset(client, filtered)
