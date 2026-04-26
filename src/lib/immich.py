#!/usr/bin/env python3
import json
import random
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request

from net import urlopen_with_retry

HISTORY_FILE = Path(__file__).parent.parent / "photo_history.json"
CACHE_DIR = Path(tempfile.gettempdir()) / "frame_cache"


def _cache_get(key: str) -> list[dict] | None:
    path = CACHE_DIR / f"{key}.json"
    try:
        if time.time() - path.stat().st_mtime > 3600:
            return None
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _cache_set(key: str, value: list[dict]) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(value))


def _load_history() -> tuple[set[str], datetime]:
    """Load (displayed, created_at). Resets if missing/corrupt or older than 7 days."""
    try:
        data = json.loads(HISTORY_FILE.read_text())
        created_at = datetime.fromisoformat(data["created_at"])
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created_at <= timedelta(days=7):
            return set(data.get("displayed", [])), created_at
        print("Photo history expired (>7 days), clearing...")
    except (FileNotFoundError, json.JSONDecodeError, ValueError, KeyError):
        pass
    return set(), datetime.now(timezone.utc)


def _save_history(displayed: set[str], created_at: datetime) -> None:
    HISTORY_FILE.write_text(json.dumps({
        "created_at": created_at.isoformat(),
        "displayed": sorted(displayed),
    }, indent=2))


