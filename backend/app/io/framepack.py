"""SFP1 compact binary frame-pack encoder and decoder."""

import json
import struct
import numpy as np


MAGIC = b"SFP1"


def encode_framepack(
    frame_ids: list[str],
    data: np.ndarray,
    flags: np.ndarray | None = None,
) -> bytes:
    """Encode float32 frame stack and optional uint16 flag planes into SFP1 binary format.

    Parameters
    ----------
    frame_ids:
        Ordered identifiers matching frames along axis 0 of `data`.
    data:
        Array of shape (n_frames, planes_per_frame, npix, npix) or (n_frames, npix, npix).
    flags:
        Optional uint16 array of shape (n_frames, npix, npix).
    """
    arr = np.asarray(data, dtype="<f4")
    if arr.ndim == 3:
        arr = arr[:, np.newaxis, :, :]
    if arr.ndim != 4:
        raise ValueError(f"Expected 3D or 4D array, got shape {arr.shape}")

    n_frames, planes_per_frame, height, width = arr.shape
    if height != width:
        raise ValueError(f"Expected square grid, got {height}x{width}")
    if len(frame_ids) != n_frames:
        raise ValueError(f"frame_ids count ({len(frame_ids)}) != n_frames ({n_frames})")

    has_flags = flags is not None
    header_obj = {
        "npix": int(width),
        "n_frames": int(n_frames),
        "planes_per_frame": int(planes_per_frame),
        "dtype": "float32",
        "has_flags": has_flags,
        "frame_ids": frame_ids,
    }
    header_bytes = json.dumps(header_obj, separators=(",", ":")).encode("utf-8")
    pad_len = (4 - ((8 + len(header_bytes)) % 4)) % 4

    chunks = [
        MAGIC,
        struct.pack("<I", len(header_bytes)),
        header_bytes,
        b"\x00" * pad_len,
        np.ascontiguousarray(arr, dtype="<f4").tobytes(order="C"),
    ]
    if flags is not None:
        f_arr = np.ascontiguousarray(flags, dtype="<u2")
        if f_arr.shape != (n_frames, height, width):
            raise ValueError(f"flags shape {f_arr.shape} != {(n_frames, height, width)}")
        chunks.append(f_arr.tobytes(order="C"))
    return b"".join(chunks)


def decode_framepack(blob: bytes) -> tuple[dict, np.ndarray, np.ndarray | None]:
    """Decode SFP1 bytes back into (header_dict, float32_data, optional_uint16_flags)."""
    if len(blob) < 8 or blob[:4] != MAGIC:
        raise ValueError("Invalid SFP1 magic header")
    header_len = struct.unpack("<I", blob[4:8])[0]
    header_end = 8 + header_len
    header = json.loads(blob[8:header_end].decode("utf-8"))
    pad_len = (4 - (header_end % 4)) % 4
    data_offset = header_end + pad_len

    n_frames = int(header["n_frames"])
    planes = int(header["planes_per_frame"])
    npix = int(header["npix"])
    float_count = n_frames * planes * npix * npix
    float_bytes = float_count * 4
    data = np.frombuffer(blob, dtype="<f4", count=float_count, offset=data_offset).reshape(
        (n_frames, planes, npix, npix)
    ).copy()

    flags = None
    if header.get("has_flags"):
        flags_offset = data_offset + float_bytes
        flag_count = n_frames * npix * npix
        flags = np.frombuffer(blob, dtype="<u2", count=flag_count, offset=flags_offset).reshape(
            (n_frames, npix, npix)
        ).copy()

    return header, data, flags
