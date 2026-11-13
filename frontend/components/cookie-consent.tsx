"use client";

import { useSyncExternalStore } from "react";

type Consent = "accepted" | "rejected";
const STORAGE_KEY = "compatflow-cookie-consent";

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  return () => window.removeEventListener("storage", callback);
}

function getSnapshot() {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === null;
  } catch {
    return false;
  }
}

function getServerSnapshot() {
  return false;
}

export function CookieConsent() {
  const visible = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  function choose(value: Consent) {
    try {
      window.localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // Keep the page usable when browser storage is unavailable.
    }
    window.dispatchEvent(new Event("storage"));
  }

  if (!visible) return null;

  return (
    <aside
      className="cookie-banner"
      aria-label="Cookie preferences"
      role="dialog"
      aria-live="polite"
    >
      <strong>Privacy preferences</strong>
      <p style={{ margin: "8px 0 0", color: "#686B70", fontSize: 14 }}>
        This demo uses essential browser storage to remember your preference.
        It does not currently load advertising or analytics cookies.
      </p>
      <div className="cookie-actions">
        <button className="accept" onClick={() => choose("accepted")}>
          Accept
        </button>
        <button onClick={() => choose("rejected")}>
          Reject optional cookies
        </button>
      </div>
    </aside>
  );
}
