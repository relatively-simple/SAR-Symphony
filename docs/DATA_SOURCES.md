# Data Sources & Public Archival Endpoints (Zero API Keys Required)

All data queried and bundled by KurinjiKumaraN comes exclusively from open, unauthenticated public astronomical archives:

1. **NASA/IPAC IRSA — SPHEREx SIAv2 Service**
   - Collections: `spherex_dr1` (**DR1 Level-2 Images**, DOI `10.26131/IRSA678`) and `spherex_qr3` (**QR3 Level-2 Images**, DOI `10.26131/IRSA662`).
   - Query URL: `https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_dr1` / `spherex_qr3`
   - Optimization: Targeted HTTP `Range` byte reads parse Primary/IMAGE headers, `FLAGS` Rice-compressed binary tile pointers (`ZTILE2=1`), `VARIANCE`, `ZODI`, and trailing `WCS-WAVE` extension directly, skipping the ~4–16 MB `EPSF` table (`~1.7–3.3x` faster than IRSA server cutouts with bit-exact pixel parity), falling back automatically to IRSA `?center=&size=` cutouts if needed.

2. **ESA Gaia Archive — DR3 TAP ADQL Service**
   - URL: `https://gea.esac.esa.int/tap-server/tap/sync` (`gaiadr3.gaia_source`)
   - Supplies optical positions, G magnitudes, and proper motions (`pmra`, `pmdec`) propagated on the fly to any displayed pass epoch (`MJD`).

3. **NASA/IPAC IRSA Gator — AllWISE Source Catalog**
   - URL: `https://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query` (`allwise_p3as_psd`)
   - Supplies 2010–2011 mid-infrared (`W1`, `W2`) reference positions to highlight 15-year astrometric displacements.

4. **SIMBAD Astronomical Database & Aladin Lite v3**
   - SIMBAD (`https://simbad.harvard.edu/simbad/sim-script`) verified reference coordinates & proper motions during preset auditing.
   - Aladin Lite v3 (`https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.js`) powers the optional wide-field multi-survey context modal (`P/allWISE/color`, `P/2MASS/color`, `P/DSS2/color`).
