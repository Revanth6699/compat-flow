"use client";

import Link from "next/link";
import { useAuth } from "@/components/auth-provider";
import { apiRequest } from "@/lib/auth-client";
import { useEffect, useState } from "react";

export function SiteHeader() {
  const { user, loading, signOut } = useAuth();
  const [isPlatformAdmin, setIsPlatformAdmin] = useState(false);
  useEffect(() => {
    let active = true;
    setIsPlatformAdmin(false);
    if (user) apiRequest<{ is_platform_admin?: boolean }>("/api/v1/auth/me")
      .then((profile) => { if (active) setIsPlatformAdmin(profile.is_platform_admin === true); })
      .catch(() => { if (active) setIsPlatformAdmin(false); });
    return () => { active = false; };
  }, [user]);

  return (
    <header className="site-header">
      <div className="container header-inner">
        <Link className="brand" href="/" aria-label="CompatFlow home">
          compat<span className="brand-mark">flow</span>
        </Link>
        <nav className="nav header-main-nav" aria-label="Main navigation">
          {user ? (
            <>
              <Link href="/">Home</Link>
              <Link href="/workspace">Workspace</Link>
              <Link href="/catalog/import">Catalog</Link>
              <Link href="/catalog/sources">Data sources</Link>
              {!isPlatformAdmin && <Link href="/pricing">Plans</Link>}
              {isPlatformAdmin && <Link href="/platform-admin">Platform admin</Link>}
            </>
          ) : (
            <>
              <Link href="/">Home</Link>
              <Link href="/#capabilities">Capabilities</Link>
              <Link href="/#workflow">How it works</Link>
              <Link href="/pricing">Pricing</Link>
              <Link href="/contact?intent=demo">Request demo</Link>
              <Link href="/reviews">Reviews</Link>
            </>
          )}
        </nav>
        <nav className="nav header-account-nav" aria-label="Account navigation">
          {!loading && (user ? (
            <>
              <Link href="/settings">Profile</Link>
              <Link href="/" onClick={() => void signOut()}>Sign out</Link>
            </>
          ) : (
            <>
              <Link href="/sign-in">Sign in</Link>
              <Link className="nav-get-started" href="/sign-up">Create account</Link>
            </>
          ))}
        </nav>
      </div>
    </header>
  );
}
