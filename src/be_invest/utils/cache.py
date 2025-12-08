"""
File-based cache with TTL support for LLM calls and news scraping.
"""

import hashlib
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FileCache:
    """
    Simple file-based cache with TTL.

    Usage:
        cache = FileCache(Path('data/cache'))
        key = FileCache.make_key('url', url)
        blob = cache.get(key, ttl=86400)
        if not blob:
            blob = {'content': fetched_bytes_or_str, 'meta': {...}}
            cache.set(key, blob)
    """

    def __init__(self, cache_dir: Optional[Path | str] = "data/cache", default_ttl: int = 24 * 3600):
        self.cache_dir = Path(cache_dir) if cache_dir else Path("data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = int(default_ttl)
        logger.info(f"📦 FileCache initialized: {self.cache_dir} (TTL: {default_ttl}s)")

    @staticmethod
    def make_key(*args, **kwargs) -> str:
        """
        Deterministic key from args/kwargs. Use this for URLs, prompts, selectors, etc.
        """
        m = hashlib.sha256()
        for a in args:
            m.update(str(a).encode("utf-8"))
            m.update(b"\x00")
        # sort kwargs for deterministic ordering
        for k in sorted(kwargs.keys()):
            m.update(f"{k}={kwargs[k]}".encode("utf-8"))
            m.update(b"\x00")
        return m.hexdigest()

    def _path_for_key(self, key: str) -> Path:
        """Store nested to avoid too many files in one dir."""
        return self.cache_dir / key[:2] / f"{key}.json"

    def get(self, key: str, ttl: Optional[int] = None) -> Any:
        """
        Return cached object or None if not found/expired.
        Stored format: {"ts": epoch_seconds, "value": <json-serializable>}
        """
        ttl = int(ttl) if ttl is not None else self.default_ttl
        p = self._path_for_key(key)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "ts" not in data or "value" not in data:
                return None
            age = time.time() - float(data["ts"])
            if age > ttl:
                logger.debug(f"♻️  Cache expired for {key[:8]}... (age: {age:.0f}s > {ttl}s)")
                try:
                    p.unlink()
                except Exception:
                    pass
                return None
            logger.debug(f"✅ Cache hit for {key[:8]}... (age: {age:.0f}s)")
            return data["value"]
        except Exception as e:
            # corrupt file -> remove and miss
            logger.warning(f"⚠️  Corrupt cache file {p.name}: {e}")
            try:
                p.unlink()
            except Exception:
                pass
            return None

    def set(self, key: str, value: Any, atomic: bool = True) -> None:
        """
        Store a JSON-serializable value under key.
        """
        p = self._path_for_key(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {"ts": time.time(), "value": value}
        if atomic:
            fd, tmp = tempfile.mkstemp(dir=str(p.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False)
                Path(tmp).replace(p)
                logger.debug(f"💾 Cached {key[:8]}...")
            finally:
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
        else:
            p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            logger.debug(f"💾 Cached {key[:8]}...")

    def clear_all(self) -> int:
        """Remove all cached files. Returns count removed."""
        count = 0
        try:
            for f in self.cache_dir.rglob("*.json"):
                try:
                    f.unlink()
                    count += 1
                except Exception:
                    pass
            logger.info(f"🗑️  Cleared {count} cache files")
            return count
        except Exception as e:
            logger.error(f"❌ Failed to clear cache: {e}")
            return 0

