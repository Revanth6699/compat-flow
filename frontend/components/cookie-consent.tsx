"use client";

import { useEffect, useState } from "react";

type Preferences = { essential: true; analytics: boolean; marketing: boolean; savedAt: string };
const STORAGE_KEY = "compatflow-privacy-preferences";
const defaults: Preferences = { essential: true, analytics: false, marketing: false, savedAt: "" };
function readPreferences(): Preferences | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<Preferences>;
    return { essential: true, analytics: parsed.analytics === true, marketing: parsed.marketing === true, savedAt: String(parsed.savedAt || "") };
  } catch { return null; }
}
export function CookieConsent() {
  const [preferences, setPreferences] = useState<Preferences | null>(null);
  const [customizing, setCustomizing] = useState(false);
  const [analytics, setAnalytics] = useState(false);
  const [marketing, setMarketing] = useState(false);
  useEffect(() => {
    const current = readPreferences();
    setPreferences(current);
    setAnalytics(current?.analytics ?? false);
    setMarketing(current?.marketing ?? false);
    const manage = () => { const saved = readPreferences(); setAnalytics(saved?.analytics ?? false); setMarketing(saved?.marketing ?? false); setPreferences(null); setCustomizing(true); };
    window.addEventListener("compatflow:manage-privacy", manage);
    return () => window.removeEventListener("compatflow:manage-privacy", manage);
  }, []);
  function save(next: Preferences) {
    try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch { /* Essential app use remains available. */ }
    setPreferences(next);
    setCustomizing(false);
    window.dispatchEvent(new CustomEvent("compatflow:consent-changed", { detail: next }));
  }
  if (preferences) return null;
  return <aside className="cookie-banner" aria-label="Privacy preferences" role="dialog" aria-modal="false">
    <strong>Privacy preferences</strong>
    <p style={{ margin: "8px 0 0", color: "#686B70", fontSize: 14 }}>Essential storage is always active for sign-in and security. Optional analytics and marketing technologies are off unless you choose them. No non-essential tracker is currently configured by this application.</p>
    {customizing && <div className="privacy-preference-options">
      <label><input type="checkbox" checked disabled /> Essential storage (always active)</label>
      <label><input type="checkbox" checked={analytics} onChange={e=>setAnalytics(e.target.checked)} /> Analytics (optional)</label>
      <label><input type="checkbox" checked={marketing} onChange={e=>setMarketing(e.target.checked)} /> Marketing (optional)</label>
    </div>}
    <div className="cookie-actions">
      <button onClick={() => save({ ...defaults, savedAt: new Date().toISOString() })}>Reject optional</button>
      <button onClick={() => save({ essential: true, analytics: true, marketing: true, savedAt: new Date().toISOString() })}>Accept all</button>
      {customizing ? <button className="accept" onClick={() => save({ essential: true, analytics, marketing, savedAt: new Date().toISOString() })}>Save choices</button> : <button className="accept" onClick={() => setCustomizing(true)}>Customize</button>}
    </div>
  </aside>;
}
