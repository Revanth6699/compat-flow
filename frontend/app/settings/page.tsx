"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthRequired } from "@/components/auth-required";
import { useAuth } from "@/components/auth-provider";
import { apiRequest, updatePassword, updateProfile } from "@/lib/auth-client";

function SettingsContent() {
  const { user, signOut } = useAuth();
  const router = useRouter();
  const [accountRole, setAccountRole] = useState<string | null>(null);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const requiredDeleteText = accountRole === "owner" ? "DELETE ORGANIZATION" : "DELETE MY ACCOUNT";
  const metadata = user?.user_metadata || {};
  const [fullName, setFullName] = useState(metadata.full_name || "");
  const [jobTitle, setJobTitle] = useState(metadata.job_title || "");
  const [phone, setPhone] = useState(metadata.phone || "");
  const [companyWebsite, setCompanyWebsite] = useState(metadata.company_website || "");
  const [industry, setIndustry] = useState(metadata.industry || "");
  const [teamSize, setTeamSize] = useState(metadata.team_size || "");
  const [profileMessage, setProfileMessage] = useState("");
  const [profileError, setProfileError] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordMessage, setPasswordMessage] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [busyProfile, setBusyProfile] = useState(false);
  const [busyPassword, setBusyPassword] = useState(false);

  useEffect(() => {
    void apiRequest<{ role: string }>("/api/v1/auth/me").then(profile => setAccountRole(profile.role)).catch(() => setAccountRole(null));
  }, []);

  async function deleteAccount() {
    setDeleteError("");
    if (deleteConfirmation !== requiredDeleteText) {
      setDeleteError(`Type ${requiredDeleteText} exactly to continue.`);
      return;
    }
    setDeleting(true);
    try {
      await apiRequest<{ deleted: boolean }>("/api/v1/auth/account", {
        method: "DELETE",
        body: JSON.stringify({ confirmation: requiredDeleteText }),
      });
      await signOut();
      router.replace("/");
    } catch (cause) {
      setDeleteError(cause instanceof Error ? cause.message : "Account deletion could not be completed.");
      setDeleting(false);
    }
  }

  async function saveProfile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setProfileMessage(""); setProfileError("");
    if (fullName.trim().length < 2 || jobTitle.trim().length < 2) { setProfileError("Enter a valid name and job title."); return; }
    if (phone && !/^\+?[0-9() .-]{7,20}$/.test(phone)) { setProfileError("Enter a valid phone number."); return; }
    if (companyWebsite && !/^https?:\/\//i.test(companyWebsite)) { setProfileError("Enter a valid company website URL."); return; }
    if (!industry || !teamSize) { setProfileError("Select your industry and team size."); return; }
    setBusyProfile(true);
    try {
      await updateProfile(fullName, { job_title: jobTitle.trim(), phone: phone.trim(), company_website: companyWebsite.trim(), industry, team_size: teamSize });
      setProfileMessage("Your profile details have been updated.");
    } catch (error) { setProfileError(error instanceof Error ? error.message : "Could not update profile."); }
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
    <header className="workspace-heading"><div><span className="eyebrow">ACCOUNT</span><h1>Profile settings</h1><p>Manage your personal and organization details, security and subscription.</p></div><div className="workspace-actions"><Link className="button button-secondary" href="/billing">Billing and subscription</Link><Link className="button button-secondary" href="/workspace">Back to workspace</Link></div></header>
    <section className="panel settings-panel"><h2>Profile and company information</h2><p className="settings-description">These details help identify your role and the organization using CompatFlow. Your sign-in email is managed by your authentication account.</p><form className="auth-form" onSubmit={saveProfile}>
      <label htmlFor="profile-name">Full name</label><input id="profile-name" autoComplete="name" minLength={2} maxLength={100} required value={fullName} onChange={event => setFullName(event.target.value)} />
      <label htmlFor="profile-email">Account email</label><input id="profile-email" type="email" value={user?.email || ""} readOnly />
      <label htmlFor="profile-job-title">Job title</label><input id="profile-job-title" minLength={2} maxLength={100} required value={jobTitle} onChange={event => setJobTitle(event.target.value)} />
      <label htmlFor="profile-phone">Phone number</label><input id="profile-phone" type="tel" autoComplete="tel" maxLength={20} pattern="^\+?[0-9() .-]{7,20}$" value={phone} onChange={e=>setPhone(e.target.value)} placeholder="+91 98765 43210" />
      <label htmlFor="profile-website">Company website</label><input id="profile-website" type="url" maxLength={255} value={companyWebsite} onChange={event => setCompanyWebsite(event.target.value)} placeholder="https://example.com" />
      <label htmlFor="profile-industry">Industry</label><select id="profile-industry" required value={industry} onChange={event => setIndustry(event.target.value)}><option value="">Select industry</option><option value="ecommerce">Ecommerce / D2C</option><option value="retail">Retail</option><option value="automotive">Automotive / Parts</option><option value="manufacturing">Manufacturing</option><option value="distribution">Wholesale / Distribution</option><option value="technology">Technology / Software</option><option value="other">Other</option></select>
      <label htmlFor="profile-team-size">Team size</label><select id="profile-team-size" required value={teamSize} onChange={event => setTeamSize(event.target.value)}><option value="">Select team size</option><option value="1">Just me</option><option value="2-5">2–5</option><option value="6-20">6–20</option><option value="21-50">21–50</option><option value="51-200">51–200</option><option value="201+">201+</option></select>
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
    <section className="panel settings-panel danger-zone">
      <h2>Delete account</h2>
      {accountRole === "owner" ? <p className="settings-description">Deleting the owner account permanently removes the entire company workspace: all employee accounts, organization data, import history, reviews, subscription records and payment history. Any active Razorpay subscription is sent an immediate cancellation request first. This cannot be undone.</p> : <p className="settings-description">Deleting your account permanently removes your sign-in identity and organization membership. Shared company data and the organization subscription remain with the company owner.</p>}
      <label htmlFor="delete-account-confirmation">Type <strong>{requiredDeleteText}</strong> to confirm</label>
      <input id="delete-account-confirmation" value={deleteConfirmation} onChange={event => setDeleteConfirmation(event.target.value)} autoComplete="off" spellCheck={false} placeholder={requiredDeleteText} />
      {deleteError && <p className="auth-error" role="alert">{deleteError}</p>}
      <button className="button button-danger" type="button" disabled={deleting || deleteConfirmation !== requiredDeleteText} onClick={() => void deleteAccount()}>{deleting ? "Deleting account…" : "Permanently delete account"}</button>
    </section>
  </div></main>;
}
export default function SettingsPage() { return <AuthRequired><SettingsContent /></AuthRequired>; }
