"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { setSessionFromCallback, updatePassword } from "@/lib/auth-client";

export default function ResetPasswordPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    void Promise.resolve().then(async () => {
      const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
      const access_token = hash.get("access_token");
      const refresh_token = hash.get("refresh_token");
      if (!access_token || !refresh_token) throw new Error("This reset link is invalid or expired. Request another one.");
      const response = await fetch(`${process.env.NEXT_PUBLIC_SUPABASE_URL}/auth/v1/user`, {
        headers: { apikey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "", Authorization: `Bearer ${access_token}` },
      });
      if (!response.ok) throw new Error("This reset link is invalid or expired.");
      const user = await response.json();
      if (!active) return;
      setSessionFromCallback({ access_token, refresh_token, user: { id: user.id, email: user.email } });
      setReady(true);
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : "Could not verify reset link.");
    });
    return () => { active = false; };
  }, []);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (password.length < 10) { setError("Use a password with at least 10 characters."); return; }
    if (password !== confirm) { setError("The passwords do not match."); return; }
    setBusy(true);
    try { await updatePassword(password); router.replace("/sign-in?reset=success"); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not update password."); }
    finally { setBusy(false); }
  }

  return <main id="main" className="auth-shell"><section className="auth-card"><span className="eyebrow">ACCOUNT RECOVERY</span><h1>Choose a new password</h1>{ready ? <form className="auth-form" onSubmit={submit}><label htmlFor="new-password">New password</label><input id="new-password" type="password" autoComplete="new-password" minLength={10} required value={password} onChange={event => setPassword(event.target.value)} /><label htmlFor="confirm-new-password">Confirm new password</label><input id="confirm-new-password" type="password" autoComplete="new-password" minLength={10} required value={confirm} onChange={event => setConfirm(event.target.value)} />{error && <p className="auth-error" role="alert">{error}</p>}<button className="button auth-submit" disabled={busy}>{busy ? "Updating…" : "Update password"}</button></form> : <p className={error ? "auth-error" : "auth-intro"} role={error ? "alert" : "status"}>{error || "Verifying your reset link…"}</p>}<p className="auth-switch"><Link href="/sign-in">Back to sign in</Link></p></section></main>;
}
