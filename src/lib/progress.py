"""Simple terminal progress bar for e-ink frame."""

import sys


class ProgressBar:
    """Simple text-based progress bar."""

    def __init__(self, total: int, desc: str = "", width: int = 30):
        self.total = total
        self.current = 0
        self.desc = desc
        self.width = width
        self._last_percent = -1

    def update(self, n: int = 1) -> None:
        """Update progress by n steps."""
        self.current = min(self.current + n, self.total)
        self._render()

    def set(self, value: int) -> None:
        """Set progress to specific value."""
        self.current = min(value, self.total)
        self._render()

    def _render(self) -> None:
        if self.total == 0:
            return

        percent = int(100 * self.current / self.total)
        if percent == self._last_percent:
            return
        self._last_percent = percent

        filled = int(self.width * self.current / self.total)
        bar = "█" * filled + "░" * (self.width - filled)

        desc = f"{self.desc}: " if self.desc else ""
        sys.stdout.write(f"\r{desc}|{bar}| {percent:3d}%")
        sys.stdout.flush()

        if self.current >= self.total:
            sys.stdout.write("\n")
            sys.stdout.flush()

    def finish(self) -> None:
        """Complete the progress bar."""
        self.current = self.total
        self._render()


def print_status(msg: str) -> None:
    """Print a status message."""
    print(f"  {msg}")
