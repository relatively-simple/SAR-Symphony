"""Authoritative SPHEREx six-detector (D1-D6) LVF specifications."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DetectorSpec:
    """Properties of one SPHEREx 2040x2040 H2RG linear-variable-filter array."""

    index: int
    bandpass_name: str
    lam_min_um: float
    lam_max_um: float
    lam_mid_um: float
    resolving_power: int
    color_hex: str
    summary: str


DETECTORS: dict[int, DetectorSpec] = {
    1: DetectorSpec(
        index=1,
        bandpass_name="SPHEREx-D1",
        lam_min_um=0.744,
        lam_max_um=1.116,
        lam_mid_um=0.930,
        resolving_power=39,
        color_hex="#60a5fa",
        summary="Optical/NIR boundary; matches Gaia optical stars cleanly.",
    ),
    2: DetectorSpec(
        index=2,
        bandpass_name="SPHEREx-D2",
        lam_min_um=1.099,
        lam_max_um=1.651,
        lam_mid_um=1.375,
        resolving_power=41,
        color_hex="#34d399",
        summary="J/H near-IR; mapped to Blue in IR False-Color RGB.",
    ),
    3: DetectorSpec(
        index=3,
        bandpass_name="SPHEREx-D3",
        lam_min_um=1.636,
        lam_max_um=2.421,
        lam_mid_um=2.029,
        resolving_power=41,
        color_hex="#a3e635",
        summary="K near-IR; ideal default for stellar variability and dusty disks.",
    ),
    4: DetectorSpec(
        index=4,
        bandpass_name="SPHEREx-D4",
        lam_min_um=2.423,
        lam_max_um=3.822,
        lam_mid_um=3.123,
        resolving_power=35,
        color_hex="#facc15",
        summary="Water-ice (3.0 um) & PAH region; Green in IR False-Color RGB.",
    ),
    5: DetectorSpec(
        index=5,
        bandpass_name="SPHEREx-D5",
        lam_min_um=3.809,
        lam_max_um=4.420,
        lam_mid_um=4.115,
        resolving_power=112,
        color_hex="#fb923c",
        summary="Thermal mid-IR / CO2 (4.26 um); reveals ~250 K cold brown dwarfs.",
    ),
    6: DetectorSpec(
        index=6,
        bandpass_name="SPHEREx-D6",
        lam_min_um=4.412,
        lam_max_um=5.002,
        lam_mid_um=4.707,
        resolving_power=128,
        color_hex="#f87171",
        summary="Longest cold-glow band / CO (4.67 um); Red in IR False-Color RGB.",
    ),
}


def bandpass_to_detector(name: str | None) -> int | None:
    """Parse SIA energy_bandpassname like 'SPHEREx-D3' -> 3."""
    if not name:
        return None
    for idx, spec in DETECTORS.items():
        if spec.bandpass_name.lower() == name.strip().lower():
            return idx
    upper = name.upper()
    for idx in range(1, 7):
        if f"D{idx}" in upper:
            return idx
    return None
