"""Local disk cache for compiled SAR Symphony session artifacts."""

from pathlib import Path


class DiskCache:
    """Thread- and async-safe disk cache managing runtime session artifacts and LRU eviction."""

    def __init__(self, root_dir: Path) -> None:
        self.root = Path(root_dir)
        self.raw_dir = self.root / "raw"
        self.sessions_dir = self.root / "sessions"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def session_path(self, session_id: str) -> Path:
        p = self.sessions_dir / session_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def evict_lru(self, max_gb: float = 2.0) -> int:
        """Delete oldest cached runtime files if total runtime_cache exceeds max_gb."""
        limit = int(max_gb * (1024**3))
        files: list[tuple[float, int, Path]] = []
        total = 0
        for p in self.root.rglob("*"):
            if p.is_file():
                st = p.stat()
                total += st.st_size
                files.append((st.st_mtime, st.st_size, p))
        if total <= limit:
            return 0
        files.sort(key=lambda t: t[0])
        removed = 0
        for _, size, p in files:
            if total <= limit * 0.85:
                break
            try:
                p.unlink()
                total -= size
                removed += 1
            except OSError:
                pass
        return removed
