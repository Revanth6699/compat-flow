"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthRequired } from "@/components/auth-required";
import { useAuth } from "@/components/auth-provider";
import { updatePassword, updateProfile } from "@/lib/auth-client";

function SettingsContent() {
  const { user, signOut } = useAuth();
  const [fullName, setFullName] = useState(user?.user_metadata?.full_name || "");
  const [profileMessage, setProfileMessage] = useState("");
  const [profileError, setProfileError] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordMessage, setPasswordMessage] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [busyProfile, setBusyProfile] = useState(false);
  const [busyPassword, setBusyPassword] = useState(false);

  async function saveProfile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setProfileMessage(""); setProfileError(""); setBusyProfile(true);
    try { await updateProfile(fullName); setProfileMessage("Your profile details have been updated."); }
    catch (error) { setProfileError(error instanceof Error ? error.message : "Could not update profile."); }
    finally { setBusyProfile(false); }
  }
  async function savePassword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPasswordMessage(""); setPasswordError("");
    if (password.length < 10) { setPasswordError("Use at least 10 characters."); return; }
    if (password !== confirmPassword) { setPasswordError("The passwords do not match."); return; }
    setBusyPassword(true);
    try { await updatePassword(password); setPassword(""); setConfirmPassword(""); setPasswordMessage("Your password has been changed."); }
    catch (error) { setPasswordError(error instanceof Error ? error.message : "Could not change password."); }
    finally { setBusyPassword(false); }
  }

  return <main id="main" className="page"><div className="container account-settings">
    <header className="workspace-heading"><div><span className="eyebrow">ACCOUNT</span><h1>Profile settings</h1><p>Manage your account details and sign-in credentials.</p></div><div className="workspace-actions"><Link className="button button-secondary" href="/billing">Billing and subscription</Link><Link className="button button-secondary" href="/workspace">Back to workspace</Link></div></header>
    <section className="panel settings-panel"><h2>Profile information</h2><form className="auth-form" onSubmit={saveProfile}>
      <label htmlFor="profile-name">Full name</label><input id="profile-name" autoComplete="name" maxLength={100} value={fullName} onChange={event => setFullName(event.target.value)} placeholder="Enter your name" />
      <label htmlFor="profile-email">Account email</label><input id="profile-email" type="email" value={user?.email || ""} readOnly aria-describedby="email-help" /><small id="email-help">Your sign-in email is managed by your authentication account. Contact an administrator if it needs to change.</small>
      {profileError && <p className="auth-error" role="alert">{profileError}</p>}{profileMessage && <p className="auth-success" role="status">{profileMessage}</p>}
      <button className="button auth-submit" disabled={busyProfile}>{busyProfile ? "Saving…" : "Save profile"}</button>
    </form></section>
    <section className="panel settings-panel"><h2>Change password</h2><p className="settings-description">Choose a password with at least 10 characters. Use a unique password you do not use on another service.</p><form className="auth-form" onSubmit={savePassword}>
      <label htmlFor="settings-password">New password</label><input id="settings-password" type="password" autoComplete="new-password" minLength={10} required value={password} onChange={event => setPassword(event.target.value)} />
      <label htmlFor="settings-confirm-password">Confirm new password</label><input id="settings-confirm-password" type="password" autoComplete="new-password" minLength={10} required value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} />
      {passwordError && <p className="auth-error" role="alert">{passwordError}</p>}{passwordMessage && <p className="auth-success" role="status">{passwordMessage}</p>}
      <button className="button auth-submit" disabled={busyPassword}>{busyPassword ? "Updating…" : "Update password"}</button>
    </form></section>
    <section className="panel settings-panel"><h2>Account and privacy</h2><p className="settings-description">CompatFlow uses your account details to authenticate you and associate your access with an organization. You can review how information is processed in the <Link href="/privacy">Privacy Policy</Link>.</p><button className="button button-secondary" onClick={() => void signOut()}>Sign out</button></section>
  </div></main>;
}
export default function SettingsPage() { return <AuthRequired><SettingsContent /></AuthRequired>; }
