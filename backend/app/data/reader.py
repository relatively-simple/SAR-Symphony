"""Byte-range HTTP FITS subimage reader for SPHEREx Level 2 MEFs with IRSA cutout fallback."""

import asyncio
import struct
from io import BytesIO
import numpy as np
import httpx
from astropy import log as _astropy_log
from astropy.io import fits
from astropy.wcs import WCS

_astropy_log.setLevel("WARNING")

from app.data.cache import DiskCache
from app.data.http import request_with_retry
from app.models import ExposureRecord


_BLOCK = 2880


def _pad_bytes(data: bytes, fill: bytes = b"\x00") -> bytes:
    rem = len(data) % _BLOCK
    return data + (fill * ((_BLOCK - rem) % _BLOCK))


def _parse_header_cards(buf: bytes) -> tuple[fits.Header, int]:
    """Read FITS header blocks from `buf` starting at 0, returning (Header, end_offset)."""
    pos = 0
    raw_cards: list[str] = []
    while pos + _BLOCK <= len(buf):
        block = buf[pos : pos + _BLOCK]
        pos += _BLOCK
        found_end = False
        for i in range(0, _BLOCK, 80):
            card_str = block[i : i + 80].decode("ascii", errors="replace")
            raw_cards.append(card_str)
            if card_str[:8].strip() == "END":
                found_end = True
                break
        if found_end:
            hdr = fits.Header.fromstring("".join(raw_cards), sep="")
            return hdr, pos
    raise ValueError("END card not found within fetched header buffer")


