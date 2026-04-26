"""Simple terminal progress bar for e-ink frame."""


class ProgressBar:
    def __init__(self, total: int, desc: str = ""):
        self.total = total
        self.desc = desc
        self._last_percent = -1

    def set(self, value: int) -> None:
        if self.total == 0:
            return
        value = min(value, self.total)
        percent = int(100 * value / self.total)
        if percent == self._last_percent:
            return
        self._last_percent = percent

        filled = int(30 * value / self.total)
        bar = "█" * filled + "░" * (30 - filled)
        end = "\n" if value >= self.total else ""
        prefix = f"{self.desc}: " if self.desc else ""
        print(f"\r{prefix}|{bar}| {percent:3d}%", end=end, flush=True)
