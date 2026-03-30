#!/usr/bin/env python3
import json
from urllib.request import Request, urlopen


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
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    def is_person_home(self, entity_id: str) -> bool:
        try:
            return self.get_state(entity_id).get("state") == "home"
        except Exception as e:
            print(f"Failed to check {entity_id}: {e}")
            return False
