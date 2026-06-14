from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable


def _default_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class FileLogger:
    def __init__(
        self,
        base: str | Path = "logs",
        now: Callable[[], str] = _default_now,
        console: bool = False,
    ):
        self.base = Path(base)
        self.now = now
        self.console = console

    def write(self, category: str, message: str) -> None:
        ts = self.now()
        date = ts[:10].replace("-", "_")
        folder = self.base / category
        folder.mkdir(parents=True, exist_ok=True)
        line = f"[{ts}] {message}"
        with (folder / f"{date}.txt").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        if self.console:
            print(line)
