
"use client";

import { useState } from "react";

type Consent = "accepted" | "rejected";

const STORAGE_KEY = "compatflow-cookie-consent";

export function CookieConsent() {
  const [visible, setVisible] = useState(() => {
    try {
      return (
        typeof window !== "undefined" &&
        window.localStorage.getItem(STORAGE_KEY) === null
      );
    } catch {
      return false;
    }
  });

  function choose(value: Consent) {
    try {
      window.localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // Keep the current page usable if browser storage is unavailable.
    }

    setVisible(false);
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

      <p style={{ margin: "8px 0 0", color: "#374151", fontSize: 14 }}>
        This demo uses essential browser storage to remember your
        preference. It does not currently load advertising or analytics
        cookies.
      </p>

      <div className="cookie-actions">
        <button
          className="accept"
          onClick={() => choose("accepted")}
        >
          Accept
        </button>

        <button onClick={() => choose("rejected")}>
          Reject optional cookies
        </button>
      </div>
    </aside>
  );
}
