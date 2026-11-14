"""SPHEREx Level 2 MEF FLAGS bitmask constants, classification, and compact encoding."""

import numpy as np


TRANSIENT = 1 << 0       # 1: cosmic ray or transient glitch
OVERFLOW = 1 << 1        # 2: detector saturation / overflow
SUR_ERROR = 1 << 2       # 4: sample-up-the-ramp error
NONFUNC = 1 << 6         # 64: dead / non-functional pixel
DICHROIC = 1 << 7        # 128: dichroic artifact
MISSING_DATA = 1 << 9    # 512: missing telemetry / dead region

FATAL_MASK = OVERFLOW | SUR_ERROR | NONFUNC | MISSING_DATA
WARN_MASK = TRANSIENT | DICHROIC

FLAG_NAMES: dict[int, str] = {
    TRANSIENT: "TRANSIENT",
    OVERFLOW: "OVERFLOW",
    SUR_ERROR: "SUR_ERROR",
    NONFUNC: "NONFUNC",
    DICHROIC: "DICHROIC",
    MISSING_DATA: "MISSING_DATA",
}

# Compact uint16 bit positions shared with frontend/src/engine/framepack.ts
COMPACT_BITS: list[tuple[int, str, int]] = [
    (0, "TRANSIENT", TRANSIENT),
    (1, "OVERFLOW", OVERFLOW),
    (2, "SUR_ERROR", SUR_ERROR),
    (3, "NONFUNC", NONFUNC),
    (4, "DICHROIC", DICHROIC),
    (5, "MISSING_DATA", MISSING_DATA),
]


def summarize_raw_flags(flags_arr: np.ndarray) -> dict[str, int]:
    """Count pixels containing each known SPHEREx Level 2 flag bit."""
    if flags_arr.size == 0:
        return {}
    arr = flags_arr.astype(np.int64, copy=False)
    summary: dict[str, int] = {}
    for raw_bit, name in FLAG_NAMES.items():
        count = int(np.count_nonzero((arr & raw_bit) != 0))
        if count > 0:
            summary[name] = count
    return summary


def remap_raw_to_uint16(flags_arr: np.ndarray) -> np.ndarray:
    """Pack raw SPHEREx 32-bit flag words into compact 0..5 bit positions in uint16."""
    arr = flags_arr.astype(np.int64, copy=False)
    out = np.zeros(arr.shape, dtype=np.uint16)
    for bit_pos, _, raw_bit in COMPACT_BITS:
        mask = (arr & raw_bit) != 0
        if np.any(mask):
            out[mask] |= np.uint16(1 << bit_pos)
    return out


def summarize_uint16_flags(compact_arr: np.ndarray) -> dict[str, int]:
    """Count pixels containing each compact flag bit (inverse of remap_raw_to_uint16)."""
    if compact_arr.size == 0:
        return {}
    summary: dict[str, int] = {}
    for bit_pos, name, _ in COMPACT_BITS:
        count = int(np.count_nonzero((compact_arr & (1 << bit_pos)) != 0))
        if count > 0:
            summary[name] = count
    return summary
