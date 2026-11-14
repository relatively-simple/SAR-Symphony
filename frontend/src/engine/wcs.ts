import type { GridSpec } from "../api/types";

const DEG2RAD = Math.PI / 180.0;
const RAD2DEG = 180.0 / Math.PI;

/** Convert ICRS (ra, dec) degrees into FITS pixel coordinates (px, py) on shared TAN grid. */
export function skyToFitsPixel(raDeg: number, decDeg: number, grid: GridSpec): [number, number] {
  const crval0 = grid.ra0 * DEG2RAD;
  const crval1 = grid.dec0 * DEG2RAD;
  const crpix = (grid.npix - 1) * 0.5;
  const cdelt = grid.pixscale_arcsec / 3600.0;

  const ra = raDeg * DEG2RAD;
  const dec = decDeg * DEG2RAD;
  const dra = ra - crval0;

  const cosDec = Math.cos(dec);
  const sinDec = Math.sin(dec);
  const cosDec0 = Math.cos(crval1);
  const sinDec0 = Math.sin(crval1);

  const denom = sinDec * sinDec0 + cosDec * cosDec0 * Math.cos(dra);
  if (denom <= 1e-6) return [NaN, NaN];

  const xRad = (cosDec * Math.sin(dra)) / denom;
  const yRad = (sinDec * cosDec0 - cosDec * sinDec0 * Math.cos(dra)) / denom;

  const dxDeg = (xRad * RAD2DEG) / -cdelt; // East left => negative CDELT1
  const dyDeg = (yRad * RAD2DEG) / cdelt;  // North up => positive CDELT2
  return [crpix + dxDeg, crpix + dyDeg];
}

/** Convert HTML5 Canvas display coordinates [0..width, 0..height] into ICRS (ra, dec) degrees. */
export function canvasToSky(
  canvasX: number,
  canvasY: number,
  canvasWidth: number,
  canvasHeight: number,
  grid: GridSpec
): { ra: number; dec: number; fitsX: number; fitsY: number } {
  const fitsX = (canvasX / canvasWidth) * grid.npix - 0.5;
  const canvasRow = (canvasY / canvasHeight) * grid.npix - 0.5;
  const fitsY = grid.npix - 1 - canvasRow;

  const crpix = (grid.npix - 1) * 0.5;
  const cdelt = grid.pixscale_arcsec / 3600.0;
  const xRad = (fitsX - crpix) * -cdelt * DEG2RAD;
  const yRad = (fitsY - crpix) * cdelt * DEG2RAD;

  const ra0 = grid.ra0 * DEG2RAD;
  const dec0 = grid.dec0 * DEG2RAD;
  const rho = Math.hypot(xRad, yRad);

  if (rho < 1e-12) {
    return { ra: grid.ra0, dec: grid.dec0, fitsX, fitsY };
  }
  const c = Math.atan(rho);
  const sinC = Math.sin(c);
  const cosC = Math.cos(c);

  const dec = Math.asin(cosC * Math.sin(dec0) + (yRad * sinC * Math.cos(dec0)) / rho);
  const ra =
    ra0 +
    Math.atan2(xRad * sinC, rho * Math.cos(dec0) * cosC - yRad * Math.sin(dec0) * sinC);

  return {
    ra: ((ra * RAD2DEG) % 360 + 360) % 360,
    dec: dec * RAD2DEG,
    fitsX,
    fitsY,
  };
}
