from __future__ import annotations

import gzip
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class SnapshotRef:
    sha256_hex: str
    relative_path: str
    compression: str
    byte_size: int
    text_length: int
    content_type: str
    newly_written: bool


class RawSnapshotStore:
    def __init__(self, data_dir: str | Path) -> None:
        self._root = Path(data_dir).expanduser().resolve() / "raw"
        self._root.mkdir(parents=True, exist_ok=True)

    def store_text(
        self,
        *,
        category: str,
        url: str,
        text: str,
        content_type: str = "text/html; charset=utf-8",
    ) -> SnapshotRef:
        payload = text.encode("utf-8")
        digest = sha256(payload).hexdigest()
        relative_path = Path(category) / digest[:2] / f"{digest}.gz"
        absolute_path = self._root / relative_path
        newly_written = False
        if not absolute_path.exists():
            absolute_path.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(absolute_path, "wb", compresslevel=6) as handle:
                handle.write(payload)
            newly_written = True

        return SnapshotRef(
            sha256_hex=digest,
            relative_path=str(relative_path).replace("\\", "/"),
            compression="gzip",
            byte_size=len(payload),
            text_length=len(text),
            content_type=content_type,
            newly_written=newly_written,
        )

    def read_text(self, *, category: str, sha256_hex: str) -> str:
        relative_path = Path(category) / sha256_hex[:2] / f"{sha256_hex}.gz"
        absolute_path = self._root / relative_path
        if not absolute_path.exists():
            raise FileNotFoundError(str(relative_path))
        with gzip.open(absolute_path, "rt", encoding="utf-8") as handle:
            return handle.read()
