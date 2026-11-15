"""Comprehensive unit and boundary tests for SFP1 binary framepack encoding and decoding."""

import struct
import numpy as np
import pytest

from app.io.framepack import MAGIC, decode_framepack, encode_framepack


def test_sfp1_basic_roundtrip_single_plane() -> None:
    """Test standard single-plane 64x64 12-frame cube with uint16 flags."""
    n_frames = 12
    npix = 64
    frame_ids = [f"frame_{i:02d}" for i in range(n_frames)]

    data = np.linspace(-30.0, 15.0, n_frames * 1 * npix * npix, dtype=np.float32).reshape(
        (n_frames, 1, npix, npix)
    )
    flags = np.zeros((n_frames, npix, npix), dtype=np.uint16)
    flags[0, 10, 10] = 0x0001  # Bit 1 Wind-Ripple
    flags[5, 20, 20] = 0x0002  # Bit 2 Sub-Zero Freeze
    flags[11, 30, 30] = 0x0008  # Bit 4 Cloud Cover

    blob = encode_framepack(frame_ids, data, flags)
    header, out_data, out_flags = decode_framepack(blob)

    assert header["n_frames"] == n_frames
    assert header["npix"] == npix
    assert header["planes_per_frame"] == 1
    assert header["dtype"] == "float32"
    assert header["has_flags"] is True
    assert header["frame_ids"] == frame_ids

    assert out_data.shape == (n_frames, 1, npix, npix)
    assert out_data.dtype == np.float32
    assert np.allclose(out_data, data, rtol=1e-5, atol=1e-6)

    assert out_flags is not None
    assert out_flags.shape == (n_frames, npix, npix)
    assert out_flags.dtype == np.uint16
    assert out_flags[0, 10, 10] == 0x0001
    assert out_flags[5, 20, 20] == 0x0002
    assert out_flags[11, 30, 30] == 0x0008
    assert np.array_equal(out_flags, flags)


def test_sfp1_multi_plane_rgb_roundtrip() -> None:
    """Test 3-plane RGB product encoding and decoding."""
    n_frames = 12
    planes = 3
    npix = 64
    frame_ids = [f"rgb_{i}" for i in range(n_frames)]

    data = np.random.uniform(0.0, 1.0, (n_frames, planes, npix, npix)).astype(np.float32)
    blob = encode_framepack(frame_ids, data, flags=None)
    header, out_data, out_flags = decode_framepack(blob)

    assert header["planes_per_frame"] == 3
    assert header["has_flags"] is False
    assert out_data.shape == (n_frames, 3, npix, npix)
    assert out_flags is None
    assert np.allclose(out_data, data, rtol=1e-5)


def test_sfp1_3d_input_expands_to_4d() -> None:
    """A 3D array of shape (N, H, W) must automatically expand to (N, 1, H, W)."""
    n_frames = 4
    npix = 16
    data_3d = np.ones((n_frames, npix, npix), dtype=np.float32) * 42.0
    frame_ids = [f"f_{i}" for i in range(n_frames)]

    blob = encode_framepack(frame_ids, data_3d)
    header, out_data, out_flags = decode_framepack(blob)

    assert header["planes_per_frame"] == 1
    assert out_data.shape == (n_frames, 1, npix, npix)
    assert np.all(out_data == 42.0)
    assert out_flags is None


def test_sfp1_4byte_padding_alignment() -> None:
    """Verify that the float32 data payload is strictly 4-byte aligned regardless of header length."""
    npix = 8
    data = np.zeros((1, 1, npix, npix), dtype=np.float32)

    # Vary header lengths to test all possible modulo 4 offsets (0, 1, 2, 3)
    for pad_test_suffix in ["", "x", "xx", "xxx", "xxxx"]:
        frame_ids = [f"frame_with_variable_id_{pad_test_suffix}"]
        blob = encode_framepack(frame_ids, data)

        assert blob[:4] == MAGIC
        header_len = struct.unpack("<I", blob[4:8])[0]
        header_end = 8 + header_len
        pad_len = (4 - (header_end % 4)) % 4
        data_offset = header_end + pad_len

        # Data offset must be an exact multiple of 4
        assert data_offset % 4 == 0, f"Offset {data_offset} is not 4-byte aligned!"

        # Roundtrip verification
        header, out_data, _ = decode_framepack(blob)
        assert header["frame_ids"] == frame_ids
        assert out_data.shape == (1, 1, npix, npix)


