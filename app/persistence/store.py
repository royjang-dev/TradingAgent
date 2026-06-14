from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class JsonStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.bak = self.path.with_suffix(self.path.suffix + ".bak")

    def load(self, default: Any = None) -> Any:
        if not self.path.exists():
            return default
        text = self.path.read_text(encoding="utf-8-sig").strip()  # utf-8-sig tolerates a BOM
        return json.loads(text) if text else default

    def save(self, data: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.bak.write_text(self.path.read_text(encoding="utf-8"), encoding="utf-8")
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
