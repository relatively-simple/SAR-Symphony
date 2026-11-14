# AI & Tooling Transparency Disclosure

Per NASA Space Apps Challenge rules regarding use of Artificial Intelligence (AI) tools:

- **AI Assistant Used:** Antigravity (Google DeepMind coding & research assistant) was used by Team KurinjiKumaraN to architect the Python/FastAPI + React/Canvas application, generate code and unit/integration tests, audit live IRSA/SIMBAD/Gaia endpoints, and verify data processing behavior.
- **Origin of Data & Computations:** Zero synthetic, fabricated, or AI-generated imagery or spectra are presented as astronomical data. Every pixel, error variance, flag mask, wavelength value (`WCS-WAVE`), and catalog overlay rendered in the workbench is fetched verbatim from NASA/IPAC IRSA, ESA Gaia DR3, and IRSA AllWISE public archives and processed deterministically with open-source scientific Python libraries (`astropy`, `reproject`, `numpy`, `scipy`).
- **Verification:** All pipeline stages (Range vs Cutout bit-exact FITS verification, coordinate propagation, flag masking, coadd/dipole physics, SFP1 serialization, API endpoints, and rendered UI DOM/canvas verification) were executed and verified in this repository.
