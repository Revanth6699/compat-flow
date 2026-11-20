"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthRequired } from "@/components/auth-required";
import { useAuth } from "@/components/auth-provider";
import { apiRequest, ApiRequestError, updatePassword, updateProfile } from "@/lib/auth-client";

type OwnReview = { id: string; display_name: string; rating: number; comment: string; created_at: string };
type OwnReviewReply = { id: string; review_id: string; display_name: string; comment: string; created_at: string };

function SettingsContent() {
  const { user, signOut } = useAuth();
  const router = useRouter();
  const [accountRole, setAccountRole] = useState<string | null>(null);
  const [roleLoading, setRoleLoading] = useState(true);
  const [roleError, setRoleError] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const requiredDeleteText = accountRole === "owner" ? "DELETE ORGANIZATION" : "DELETE MY ACCOUNT";
  const confirmationMatches = deleteConfirmation.trim().toUpperCase() === requiredDeleteText;
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
  const [myReview, setMyReview] = useState<OwnReview | null>(null);
  const [myReviewReplies, setMyReviewReplies] = useState<OwnReviewReply[]>([]);
  const [myReviewLoading, setMyReviewLoading] = useState(true);
  const [myReplyText, setMyReplyText] = useState("");
  const [myReplyName, setMyReplyName] = useState(metadata.full_name || "");
  const [myReviewMessage, setMyReviewMessage] = useState("");
  const [myReviewError, setMyReviewError] = useState("");
  const [myReviewBusy, setMyReviewBusy] = useState(false);

  useEffect(() => {
    let active = true;
    void apiRequest<{ role: string }>("/api/v1/auth/me")
      .then(profile => { if (active) { setAccountRole(profile.role); setRoleError(""); } })
      .catch(error => { if (active) setRoleError(error instanceof Error ? error.message : "Could not verify your organization role."); })
      .finally(() => { if (active) setRoleLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    void apiRequest<OwnReview>("/api/v1/reviews/mine")
      .then(async review => {
        if (!active) return;
        setMyReview(review);
        const replies = await apiRequest<OwnReviewReply[]>("/api/v1/reviews/" + review.id + "/replies");
        if (active) setMyReviewReplies(replies);
      })
      .catch(cause => {
        if (cause instanceof ApiRequestError && cause.status === 404) {
          if (active) { setMyReview(null); setMyReviewReplies([]); }
        } else if (active) {
          setMyReviewError(cause instanceof Error ? cause.message : "Could not load your review.");
        }
      })
      .finally(() => { if (active) setMyReviewLoading(false); });
    return () => { active = false; };
  }, []);

  async function deleteMyReview() {
    if (!myReview || !window.confirm("Delete your published review and all replies? This cannot be undone.")) return;
    setMyReviewBusy(true); setMyReviewError(""); setMyReviewMessage("");
    try {
      await apiRequest<{ deleted: boolean }>("/api/v1/reviews/mine", { method: "DELETE" });
      setMyReview(null); setMyReviewReplies([]); setMyReplyText("");
      setMyReviewMessage("Your review and its replies have been deleted.");
    } catch (cause) {
      setMyReviewError(cause instanceof Error ? cause.message : "Could not delete your review.");
    } finally { setMyReviewBusy(false); }
  }

  async function sendMyReviewReply(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!myReview) return;
    setMyReviewBusy(true); setMyReviewError(""); setMyReviewMessage("");
    try {
      const reply = await apiRequest<OwnReviewReply>("/api/v1/reviews/" + myReview.id + "/replies", {
        method: "POST",
        body: JSON.stringify({ display_name: myReplyName, comment: myReplyText }),
      });
      setMyReviewReplies(current => [...current, reply]);
      setMyReplyText("");
      setMyReviewMessage("Your reply has been posted.");
    } catch (cause) {
      setMyReviewError(cause instanceof Error ? cause.message : "Could not post your reply.");
    } finally { setMyReviewBusy(false); }
  }

  async function deleteAccount() {
    setDeleteError("");
    if (!confirmationMatches) {
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
    <section className="panel settings-panel your-reviews-panel" id="your-reviews">
      <div className="your-reviews-heading"><div><h2>Your reviews</h2><p className="settings-description">Manage your published review and read or join its public reply thread.</p></div><Link className="button button-secondary" href="/reviews/write">{myReview ? "Edit review" : "Write a review"}</Link></div>
      {myReviewLoading && <p>Loading your review…</p>}
      {!myReviewLoading && !myReview && <p className="settings-description">You have not published a review yet.</p>}
      {myReview && <>
        <article className="your-review-card">
          <div className="review-card-top"><strong>{myReview.display_name}</strong><time dateTime={myReview.created_at}>{new Date(myReview.created_at).toLocaleDateString()}</time></div>
          <div className="review-stars" aria-label={myReview.rating + " out of 5 stars"}>{"★".repeat(myReview.rating)}{"☆".repeat(5-myReview.rating)}</div>
          <p>{myReview.comment}</p>
          <div className="your-review-actions"><Link className="button button-secondary" href="/reviews/write">Edit review</Link><button className="button button-danger" type="button" disabled={myReviewBusy} onClick={() => void deleteMyReview()}>{myReviewBusy ? "Please wait…" : "Delete review"}</button></div>
        </article>
        <div className="review-replies">
          <h3>Replies ({myReviewReplies.length})</h3>
          {myReviewReplies.map(reply => <div className="review-reply" key={reply.id}><div className="review-reply-meta"><strong>{reply.display_name}</strong><time dateTime={reply.created_at}>{new Date(reply.created_at).toLocaleString()}</time></div><p>{reply.comment}</p></div>)}
          <form className="review-reply-form" onSubmit={sendMyReviewReply}>
            <label htmlFor="your-review-reply-name">Your name</label><input id="your-review-reply-name" minLength={2} maxLength={80} required value={myReplyName} onChange={event => setMyReplyName(event.target.value)} />
            <label htmlFor="your-review-reply-text">Reply to the thread</label><textarea id="your-review-reply-text" minLength={2} maxLength={2000} required rows={3} value={myReplyText} onChange={event => setMyReplyText(event.target.value)} placeholder="Write a reply…" />
            <button className="button button-secondary" disabled={myReviewBusy}>{myReviewBusy ? "Posting…" : "Post reply"}</button>
          </form>
        </div>
      </>}
      {myReviewError && <p className="auth-error" role="alert">{myReviewError}</p>}
      {myReviewMessage && <p className="auth-success" role="status">{myReviewMessage}</p>}
    </section>
    <section className="panel settings-panel"><h2>Account and privacy</h2><p className="settings-description">CompatFlow uses your account details to authenticate you and associate your access with an organization. You can review how information is processed in the <Link href="/privacy">Privacy Policy</Link>.</p><button className="button button-secondary" onClick={() => void signOut()}>Sign out</button></section>
    <section className="panel settings-panel danger-zone">
      <h2>Delete account</h2>
      {accountRole === "owner" ? <p className="settings-description">Deleting the owner account permanently removes the entire company workspace: all employee accounts, organization data, import history, reviews, subscription records and payment history. Any active Razorpay subscription is sent an immediate cancellation request first. This cannot be undone.</p> : <p className="settings-description">Deleting your account permanently removes your sign-in identity and organization membership. Shared company data and the organization subscription remain with the company owner.</p>}
      {roleLoading ? <p className="settings-description">Checking your organization role before enabling deletion…</p> : <><p className="settings-description">Your current role: <strong>{accountRole || "unverified"}</strong>. {accountRole === "owner" ? "Because this account owns the subscription and workspace, deletion removes the entire organization. Type DELETE ORGANIZATION." : "Type DELETE MY ACCOUNT to remove only your own account and membership."}</p><label htmlFor="delete-account-confirmation">Confirmation phrase: <strong>{requiredDeleteText}</strong></label><input id="delete-account-confirmation" className="delete-confirmation-input" value={deleteConfirmation} onChange={event => setDeleteConfirmation(event.target.value)} autoComplete="off" spellCheck={false} placeholder={requiredDeleteText} aria-describedby="delete-confirmation-help" /><p id="delete-confirmation-help" className="settings-description">The phrase is not case-sensitive. Leading and trailing spaces are ignored.</p></>}
      {roleError && <p className="auth-error" role="alert">We could not verify your organization role: {roleError}. Refresh this page or contact support; deletion remains disabled for safety.</p>}
      {deleteError && <p className="auth-error" role="alert">{deleteError}</p>}
      <button className="button button-danger" type="button" disabled={deleting || roleLoading || !accountRole || !confirmationMatches} onClick={() => void deleteAccount()}>{deleting ? "Deleting account…" : accountRole === "owner" ? "Permanently delete organization" : "Permanently delete my account"}</button>
    </section>
  </div></main>;
}
export default function SettingsPage() { return <AuthRequired><SettingsContent /></AuthRequired>; }