def _hdu_data_bytes(hdr: fits.Header) -> tuple[int, int]:
    """Return (raw_data_bytes, 2880-padded_bytes) described by FITS header."""
    naxis = int(hdr.get("NAXIS", 0))
    if naxis == 0:
        return 0, 0
    bitpix = abs(int(hdr["BITPIX"])) // 8
    nelem = 1
    for axis in range(1, naxis + 1):
        nelem *= int(hdr[f"NAXIS{axis}"])
    pcount = int(hdr.get("PCOUNT", 0))
    gcount = int(hdr.get("GCOUNT", 1))
    raw = bitpix * gcount * (pcount + nelem)
    padded = ((raw + _BLOCK - 1) // _BLOCK) * _BLOCK
    return raw, padded


async def _fetch_header_at(client: httpx.AsyncClient, url: str, start: int, span: int = 23040) -> tuple[fits.Header, int]:
    """Fetch header starting cleanly at byte offset `start`, retrying larger span if needed."""
    for try_span in (span, span * 3):
        resp = await request_with_retry(
            client,
            "GET",
            url,
            headers={"Range": f"bytes={start}-{start + try_span - 1}"},
        )
        try:
            hdr, rel_end = _parse_header_cards(resp.content)
            return hdr, start + rel_end
        except ValueError:
            continue
    raise ValueError(f"Could not parse FITS header at offset {start} from {url}")


async def _fetch_row_window(
    client: httpx.AsyncClient,
    url: str,
    data_offset: int,
    naxis1: int,
    bitpix: int,
    y0: int,
    y1: int,
    x0: int,
    x1: int,
) -> np.ndarray:
    """Range-read contiguous FITS image rows [y0:y1] and slice columns [x0:x1]."""
    elem_bytes = abs(bitpix) // 8
    row_bytes = naxis1 * elem_bytes
    byte_start = data_offset + y0 * row_bytes
    byte_end = data_offset + y1 * row_bytes - 1
    resp = await request_with_retry(
        client,
        "GET",
        url,
        headers={"Range": f"bytes={byte_start}-{byte_end}"},
    )
    dtype = ">f4" if bitpix == -32 else (">i4" if bitpix == 32 else ">f8")
    rows = np.frombuffer(resp.content, dtype=dtype).reshape((y1 - y0, naxis1))
    return rows[:, x0:x1].copy()


async def _fetch_compressed_flags_window(
    client: httpx.AsyncClient,
    url: str,
    h_flg: fits.Header,
    data_offset: int,
    y0: int,
    y1: int,
    x0: int,
    x1: int,
) -> np.ndarray:
    """Range-read row-compressed Rice FLAGS tiles for rows [y0:y1] and crop [x0:x1]."""
    if not h_flg.get("ZIMAGE", False):
        return await _fetch_row_window(
            client, url, data_offset, int(h_flg["NAXIS1"]), int(h_flg["BITPIX"]), y0, y1, x0, x1
        )

    if int(h_flg.get("ZTILE2", 1)) != 1:
        raise ValueError(f"Unsupported FLAGS tile height ZTILE2={h_flg.get('ZTILE2')}")

    ny = y1 - y0
    row_stride = int(h_flg["NAXIS1"])
    ptr_start = data_offset + y0 * row_stride
    ptr_end = data_offset + y1 * row_stride - 1
    r_ptr = await request_with_retry(client, "GET", url, headers={"Range": f"bytes={ptr_start}-{ptr_end}"})
    ptrs = np.frombuffer(r_ptr.content, dtype=">i4").reshape((ny, 2))

    # Non-empty compressed heap span
    nonzero = ptrs[:, 0] > 0
    if not np.any(nonzero):
        return np.zeros((ny, x1 - x0), dtype=np.int32)

    heap_base = data_offset + row_stride * int(h_flg["NAXIS2"])
    rel_start = int(np.min(ptrs[nonzero, 1]))
    rel_end = int(np.max(ptrs[nonzero, 1] + ptrs[nonzero, 0]))

    r_heap = await request_with_retry(
        client, "GET", url, headers={"Range": f"bytes={heap_base + rel_start}-{heap_base + rel_end - 1}"}
    )
    heap_slice = r_heap.content

    table_bytes = bytearray(ny * 8)
    for k in range(ny):
        cnt = int(ptrs[k, 0])
        old_off = int(ptrs[k, 1])
        new_off = (old_off - rel_start) if cnt > 0 else 0
        struct.pack_into(">II", table_bytes, k * 8, cnt, new_off)

    hdr = h_flg.copy()
    hdr["NAXIS2"] = ny
    hdr["ZNAXIS2"] = ny
    hdr["PCOUNT"] = len(heap_slice)
    hdr["THEAP"] = ny * 8

    p_hdr = _pad_bytes(fits.PrimaryHDU().header.tostring(sep="", endcard=True).encode("ascii"), b" ")
    f_hdr = _pad_bytes(hdr.tostring(sep="", endcard=True).encode("ascii"), b" ")
    payload = _pad_bytes(bytes(table_bytes) + heap_slice, b"\x00")
    with fits.open(BytesIO(p_hdr + f_hdr + payload)) as hdul:
        rows = np.asarray(hdul[1].data, dtype=np.int32)
    return rows[:, x0:x1].copy()


async def _fetch_wcs_wave_map(
    client: httpx.AsyncClient,
    url: str,
    base_header: fits.Header,
    y0: int,
    y1: int,
    x0: int,
    x1: int,
) -> np.ndarray | None:
    """Range-read WCS-WAVE extension from file tail and evaluate wavelength map (um) on slice."""
    resp = await request_with_retry(client, "GET", url, headers={"Range": "bytes=-32768"})
    tail = resp.content
    marker = b"EXTNAME = 'WCS-WAVE'"
    idx = tail.find(marker)
    if idx == -1:
        idx = tail.find(b"WCS-WAVE")
        if idx == -1:
            return None
    xt_idx = tail.rfind(b"XTENSION= 'BINTABLE'", 0, idx + 80)
    if xt_idx == -1:
        return None
    hdu_bytes = tail[xt_idx:]

    primary = fits.PrimaryHDU()
    wave_hdu = fits.BinTableHDU.fromstring(hdu_bytes)
    img_hdr = base_header.copy()
    with fits.HDUList(
        [primary, fits.ImageHDU(data=np.zeros((2, 2), dtype=np.float32), header=img_hdr), wave_hdu]
    ) as hdul:
        swcs = WCS(img_hdr, fobj=hdul, key="W")
        swcs.sip = None
        yy, xx = np.mgrid[y0:y1, x0:x1]
        world = swcs.pixel_to_world_values(xx, yy)
        wave_m = np.asarray(world[0] if isinstance(world, tuple) else world, dtype=np.float64)
        if np.nanmedian(wave_m) < 1e-3:
            wave_m = wave_m * 1e6
        return wave_m.astype(np.float32)


def _bbox_for_fov(
    wcs: WCS, shape: tuple[int, int], ra_deg: float, dec_deg: float, fov_deg: float, pad: int = 12
) -> tuple[int, int, int, int]:
    """Compute bounded pixel slice [y0:y1, x0:x1] covering sky FOV box with padding."""
    ny, nx = shape
    half = fov_deg * 0.5
    cosd = max(np.cos(np.radians(dec_deg)), 0.1)
    dra = half / cosd
    corners_ra = [ra_deg - dra, ra_deg + dra, ra_deg - dra, ra_deg + dra, ra_deg]
    corners_dec = [dec_deg - half, dec_deg - half, dec_deg + half, dec_deg + half, dec_deg]
    px, py = wcs.world_to_pixel_values(corners_ra, corners_dec)
    px = np.asarray(px, dtype=np.float64)
    py = np.asarray(py, dtype=np.float64)
    x0 = max(0, int(np.floor(np.min(px))) - pad)
    x1 = min(nx, int(np.ceil(np.max(px))) + pad + 1)
    y0 = max(0, int(np.floor(np.min(py))) - pad)
    y1 = min(ny, int(np.ceil(np.max(py))) + pad + 1)
    return y0, y1, x0, x1


async def read_range(
    client: httpx.AsyncClient,
    rec: ExposureRecord,
    ra_deg: float,
    dec_deg: float,
    fov_deg: float,
) -> dict:
    """Fetch SPHEREx subimage via targeted HTTP Range reads, skipping the ~16 MB/4 MB EPSF table."""
    url = rec.access_url
    resp0 = await request_with_retry(client, "GET", url, headers={"Range": "bytes=0-28799"})
    buf0 = resp0.content
    h0, off1 = _parse_header_cards(buf0)
    _, pad0 = _hdu_data_bytes(h0)
    off_img_hdr = off1 + pad0
    if off_img_hdr < len(buf0):
        try:
            h_img, rel_end = _parse_header_cards(buf0[off_img_hdr:])
            off_img_data = off_img_hdr + rel_end
        except ValueError:
            h_img, off_img_data = await _fetch_header_at(client, url, off_img_hdr)
    else:
        h_img, off_img_data = await _fetch_header_at(client, url, off_img_hdr)

    nx = int(h_img["NAXIS1"])
    ny = int(h_img["NAXIS2"])
    full_wcs = WCS(h_img)
    y0, y1, x0, x1 = _bbox_for_fov(full_wcs, (ny, nx), ra_deg, dec_deg, fov_deg)
    if (x1 - x0) < 4 or (y1 - y0) < 4:
        raise ValueError(f"Exposure {rec.obs_id} has <4 px overlap with target box")

    _, pad_img = _hdu_data_bytes(h_img)
    off_flg_hdr = off_img_data + pad_img
    h_flg, off_flg_data = await _fetch_header_at(client, url, off_flg_hdr, span=8640)
    _, pad_flg = _hdu_data_bytes(h_flg)

    off_var_hdr = off_flg_data + pad_flg
    h_var, off_var_data = await _fetch_header_at(client, url, off_var_hdr, span=8640)
    _, pad_var = _hdu_data_bytes(h_var)

    off_zod_hdr = off_var_data + pad_var
    h_zod, off_zod_data = await _fetch_header_at(client, url, off_zod_hdr, span=8640)

    img_coro = _fetch_row_window(client, url, off_img_data, nx, int(h_img["BITPIX"]), y0, y1, x0, x1)
    flg_coro = _fetch_compressed_flags_window(client, url, h_flg, off_flg_data, y0, y1, x0, x1)
    var_coro = _fetch_row_window(
        client, url, off_var_data, int(h_var["NAXIS1"]), int(h_var["BITPIX"]), y0, y1, x0, x1
    )
    zod_coro = _fetch_row_window(
        client, url, off_zod_data, int(h_zod["NAXIS1"]), int(h_zod["BITPIX"]), y0, y1, x0, x1
    )
    wav_coro = _fetch_wcs_wave_map(client, url, h_img, y0, y1, x0, x1)

    image, flags, variance, zodi, wave_map = await asyncio.gather(
        img_coro, flg_coro, var_coro, zod_coro, wav_coro
    )

    if wave_map is None or not np.any(np.isfinite(wave_map)):
        lam_mid = 0.5 * (rec.em_min_um + rec.em_max_um)
        wave_map = np.full(image.shape, lam_mid, dtype=np.float32)

    sub_wcs = full_wcs.slice((slice(y0, y1), slice(x0, x1)))
    wcs_hdr = sub_wcs.to_header(relax=True)
    if "A_ORDER" in wcs_hdr and not str(wcs_hdr.get("CTYPE1", "")).endswith("-SIP"):
        wcs_hdr["CTYPE1"] = "RA---TAN-SIP"
        wcs_hdr["CTYPE2"] = "DEC--TAN-SIP"
    wcs_hdr_str = wcs_hdr.tostring(sep="\n")
    lam_center = float(np.nanmedian(wave_map))

    return {
        "image": image.astype(np.float32),
        "flags": flags.astype(np.int32),
        "variance": variance.astype(np.float32),
        "zodi": zodi.astype(np.float32),
        "wavelength_um": lam_center,
        "wave_map": wave_map.astype(np.float32),
        "wcs": sub_wcs,
        "wcs_header": wcs_hdr_str,
        "meta": {
            "obs_id": rec.obs_id,
            "collection": rec.collection,
            "detector": rec.detector,
            "t_mid_mjd": rec.t_mid_mjd,
            "slice_bbox": [y0, y1, x0, x1],
            "method": "range",
        },
    }


async def read_cutout(
    client: httpx.AsyncClient,
    rec: ExposureRecord,
    ra_deg: float,
    dec_deg: float,
    fov_deg: float,
) -> dict:
    """Fallback reader calling IRSA's server-side ?center=&size= cutout endpoint."""
    # Request slight padding around requested FOV for clean alignment edges
    req_size = min(0.35, fov_deg + 0.025)
    cutout_url = f"{rec.access_url}?center={ra_deg:.6f},{dec_deg:.6f}&size={req_size:.4f}"
    resp = await request_with_retry(client, "GET", cutout_url)
    with fits.open(BytesIO(resp.content)) as hdul:
        img_hdu = hdul["IMAGE"]
        image = np.asarray(img_hdu.data, dtype=np.float32)
        flags = np.asarray(hdul["FLAGS"].data, dtype=np.int32)
        variance = np.asarray(hdul["VARIANCE"].data, dtype=np.float32)
        zodi = np.asarray(hdul["ZODI"].data, dtype=np.float32)
        sub_wcs = WCS(img_hdu.header)

        try:
            swcs = WCS(img_hdu.header, fobj=hdul, key="W")
            swcs.sip = None
            ny, nx = image.shape
            yy, xx = np.mgrid[0:ny, 0:nx]
            world = swcs.pixel_to_world_values(xx, yy)
            wave_m = np.asarray(world[0] if isinstance(world, tuple) else world, dtype=np.float64)
            if np.nanmedian(wave_m) < 1e-3:
                wave_m = wave_m * 1e6
            wave_map = wave_m.astype(np.float32)
        except Exception:
            lam_mid = 0.5 * (rec.em_min_um + rec.em_max_um)
            wave_map = np.full(image.shape, lam_mid, dtype=np.float32)

    wcs_hdr = sub_wcs.to_header(relax=True)
    if "A_ORDER" in wcs_hdr and not str(wcs_hdr.get("CTYPE1", "")).endswith("-SIP"):
        wcs_hdr["CTYPE1"] = "RA---TAN-SIP"
        wcs_hdr["CTYPE2"] = "DEC--TAN-SIP"
    wcs_hdr_str = wcs_hdr.tostring(sep="\n")
    return {
        "image": image,
        "flags": flags,
        "variance": variance,
        "zodi": zodi,
        "wavelength_um": float(np.nanmedian(wave_map)),
        "wave_map": wave_map,
        "wcs": sub_wcs,
        "wcs_header": wcs_hdr_str,
        "meta": {
            "obs_id": rec.obs_id,
            "collection": rec.collection,
            "detector": rec.detector,
            "t_mid_mjd": rec.t_mid_mjd,
            "method": "cutout",
        },
    }


async def read_subimage(
    client: httpx.AsyncClient,
    cache: DiskCache,
    rec: ExposureRecord,
    ra_deg: float,
    dec_deg: float,
    fov_deg: float,
    mode: str = "auto",
) -> dict:
    """Load subimage from DiskCache, or fetch via range/cutout and persist cleanly."""
    cached = cache.get_raw(rec.obs_id, rec.detector, ra_deg, dec_deg, fov_deg)
    if cached is not None:
        return cached

    if mode == "cutout":
        sub = await read_cutout(client, rec, ra_deg, dec_deg, fov_deg)
    elif mode == "range":
        sub = await read_range(client, rec, ra_deg, dec_deg, fov_deg)
    else:
        try:
            sub = await read_range(client, rec, ra_deg, dec_deg, fov_deg)
        except Exception:
            sub = await read_cutout(client, rec, ra_deg, dec_deg, fov_deg)

    cache.put_raw(
        rec.obs_id,
        rec.detector,
        ra_deg,
        dec_deg,
        fov_deg,
        image=sub["image"],
        flags=sub["flags"],
        variance=sub["variance"],
        zodi=sub["zodi"],
        wavelength_um=sub["wavelength_um"],
        wave_map=sub["wave_map"],
        wcs_header=sub["wcs_header"],
        meta=sub["meta"],
    )
    return sub
