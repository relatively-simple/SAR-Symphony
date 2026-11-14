# Scientific Methodology & Data Processing

## 1. Per-Exposure Calibration & Cleaning (`app/science/clean.py`)
Each SPHEREx Level-2 Multi-Extension FITS (`MEF`) file contains pixel radiance in `MJy/sr` (`IMAGE`), the mission zodiacal light model (`ZODI`), pixel variance (`VARIANCE`), bitmask flags (`FLAGS`), and spectral wavelength calibration (`WCS-WAVE`). Before combining any frame:
1. Subtract `ZODI` directly from `IMAGE` (`net = IMAGE - ZODI`) to suppress bright seasonal interplanetary dust glow.
2. Mask fatal SPHEREx bit flags (`TRANSIENT=0`, `OVERFLOW=1`, `SUR_ERROR=2`, `NONFUNC=15`, `DICHROIC=19`, `MISSING_DATA=21` in the Level-2 bitmask) to `NaN` for coadds while preserving compact 6-bit mask flags for interactive Pro-Control inspection.

## 2. Proper-Motion Coordinate Accuracy (`app/core/coords.py`)
SPHEREx observes ~26 years after **J2000** (`2000.0`). Fast nearby stars and brown dwarfs move many pixels over a quarter-century (`WISE 0855` moves ~212 arcsec; `Barnard's Star` moves ~270 arcsec; `epsilon Indi B` moves ~122 arcsec). We propagate official Gaia DR3 / SIMBAD ICRS coordinates and proper motions strictly to the midpoint epoch of each target's SPHEREx passes before querying IRSA SIAv2. For `R Draconis`, we use verified ICRS J2000 coordinates (`248.167611°, +66.754979°`) rather than typo'd legacy tables, and for `epsilon Indi B` we target the brown dwarf itself (`331.044147°, -56.782844°`) rather than parent star `eps Ind`.

## 3. Temporal Pass Grouping & Lenses (`app/data/planner.py`, `app/science/products.py`)
IRSA results sorted across **DR1 + QR3** are partitioned whenever consecutive observation midpoints (`MJD`) differ by >45 days, separating SPHEREx's ~6-month sky visits.
- **Motion Finder (`diffs`):** Outlier-clipped inverse-variance median per pass minus Pass 0 (`Pass_n - Pass_0`), scaled diverging red/cyan.
- **Cold Glow (`coldglow`):** Inverse-variance stack combining only SPHEREx's longest thermal detectors (`D5 + D6`, `3.8–5.0 µm`) per pass, maximizing signal-to-noise on cold methane-bearing Y/T dwarfs (`WISE 0855`, `eps Indi B`) that fade at shorter wavelengths.
- **Variable Watch (`pass_coadds`):** Per-pass calibrated brightness (`MJy/sr`) across 6-month intervals.
- **False-Color IR (`rgb`):** Continuous wavelength mapping `B = D1+D2`, `G = D3+D4`, `R = D5+D6`.

## 4. Click-to-Spectrum (`app/science/spectrum.py`)
Clicking any sky coordinate maps `(RA, Dec)` through each exposure's `-SIP` astrometric WCS and evaluates the native SPHEREx linear variable filter dispersion (`WCS-WAVE`) directly at `(px, py)`. Local median sky background in an annular ring (`3–6 px`) is subtracted per exposure. For bright saturated cores (`OVERFLOW`) such as Barnard's Star, if zero strict core exposures remain unmasked, the extractor samples unmasked PSF wing halo pixels (`r <= 3.2 px`) and marks all points as PSF-halo lower limits.

## 5. Honest Detection Boundaries
SPHEREx's ~6.2" pixels and single-pass noise floor (~mJy regime per exposure) cleanly reveal fast brown dwarfs down to `WISE 0855` (`W2 ~ 14 mag`), luminous variable giants, and nearby high-PM stars, whereas ultra-faint theoretical outer Solar System objects (`V > 22 mag`) remain below unstacked per-pass sensitivity and require dedicated multi-exposure shift-and-stack searches.
