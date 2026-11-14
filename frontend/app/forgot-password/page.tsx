"use client";

import Link from "next/link";
import { useState } from "react";
import { requestPasswordReset } from "@/lib/auth-client";

export default function ForgotPasswordPage() {
  const [email,setEmail]=useState(""); const [message,setMessage]=useState(""); const [error,setError]=useState(""); const [busy,setBusy]=useState(false);
  async function submit(event:React.FormEvent<HTMLFormElement>){event.preventDefault();setError("");setMessage("");setBusy(true);try{await requestPasswordReset(email);setMessage("If an account exists for that email, a password reset link will be sent.");}catch(e){setError(e instanceof Error?e.message:"Could not request a reset.");}finally{setBusy(false);}}
  return <main id="main" className="auth-shell"><section className="auth-card"><span className="eyebrow">ACCOUNT RECOVERY</span><h1>Reset your password</h1><p className="auth-intro">Enter your account email and we’ll send a password reset link.</p><form className="auth-form" onSubmit={submit}><label htmlFor="reset-email">Work email</label><input id="reset-email" type="email" autoComplete="email" required value={email} onChange={e=>setEmail(e.target.value)} />{error&&<p className="auth-error" role="alert">{error}</p>}{message&&<p className="auth-success" role="status">{message}</p>}<button className="button auth-submit" disabled={busy}>{busy?"Sending…":"Send reset link"}</button></form><p className="auth-switch"><Link href="/sign-in">Back to sign in</Link></p></section></main>;
}
