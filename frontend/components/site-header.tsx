"use client";

import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/components/auth-provider";
import { RequestDemoLink } from "@/components/request-demo-link";
import { getCurrentProfile } from "@/lib/auth-client";
import { useEffect, useState } from "react";

export function SiteHeader() {
  const { user, loading, signOut } = useAuth();
  const [platformAdminForUser, setPlatformAdminForUser] = useState<{ userId: string; isAdmin: boolean } | null>(null);
  const isPlatformAdmin = !!user && platformAdminForUser?.userId === user.id && platformAdminForUser.isAdmin;
  useEffect(() => {
    if (!user) return;
    let active = true;
    getCurrentProfile<{ is_platform_admin?: boolean }>()
      .then((profile) => { if (active) setPlatformAdminForUser({ userId: user.id, isAdmin: profile.is_platform_admin === true }); })
      .catch(() => { if (active) setPlatformAdminForUser({ userId: user.id, isAdmin: false }); });
    return () => { active = false; };
  }, [user]);

  return (
    <header className="site-header">
      <div className="container header-inner">
        <Link className="brand" href="/" aria-label="CompatFlow home">
          <Image src="/compatflow-logo.svg" alt="CompatFlow" width={174} height={52} priority />
        </Link>
        <nav className="nav header-main-nav" aria-label="Main navigation">
          {user ? (
            <>
              <Link href="/">Home</Link>
              <Link href="/workspace">Workspace</Link>
              <Link href="/catalog/import">Catalog</Link>
              <Link href="/catalog/sources">Data sources</Link>
              <Link href="/reviews/write">Write a review</Link>
              <RequestDemoLink />
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