def test_sfp1_little_endian_wire_format() -> None:
    """Verify byte-level little-endian representation of float32 and uint16."""
    data = np.array([[[[1.0]]]], dtype="<f4")  # 1.0 in IEEE 754 LE is \x00\x00\x80\x3f
    flags = np.array([[[0x1234]]], dtype="<u2")  # 0x1234 in LE is \x34\x12
    blob = encode_framepack(["f0"], data, flags)

    header_len = struct.unpack("<I", blob[4:8])[0]
    header_end = 8 + header_len
    pad_len = (4 - (header_end % 4)) % 4
    data_offset = header_end + pad_len

    # Float 1.0 check
    float_bytes = blob[data_offset : data_offset + 4]
    assert float_bytes == b"\x00\x00\x80?", f"Expected IEEE 754 LE 1.0, got {float_bytes!r}"

    # Uint16 0x1234 check
    flags_offset = data_offset + 4
    flag_bytes = blob[flags_offset : flags_offset + 2]
    assert flag_bytes == b"\x34\x12", f"Expected uint16 LE 0x1234, got {flag_bytes!r}"


def test_sfp1_handles_nans_infs_and_negatives() -> None:
    """Verify that special float32 values (NaN, Inf, negative zero) are preserved."""
    data = np.array([[[[-0.0, np.nan], [np.inf, -np.inf]]]], dtype=np.float32)
    blob = encode_framepack(["special"], data)
    _, out_data, _ = decode_framepack(blob)

    assert np.isnan(out_data[0, 0, 0, 1])
    assert np.isposinf(out_data[0, 0, 1, 0])
    assert np.isneginf(out_data[0, 0, 1, 1])
    assert np.signbit(out_data[0, 0, 0, 0])  # Negative zero


def test_sfp1_validation_rejects_non_square() -> None:
    """Rectangular inputs (height != width) must raise ValueError."""
    rect_data = np.zeros((2, 1, 64, 32), dtype=np.float32)
    with pytest.raises(ValueError, match="Expected square grid"):
        encode_framepack(["f0", "f1"], rect_data)


def test_sfp1_validation_rejects_mismatched_frame_ids() -> None:
    """Mismatch between frame_ids length and n_frames must raise ValueError."""
    data = np.zeros((3, 1, 16, 16), dtype=np.float32)
    with pytest.raises(ValueError, match="frame_ids count"):
        encode_framepack(["f0", "f1"], data)  # 2 IDs for 3 frames


def test_sfp1_validation_rejects_bad_dimensions() -> None:
    """2D or 5D arrays must raise ValueError."""
    with pytest.raises(ValueError, match="Expected 3D or 4D array"):
        encode_framepack(["f0"], np.zeros((16, 16), dtype=np.float32))

    with pytest.raises(ValueError, match="Expected 3D or 4D array"):
        encode_framepack(["f0"], np.zeros((1, 1, 1, 16, 16), dtype=np.float32))


def test_sfp1_validation_rejects_mismatched_flags_shape() -> None:
    """Flags shape mismatch against data must raise ValueError."""
    data = np.zeros((2, 1, 16, 16), dtype=np.float32)
    bad_flags = np.zeros((2, 32, 32), dtype=np.uint16)
    with pytest.raises(ValueError, match="flags shape"):
        encode_framepack(["f0", "f1"], data, bad_flags)


def test_sfp1_decode_rejects_invalid_magic() -> None:
    """Decoding bytes without MAGIC = b'SFP1' must raise ValueError."""
    bad_blob = b"SPH1\x00\x00\x00\x05{}"
    with pytest.raises(ValueError, match="Invalid SFP1 magic header"):
        decode_framepack(bad_blob)


def test_sfp1_decode_rejects_truncated_blob() -> None:
    """Decoding truncated buffer must raise ValueError or struct.error."""
    short_blob = b"SFP"
    with pytest.raises(ValueError, match="Invalid SFP1 magic header"):
        decode_framepack(short_blob)
