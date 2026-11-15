"""Earth observation quality and illusion bitmask constants, classification, and compact encoding."""

import numpy as np


# Earth Illusion uint16 Bitmask Constants
FLAG_WIND_RIPPLE: int = 0x0001     # Bit 1 (1 << 0): Wind-roughened open water mimicking dry land in SAR
FLAG_SUBZERO_FREEZE: int = 0x0002  # Bit 2 (1 << 1): Sub-zero flash freeze dropping dielectric constant
FLAG_STEEP_SLOPE: int = 0x0004     # Bit 3 (1 << 2): Mountainous relief causing radar layover / shadow slip
FLAG_CLOUD_COVER: int = 0x0008     # Bit 4 (1 << 3): Dense storm / monsoon cloud cover obscuring optical NDVI

# Legacy bitmask aliases maintained for backwards compatibility
TRANSIENT: int = 1 << 0
OVERFLOW: int = 1 << 1
SUR_ERROR: int = 1 << 2
NONFUNC: int = 1 << 6
DICHROIC: int = 1 << 7
MISSING_DATA: int = 1 << 9

FATAL_MASK: int = OVERFLOW | SUR_ERROR | NONFUNC | MISSING_DATA
WARN_MASK: int = TRANSIENT | DICHROIC

FLAG_NAMES: dict[int, str] = {
    FLAG_WIND_RIPPLE: "WIND_RIPPLE",
    FLAG_SUBZERO_FREEZE: "SUBZERO_FREEZE",
    FLAG_STEEP_SLOPE: "STEEP_SLOPE",
    FLAG_CLOUD_COVER: "CLOUD_COVER",
    TRANSIENT: "TRANSIENT",
    OVERFLOW: "OVERFLOW",
    SUR_ERROR: "SUR_ERROR",
    NONFUNC: "NONFUNC",
    DICHROIC: "DICHROIC",
    MISSING_DATA: "MISSING_DATA",
}

# Bit positions shared with SFP1 header and frontend canvas decoder
COMPACT_BITS: list[tuple[int, str, int]] = [
    (0, "WIND_RIPPLE", FLAG_WIND_RIPPLE),
    (1, "SUBZERO_FREEZE", FLAG_SUBZERO_FREEZE),
    (2, "STEEP_SLOPE", FLAG_STEEP_SLOPE),
    (3, "CLOUD_COVER", FLAG_CLOUD_COVER),
]


def summarize_uint16_flags(compact_arr: np.ndarray) -> dict[str, int]:
    """Count pixels containing each compact illusion/quality flag bit."""
    if compact_arr.size == 0:
        return {}
    summary: dict[str, int] = {}
    for bit_pos, name, flag_val in COMPACT_BITS:
        count = int(np.count_nonzero((compact_arr & flag_val) != 0))
        if count > 0:
            summary[name] = count
    return summary


def summarize_raw_flags(flags_arr: np.ndarray) -> dict[str, int]:
    """Count pixels containing each known flag bit."""
    if flags_arr.size == 0:
        return {}
    arr = flags_arr.astype(np.int64, copy=False)
    summary: dict[str, int] = {}
    for bit_pos, name, flag_val in COMPACT_BITS:
        count = int(np.count_nonzero((arr & flag_val) != 0))
        if count > 0:
            summary[name] = count
    return summary


def remap_raw_to_uint16(flags_arr: np.ndarray) -> np.ndarray:
    """Pack flag words into compact uint16 bit positions."""
    arr = flags_arr.astype(np.int64, copy=False)
    out = np.zeros(arr.shape, dtype=np.uint16)
    for bit_pos, _, raw_bit in COMPACT_BITS:
        mask = (arr & raw_bit) != 0
        if np.any(mask):
            out[mask] |= np.uint16(1 << bit_pos)
    return out
