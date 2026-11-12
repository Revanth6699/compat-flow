import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "CompatFlow — Supplier Catalog Change Operations";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "center", padding: 84, background: "#edf3fb", color: "#102d53" }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: "#174ea6" }}>COMPATFLOW</div>
        <div style={{ fontSize: 68, fontWeight: 800, lineHeight: 1.05, marginTop: 34 }}>Supplier catalog<br/>change operations.</div>
        <div style={{ fontSize: 27, marginTop: 32, color: "#374151" }}>Import. Normalize. Reconcile. Prepare updates.</div>
      </div>
    ),
    size
  );
}
