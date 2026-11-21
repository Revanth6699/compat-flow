"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";

export function NavigationProgress() {
  const pathname = usePathname();
  const [active, setActive] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const handleNavigation = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const target = event.target;
      if (!(target instanceof Element)) return;
      const anchor = target.closest("a[href]");
      if (!(anchor instanceof HTMLAnchorElement)) return;
      if (anchor.target && anchor.target !== "_self") return;
      if (anchor.hasAttribute("download")) return;

      const destination = new URL(anchor.href, window.location.href);
      if (destination.origin !== window.location.origin) return;
      if (destination.pathname === window.location.pathname && destination.search === window.location.search) return;

      setActive(true);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setActive(false), 10000);
    };

    document.addEventListener("click", handleNavigation, true);
    return () => {
      document.removeEventListener("click", handleNavigation, true);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  useEffect(() => {
    if (!active) return;
    const finish = window.setTimeout(() => setActive(false), 180);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    return () => window.clearTimeout(finish);
  }, [pathname, active]);

  return (
    <div className={`navigation-progress${active ? " is-active" : ""}`} aria-hidden="true">
      <span className="navigation-progress-track" />
      <span className="navigation-progress-glow" />
    </div>
  );
}