@dataclass
class ImmichClient:
    base_url: str
    api_key: str

    def __post_init__(self):
        self.base_url = self.base_url.rstrip("/")

    def _request(self, method: str, endpoint: str, data: dict | None = None) -> dict:
        headers = {"x-api-key": self.api_key}
        body = None
        if data is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(data).encode()

        req = Request(f"{self.base_url}/api{endpoint}", data=body, headers=headers, method=method)
        with urlopen_with_retry(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    def get_person_id(self, name: str) -> str | None:
        for person in self._request("GET", "/people")["people"]:
            if person["name"].lower() == name.lower():
                return person["id"]
        return None

    def search_assets_by_people(self, person_ids: list[str]) -> list[dict]:
        key = "people_" + "_".join(sorted(person_ids))
        cached = _cache_get(key)
        if cached is not None:
            return cached

        items = []
        page = 1
        while True:
            assets = self._request("POST", "/search/metadata", {
                "personIds": person_ids,
                "size": 250,
                "page": page,
                "type": "IMAGE",
                "withExif": True,
            }).get("assets", {})
            items.extend(assets.get("items", []))
            if not assets.get("nextPage"):
                break
            page += 1
        _cache_set(key, items)
        return items

    def download_asset(self, asset_id: str, dest: Path) -> Path:
        url = f"{self.base_url}/api/assets/{asset_id}/thumbnail?size=preview"
        req = Request(url, headers={"x-api-key": self.api_key})
        with urlopen_with_retry(req, timeout=30) as resp:
            dest.write_bytes(resp.read())
        return dest

    def get_asset_faces(self, asset_id: str) -> list[dict]:
        """Face boxes for people assigned on this asset.

        Each face has imageWidth, imageHeight, boundingBoxX1/Y1/X2/Y2.
        Unassigned faces are skipped — they're often false positives (posters,
        reflections) and shouldn't drag the crop off the real subjects.
        """
        asset = self._request("GET", f"/assets/{asset_id}")
        faces = []
        for person in asset.get("people") or []:
            faces.extend(person.get("faces") or [])
        return faces

    def get_album_id(self, name: str) -> str | None:
        for album in self._request("GET", "/albums"):
            if album["albumName"].lower() == name.lower():
                return album["id"]
        return None

    def get_album_assets(self, album_id: str) -> list[dict]:
        key = f"album_{album_id}"
        cached = _cache_get(key)
        if cached is not None:
            return cached
        assets = self._request("GET", f"/albums/{album_id}").get("assets", [])
        _cache_set(key, assets)
        return assets


def _filter_by_orientation(assets: list[dict], portrait: bool) -> list[dict]:
    """Keep assets matching the requested orientation. Skips assets without EXIF dimensions."""
    out = []
    for a in assets:
        exif = a.get("exifInfo") or {}
        w = exif.get("exifImageWidth") or 0
        h = exif.get("exifImageHeight") or 0
        if not (w and h):
            continue
        if exif.get("orientation") in (6, 8, "6", "8"):
            w, h = h, w
        if (h > w) == portrait:
            out.append(a)
    return out


def _on_this_day_candidates(assets: list[dict]) -> list[dict]:
    """Photos taken on today's month-day in past years, with a ±3-day fallback."""
    today = datetime.now(timezone.utc).date()
    dated = []
    for a in assets:
        exif = a.get("exifInfo") or {}
        date_str = exif.get("dateTimeOriginal") or a.get("fileCreatedAt")
        if not date_str:
            continue
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        except (ValueError, AttributeError):
            continue
        if dt.year < today.year:
            dated.append((a, dt))

    exact = [a for a, dt in dated if (dt.month, dt.day) == (today.month, today.day)]
    if exact:
        return exact

    nearby_md = set()
    for offset in range(-3, 4):
        d = today + timedelta(days=offset)
        nearby_md.add((d.month, d.day))
    return [a for a, dt in dated if (dt.month, dt.day) in nearby_md]


def _pick_weighted_random(assets: list[dict]) -> dict:
    """Pick random asset, biased towards on-this-day memories, favorites, and recents."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    favorites = [a for a in assets if a.get("isFavorite")]
    recent = []
    for a in assets:
        try:
            if datetime.fromisoformat(a.get("createdAt", "").replace("Z", "+00:00")) >= cutoff:
                recent.append(a)
        except (ValueError, AttributeError):
            pass
    on_this_day = _on_this_day_candidates(assets)

    candidates = [
        ("on this day", on_this_day, 0.10),
        ("favorites", favorites, 0.18),
        ("recent", recent, 0.36),
        ("all", assets, 0.36),
    ]
    active = [(label, pool, w) for label, pool, w in candidates if pool]
    print("Pool sizes: " + ", ".join(f"{label}={len(pool)}" for label, pool, _ in active))
    label, pool, _ = random.choices(active, weights=[w for _, _, w in active])[0]
    print(f"Picked pool: {label} ({len(pool)} candidates)")
    return random.choice(pool)


def _pick_and_download(client: ImmichClient, assets: list[dict],
                       orientation: int, source_label: str) -> tuple[Path, dict]:
    portrait = orientation in (90, 270)
    filtered = _filter_by_orientation(assets, portrait)
    if not filtered:
        raise ValueError(f"No {'portrait' if portrait else 'landscape'} photos in {source_label}")

    displayed, created_at = _load_history()
    candidates = [a for a in filtered if a.get("id") not in displayed]
    if not candidates:
        print(f"All {len(filtered)} photos shown, picking from full list")
        candidates = filtered
    else:
        print(f"Photos: {len(candidates)} new / {len(filtered)} total")

    asset = _pick_weighted_random(candidates)
    dest = Path(tempfile.gettempdir()) / "immich_photo.jpg"
    path = client.download_asset(asset["id"], dest)
    displayed.add(asset["id"])
    _save_history(displayed, created_at)
    return path, asset


def get_random_photo_of_people(client: ImmichClient, names: list[str], orientation: int = 0) -> tuple[Path, dict]:
    person_ids = [pid for name in names if (pid := client.get_person_id(name))]
    if not person_ids:
        raise ValueError(f"No people found: {names}")

    assets = client.search_assets_by_people(person_ids)
    if not assets:
        raise ValueError(f"No photos found for: {names}")

    return _pick_and_download(client, assets, orientation, f"photos for {', '.join(names)}")


def get_random_photo_from_album(client: ImmichClient, album_name: str, orientation: int = 0) -> tuple[Path, dict]:
    album_id = client.get_album_id(album_name)
    if not album_id:
        raise ValueError(f"Album not found: {album_name}")

    assets = [a for a in client.get_album_assets(album_id) if a.get("type") == "IMAGE"]
    if not assets:
        raise ValueError(f"No photos in album: {album_name}")

    return _pick_and_download(client, assets, orientation, f"album: {album_name}")
