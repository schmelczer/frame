#!/usr/bin/env python3
import json
from urllib.request import Request

from net import urlopen_with_retry


class HomeAssistantClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def is_person_home(self, entity_id: str) -> bool:
        req = Request(
            f"{self.base_url}/api/states/{entity_id}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        try:
            with urlopen_with_retry(req, timeout=30) as resp:
                return json.loads(resp.read().decode()).get("state") == "home"
        except Exception as e:
            print(f"Failed to check {entity_id}: {e}")
            return False
