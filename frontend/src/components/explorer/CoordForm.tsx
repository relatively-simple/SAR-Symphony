import React, { useEffect, useState } from "react";
import { useAppState } from "../../state/store";

const QUICK_EXAMPLES = [
  { label: "WISE 0855 (Y Dwarf)", ra: "133.7951", dec: "-7.2451", fov: 0.05 },
  { label: "Barnard's Star (2026)", ra: "269.4462", dec: "4.7687", fov: 0.05 },
  { label: "R Draconis (Mira)", ra: "248.1676", dec: "66.7550", fov: 0.05 },
];

export const CoordForm: React.FC = () => {
  const { manifest, exploring, runExplore } = useAppState();
  const [ra, setRa] = useState("133.7951");
  const [dec, setDec] = useState("-7.2451");
  const [fov, setFov] = useState<number>(0.05);

  useEffect(() => {
    if (manifest) {
      setRa(manifest.grid.ra0.toFixed(6));
      setDec(manifest.grid.dec0.toFixed(6));
      setFov(manifest.grid.fov_deg);
    }
  }, [manifest]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runExplore(ra.trim(), dec.trim(), fov);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.7rem" }}>
      <form className="coord-form" onSubmit={handleSubmit}>
        <div className="field-group" style={{ flex: "1 1 170px" }}>
          <label className="field-label" htmlFor="explore-ra">
            RA (deg or HHhMMmSSs)
          </label>
          <input
            id="explore-ra"
            className="text-input mono"
            type="text"
            value={ra}
            onChange={(e) => setRa(e.target.value)}
            placeholder="e.g. 133.7951 or 08h55m10.8s"
            required
          />
        </div>

        <div className="field-group" style={{ flex: "1 1 170px" }}>
          <label className="field-label" htmlFor="explore-dec">
            Dec (deg or DDdMMmSSs)
          </label>
          <input
            id="explore-dec"
            className="text-input mono"
            type="text"
            value={dec}
            onChange={(e) => setDec(e.target.value)}
            placeholder="e.g. -7.2451 or -07d14m42s"
          />
        </div>

        <div className="field-group">
          <label className="field-label" htmlFor="explore-fov">
            Field of View
          </label>
          <select
            id="explore-fov"
            className="select-input"
            value={fov}
            onChange={(e) => setFov(Number(e.target.value))}
          >
            <option value={0.05}>0.05&deg; (3&apos; &middot; crisp)</option>
            <option value={0.1}>0.10&deg; (6&apos; &middot; wide)</option>
            <option value={0.25}>0.25&deg; (15&apos; &middot; survey)</option>
          </select>
        </div>

        <button type="submit" className="btn btn-primary" disabled={exploring}>
          {exploring ? "Scanning Archive..." : "Scan Sky Patch"}
        </button>
      </form>

      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "0.45rem" }}>
        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Try coordinates:</span>
        {QUICK_EXAMPLES.map((ex) => (
          <button
            key={ex.label}
            type="button"
            className="detector-chip"
            disabled={exploring}
            onClick={() => {
              setRa(ex.ra);
              setDec(ex.dec);
              setFov(ex.fov);
              runExplore(ex.ra, ex.dec, ex.fov);
            }}
          >
            {ex.label}
          </button>
        ))}
      </div>
    </div>
  );
};
