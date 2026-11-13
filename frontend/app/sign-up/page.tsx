"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { signUp } from "@/lib/auth-client";

function SignUpForm() {
  const search = useSearchParams();
  const [email,setEmail] = useState(""); const [password,setPassword] = useState(""); const [confirm,setConfirm] = useState("");
  const [message,setMessage] = useState(""); const [error,setError] = useState(""); const [busy,setBusy] = useState(false);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setMessage("");
    if(password.length<10){setError("Use a password with at least 10 characters.");return;}
    if(password!==confirm){setError("The passwords do not match.");return;}
    setBusy(true);
    try {
      const result=await signUp(email,password,search.get("next") || "/workspace");
      setMessage(result.access_token ? "Account created. Your organization access must be provisioned or linked through an invitation." : "Check your email and confirm your address. After confirmation, sign in with your new password. Organization access is granted separately.");
    } catch(e) { setError(e instanceof Error?e.message:"Could not create your account."); }
    finally { setBusy(false); }
  }
  return <main id="main" className="auth-shell"><section className="auth-card">
    <span className="eyebrow">GET STARTED</span><h1>Create your account</h1><p className="auth-intro">Create a verified CompatFlow identity. An account alone does not create an organization or grant workspace access.</p>
    <form className="auth-form" onSubmit={submit}>
      <label htmlFor="signup-email">Work email</label><input id="signup-email" type="email" autoComplete="email" required value={email} onChange={e=>setEmail(e.target.value)} />
      <label htmlFor="signup-password">Password</label><input id="signup-password" type="password" autoComplete="new-password" minLength={10} required value={password} onChange={e=>setPassword(e.target.value)} />
      <label htmlFor="signup-confirm">Confirm password</label><input id="signup-confirm" type="password" autoComplete="new-password" minLength={10} required value={confirm} onChange={e=>setConfirm(e.target.value)} />
      {error && <p className="auth-error" role="alert">{error}</p>}{message && <p className="auth-success" role="status">{message}</p>}
      <button className="button auth-submit" disabled={busy}>{busy?"Creating account…":"Create account"}</button>
    </form>
    <p className="auth-switch">Already registered? <Link href="/sign-in">Sign in</Link></p>
  </section></main>;
}

export default function SignUpPage() { return <Suspense fallback={<main id="main" className="auth-shell">Loading…</main>}><SignUpForm /></Suspense>; }
