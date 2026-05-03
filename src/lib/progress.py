"""Simple terminal progress bar for e-ink frame."""

import sys


class ProgressBar:
    def __init__(self, total: int, desc: str = ""):
        self.total = total
        self.desc = desc
        self._last_percent = -1
        self._is_tty = sys.stdout.isatty()

    def set(self, value: int) -> None:
        if self.total == 0:
            return
        value = min(value, self.total)
        percent = int(100 * value / self.total)
        if percent == self._last_percent:
            return
        # In non-tty (cron log) mode, only emit a few milestones — no \r spam.
        if not self._is_tty and percent not in (25, 50, 75, 100):
            return
        self._last_percent = percent

        prefix = f"{self.desc}: " if self.desc else ""
        if self._is_tty:
            filled = int(30 * value / self.total)
            bar = "█" * filled + "░" * (30 - filled)
            end = "\n" if value >= self.total else ""
            print(f"\r{prefix}|{bar}| {percent:3d}%", end=end, flush=True)
        else:
            print(f"{prefix}{percent}%", flush=True)
