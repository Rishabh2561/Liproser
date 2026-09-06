from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put_pdf(self, content: bytes) -> tuple[str, str]:
        digest = hashlib.sha256(content).hexdigest()
        target = (self.root / f"{uuid4()}.pdf").resolve()
        if self.root not in target.parents:
            raise ValueError("Unsafe storage path")
        target.write_bytes(content)
        return str(target), digest

    def delete(self, stored_path: str) -> None:
        target = Path(stored_path).resolve()
        if self.root not in target.parents:
            raise ValueError("Unsafe storage path")
        target.unlink(missing_ok=True)
