"""Local disk cache for SPHEREx subimages and compiled session artifacts."""

import json
import os
import time
from pathlib import Path
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS


class DiskCache:
    """Thread- and async-safe disk cache storing cropped FITS subimages cleanly as .npz."""

    def __init__(self, root_dir: Path) -> None:
        self.root = Path(root_dir)
        self.raw_dir = self.root / "raw"
        self.sessions_dir = self.root / "sessions"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def raw_path(self, obs_id: str, detector: int, ra_deg: float, dec_deg: float, fov_deg: float) -> Path:
        key = f"{ra_deg:.4f}_{dec_deg:.4f}_{fov_deg:.3f}"
        safe_obs = obs_id.replace("/", "_")
        return self.raw_dir / key / f"{safe_obs}_D{detector}.npz"

    def get_raw(self, obs_id: str, detector: int, ra_deg: float, dec_deg: float, fov_deg: float) -> dict | None:
        p = self.raw_path(obs_id, detector, ra_deg, dec_deg, fov_deg)
        if not p.exists():
            return None
        try:
            with np.load(p, allow_pickle=False) as z:
                # Rehydrate full WCS (including -SIP distortions) from serialized FITS header string
                hdr_str = str(z["wcs_header"].item())
                hdr = (
                    fits.Header.fromstring(hdr_str, sep="\n")
                    if "\n" in hdr_str
                    else fits.Header.fromstring(hdr_str)
                )
                wcs = WCS(hdr)
                meta = json.loads(str(z["meta_json"].item()))
                return {
                    "image": z["image"],
                    "flags": z["flags"],
                    "variance": z["variance"],
                    "zodi": z["zodi"],
                    "wavelength_um": float(z["wavelength_um"].item()),
                    "wave_map": z["wave_map"],
                    "wcs": wcs,
                    "wcs_header": hdr_str,
                    "meta": meta,
                }
        except Exception:
            return None

    def put_raw(
        self,
        obs_id: str,
        detector: int,
        ra_deg: float,
        dec_deg: float,
        fov_deg: float,
        *,
        image: np.ndarray,
        flags: np.ndarray,
        variance: np.ndarray,
        zodi: np.ndarray,
        wavelength_um: float,
        wave_map: np.ndarray,
        wcs_header: str,
        meta: dict,
    ) -> Path:
        p = self.raw_path(obs_id, detector, ra_deg, dec_deg, fov_deg)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp.npz")
        np.savez_compressed(
            tmp,
            image=image.astype(np.float32),
            flags=flags.astype(np.int32),
            variance=variance.astype(np.float32),
            zodi=zodi.astype(np.float32),
            wavelength_um=np.array(wavelength_um, dtype=np.float64),
            wave_map=wave_map.astype(np.float32),
            wcs_header=np.array(wcs_header),
            meta_json=np.array(json.dumps(meta)),
        )
        os.replace(tmp, p)
        return p

    def session_path(self, session_id: str) -> Path:
        p = self.sessions_dir / session_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def evict_lru(self, max_gb: float = 2.0) -> int:
        """Delete oldest cached raw files if total runtime_cache exceeds max_gb."""
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
