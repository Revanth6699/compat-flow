"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { signIn } from "@/lib/auth-client";

function SignInForm() {
  const router = useRouter();
  const search = useSearchParams();
  const [email,setEmail] = useState(""); const [password,setPassword] = useState("");
  const [error,setError] = useState(""); const [busy,setBusy] = useState(false);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setBusy(true);
    try { await signIn(email,password); const next = search.get("next"); router.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : "/"); }
    catch (e) { setError(e instanceof Error ? e.message : "Unable to sign in."); }
    finally { setBusy(false); }
  }
  return <main id="main" className="auth-shell"><section className="auth-card">
    <span className="eyebrow">COMPATFLOW ACCOUNT</span><h1>Sign in</h1><p className="auth-intro">Access your organization’s supplier catalog workspace.</p>
    <form className="auth-form" onSubmit={submit}>
      <label htmlFor="signin-email">Work email</label><input id="signin-email" type="email" autoComplete="email" required value={email} onChange={e=>setEmail(e.target.value)} />
      <label htmlFor="signin-password">Password</label><input id="signin-password" type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)} />
      <div className="auth-inline"><Link href="/forgot-password">Forgot password?</Link></div>
      {error && <p className="auth-error" role="alert">{error}</p>}
      <button className="button auth-submit" disabled={busy}>{busy?"Signing in…":"Sign in"}</button>
    </form>
    <p className="auth-switch">New to CompatFlow? <Link href="/sign-up">Create an account</Link></p>
  </section><aside className="auth-welcome"><span className="auth-welcome-kicker">SUPPLIER DATA OPERATIONS</span><h2>Welcome back.</h2><p>Bring your supplier and product information into one reliable workspace. Review catalog quality before it reaches your systems.</p></aside></main>;
}

export default function SignInPage() { return <Suspense fallback={<main id="main" className="auth-shell">Loading…</main>}><SignInForm /></Suspense>; }
