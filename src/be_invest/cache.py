"""Simple filesystem cache for fetched resources.

Caches raw bytes keyed by URL hash, with JSON metadata including timestamps,
ETag/Last-Modified, and content hash to support TTL and change detection.
"""
from __future__ import annotations

import json
import time
import hashlib
from pathlib import Path
from typing import Optional, Tuple, Dict, Any


class SimpleCache:
    def __init__(self, base_dir: Path, ttl_seconds: int = 0) -> None:
        self.base_dir = base_dir
        self.ttl_seconds = max(0, int(ttl_seconds))
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def _paths(self, url: str) -> Tuple[Path, Path]:
        k = self._key(url)
        data = self.base_dir / f"{k}.bin"
        meta = self.base_dir / f"{k}.json"
        return data, meta

    def get(self, url: str) -> Optional[bytes]:
        data_path, meta_path = self._paths(url)
        if not data_path.exists() or not meta_path.exists():
            return None

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            ts = float(meta.get("timestamp", 0))
        except Exception:
            return None

        if self.ttl_seconds > 0 and (time.time() - ts) > self.ttl_seconds:
            return None

        try:
            return data_path.read_bytes()
        except Exception:
            return None

    def put(self, url: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> None:
        data_path, meta_path = self._paths(url)
        meta: Dict[str, Any] = {
            "url": url,
            "timestamp": time.time(),
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        if metadata:
            meta.update(metadata)
        data_path.write_bytes(content)
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

