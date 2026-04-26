#!/usr/bin/env python3
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


def urlopen_with_retry(req: Request, timeout: int = 30):
    """urlopen wrapper that retries transient network failures (3s, 10s backoff)."""
    for delay in (3, 10, None):
        try:
            return urlopen(req, timeout=timeout)
        except (URLError, TimeoutError):
            if delay is None:
                raise
            time.sleep(delay)
