"use client";

import { useState, useSyncExternalStore } from "react";

type Preferences = { essential: true; analytics: boolean; marketing: boolean; savedAt: string };
const STORAGE_KEY = "compatflow-privacy-preferences";
const defaults: Preferences = { essential: true, analytics: false, marketing: false, savedAt: "" };

function subscribe(callback: () => void) {
  const onManage = () => {
    try { window.localStorage.removeItem(STORAGE_KEY); } catch { /* Keep preference controls available. */ }
    callback();
  };
  window.addEventListener("storage", callback);
  window.addEventListener("compatflow:manage-privacy", onManage);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("compatflow:manage-privacy", onManage);
  };
}
function getSnapshot() {
  try { return window.localStorage.getItem(STORAGE_KEY); } catch { return null; }
}
function getServerSnapshot() { return null; }

export function CookieConsent() {
  const savedPreferences = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const [customizing, setCustomizing] = useState(false);
  const [analytics, setAnalytics] = useState(false);
  const [marketing, setMarketing] = useState(false);

  function save(next: Preferences) {
    try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch { /* Essential app use remains available. */ }
    window.dispatchEvent(new Event("storage"));
    window.dispatchEvent(new CustomEvent("compatflow:consent-changed", { detail: next }));
    setCustomizing(false);
  }

  if (savedPreferences !== null) return null;
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
