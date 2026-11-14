"""Binary SFP1 frame-pack streaming endpoint."""

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.config import Settings, get_settings
from app.core.errors import ExploreError
from app.pipeline.session import find_session_dir


router = APIRouter(prefix="/api/sessions", tags=["frames"])
ALLOWED_PRODUCTS = {"pass_coadds", "diffs", "coldglow", "rgb", "visits"}


@router.get("/{session_id}/frames/{product}.sfp")
def get_framepack(
    session_id: str,
    product: str,
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    """Serve pre-built or runtime-compiled binary SFP1 frame bundle."""
    if product not in ALLOWED_PRODUCTS:
        raise ExploreError("BAD_PRODUCT", f"Unknown frame product '{product}'.", 404)
    sdir = find_session_dir(settings, session_id)
    fpath = sdir / "frames" / f"{product}.sfp"
    if not fpath.exists():
        raise ExploreError("PRODUCT_MISSING", f"Product '{product}' is not available for this target.", 404)
    return FileResponse(
        fpath,
        media_type="application/octet-stream",
        headers={"Cache-Control": "public, max-age=3600"},
    )
