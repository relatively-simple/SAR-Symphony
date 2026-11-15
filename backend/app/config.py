"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_DEFAULT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings for KurinjiKumaraN SAR Symphony: Dancing with Earth's Signals."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = Field(default=7860, alias="PORT")
    app_version: str = "0.1.0"
    pipeline_version: str = "v1"

    spx_collections: str = Field(
        default="sentinel1_grd,nisar_sim,gpm_imerg,merra2,modis_lst,black_marble",
        alias="SPX_COLLECTIONS",
    )
    spx_fetch_mode: str = Field(default="auto", alias="SPX_FETCH_MODE")
    spx_max_workers: int = Field(default=8, alias="SPX_MAX_WORKERS")
    spx_frames_per_pass_det: int = Field(default=4, alias="SPX_FRAMES_PER_PASS_DET")
    spx_pass_gap_days: float = Field(default=45.0, alias="SPX_PASS_GAP_DAYS")
    spx_preset_dir: Path = Field(
        default=_DEFAULT_ROOT / "cache" / "presets",
        alias="SPX_PRESET_DIR",
    )
    spx_cache_dir: Path = Field(
        default=_DEFAULT_ROOT / "runtime_cache",
        alias="SPX_CACHE_DIR",
    )
    spx_frontend_dist: Path = Field(
        default=_DEFAULT_ROOT / "frontend" / "dist",
        alias="SPX_FRONTEND_DIST",
    )
    spx_cache_max_gb: float = Field(default=2.0, alias="SPX_CACHE_MAX_GB")
    spx_http_timeout_s: float = Field(default=30.0, alias="SPX_HTTP_TIMEOUT_S")

    @property
    def collections(self) -> list[str]:
        """Return configured Earth observation collections in priority order."""
        return [c.strip() for c in self.spx_collections.split(",") if c.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached singleton Settings instance."""
    return Settings()
