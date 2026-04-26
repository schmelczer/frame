#!/usr/bin/env python3
import json
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

RETRY_DELAYS = (3, 10)


class HomeAssistantClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def get_state(self, entity_id: str) -> dict:
        url = f"{self.base_url}/api/states/{entity_id}"
        req = Request(url, headers={
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        })
        last_err: Exception | None = None
        for attempt in range(len(RETRY_DELAYS) + 1):
            try:
                with urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode())
            except (URLError, TimeoutError) as e:
                last_err = e
                if attempt < len(RETRY_DELAYS):
                    time.sleep(RETRY_DELAYS[attempt])
        raise last_err

    def is_person_home(self, entity_id: str) -> bool:
        try:
            return self.get_state(entity_id).get("state") == "home"
        except Exception as e:
            print(f"Failed to check {entity_id}: {e}")
            return False
