"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { setSessionFromCallback } from "@/lib/auth-client";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void Promise.resolve().then(async () => {
      const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
      const access_token = hash.get("access_token");
      const refresh_token = hash.get("refresh_token");
      if (!access_token || !refresh_token) {
        const params = new URLSearchParams(window.location.search);
        if (params.has("code")) {
          throw new Error("This confirmation link returned an authorization code, but this client currently expects Supabase's implicit token callback. Configure the Supabase confirmation template to use the token callback.");
        }
        throw new Error("The confirmation link is missing or expired. Request a new confirmation email.");
      }
      const response = await fetch(`${process.env.NEXT_PUBLIC_SUPABASE_URL}/auth/v1/user`, {
        headers: { apikey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "", Authorization: `Bearer ${access_token}` },
      });
      if (!response.ok) throw new Error("The confirmation link is invalid or expired.");
      const user = await response.json();
      if (!active) return;
      const expires_in = Number(hash.get("expires_in") || 3600);
      setSessionFromCallback({ access_token, refresh_token, expires_at: Date.now() / 1000 + expires_in, user: { id: user.id, email: user.email } });
      const next = new URLSearchParams(window.location.search).get("next");
      router.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : "/workspace");
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : "Could not verify your account.");
    });
    return () => { active = false; };
  }, [router]);

  return <main id="main" className="auth-shell"><section className="auth-card"><span className="eyebrow">EMAIL CONFIRMATION</span><h1>Confirming your account</h1>{error ? <><p className="auth-error" role="alert">{error}</p><Link href="/sign-in">Return to sign in</Link></> : <p className="auth-intro">Verifying your email confirmation. This may take a moment…</p>}</section></main>;
}
