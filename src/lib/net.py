#!/usr/bin/env python3
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

RETRY_DELAYS = (3, 10)


def urlopen_with_retry(req: Request, timeout: int = 30):
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
