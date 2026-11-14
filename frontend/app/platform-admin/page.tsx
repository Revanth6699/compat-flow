"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/components/auth-provider";
import { apiRequest, updatePassword } from "@/lib/auth-client";

type Overview = {
  users: number; active_users: number; organizations: number; subscriptions: number; active_subscriptions: number; reviews: number;
  demo_requests: number; pending_demo_requests: number; approved_demo_requests: number;
  complaints: number | null; complaints_note: string; subscription_usage: number | null; subscription_usage_note: string;
};
type DemoRequest = {
  id: string; name: string; email: string; organization: string; role: string;
  message: string; status: string; created_at: string;
};

export default function PlatformAdminPage() {
  const { user, loading } = useAuth();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [requests, setRequests] = useState<DemoRequest[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordMessage, setPasswordMessage] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);

  const load = useCallback(async () => {
    const [summary, items] = await Promise.all([
      apiRequest<Overview>("/api/v1/platform-admin/overview"),
      apiRequest<DemoRequest[]>("/api/v1/platform-admin/demo-requests"),
    ]);
    setOverview(summary);
    setRequests(items);
  }, []);

  useEffect(() => {
    if (!user) return;
    let active = true;
    Promise.all([
      apiRequest<Overview>("/api/v1/platform-admin/overview"),
      apiRequest<DemoRequest[]>("/api/v1/platform-admin/demo-requests"),
    ]).then(([summary, items]) => {
      if (active) { setOverview(summary); setRequests(items); }
    }).catch((err) => {
      if (active) setError(err instanceof Error ? err.message : "Platform administrator access denied.");
    });
    return () => { active = false; };
  }, [user]);

  async function changeOwnerPassword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPasswordMessage("");
    setPasswordError("");
    if (newPassword.length < 10) {
      setPasswordError("Use a password with at least 10 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("The passwords do not match.");
      return;
    }
    setPasswordBusy(true);
    try {
      await updatePassword(newPassword);
      setNewPassword("");
      setConfirmPassword("");
      setPasswordMessage("Your owner-account password has been updated.");
    } catch (cause) {
      setPasswordError(cause instanceof Error ? cause.message : "Could not update your password.");
    } finally {
      setPasswordBusy(false);
    }
  }

  async function decide(id: string, decision: "approve" | "revoke" | "reject") {
    setBusy(id); setError("");
    try {
      await apiRequest<DemoRequest>("/api/v1/platform-admin/demo-requests/" + id + "/" + decision, { method: "PATCH" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update the demo request.");
    } finally { setBusy(""); }
  }

  if (loading) return <main className="page"><div className="container">Checking account...</div></main>;
  if (!user) return <main className="page"><div className="container panel"><h1>Platform administration</h1><p>Sign in with the configured platform-owner account.</p><Link className="button" href="/sign-in?next=%2Fplatform-admin">Sign in</Link></div></main>;
  if ((user.email || "").trim().toLowerCase() !== "sarvasettyrevanth.66@gmail.com") {
    return <main className="page"><div className="container panel"><h1>Access denied</h1><p>This account is not authorized to access platform administration.</p><Link className="button button-secondary" href="/">Return to website</Link></div></main>;
  }

  return <main className="page"><div className="container">
    <div className="import-heading"><div className="eyebrow">RESTRICTED CONSOLE</div><h1>Platform overview</h1><p>Platform-level metrics and demo access decisions. Authorization is enforced by the API.</p></div>
    <section className="panel result-section" aria-label="Platform owner profile">
      <div className="eyebrow">OWNER ACCOUNT</div>
      <div className="row" style={{ alignItems: "center", gap: "1rem" }}>
        <div aria-hidden="true" style={{ width: 52, height: 52, borderRadius: "50%", display: "grid", placeItems: "center", fontWeight: 700, background: "var(--surface, #eeeeec)" }}>RK</div>
        <div>
          <h2 style={{ margin: 0 }}>Sarvasetty Revanth Kumar</h2>
          <p style={{ margin: "0.25rem 0" }}>Platform Owner</p>
          <p style={{ margin: 0 }}>sarvasettyrevanth.66@gmail.com</p>
        </div>
      </div>
      <p><strong>Access level:</strong> Full platform administration</p>
    </section>
    <section className="panel result-section" aria-label="Owner password settings">
      <h2>Change owner password</h2>
      <p>Set or change the password for your CompatFlow owner account. Your password is handled by the authentication provider and is never displayed here.</p>
      <form className="auth-form" onSubmit={changeOwnerPassword}>
        <label htmlFor="owner-new-password">New password</label>
        <input id="owner-new-password" type="password" autoComplete="new-password" minLength={10} required value={newPassword} onChange={event => setNewPassword(event.target.value)} />
        <label htmlFor="owner-confirm-password">Confirm new password</label>
        <input id="owner-confirm-password" type="password" autoComplete="new-password" minLength={10} required value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} />
        {passwordError && <p className="auth-error" role="alert">{passwordError}</p>}
        {passwordMessage && <p className="auth-success" role="status">{passwordMessage}</p>}
        <button className="button" disabled={passwordBusy}>{passwordBusy ? "Updating…" : "Update password"}</button>
      </form>
      <p><Link href="/forgot-password">Forgot your password? Reset it by email.</Link></p>
    </section>
    {error && <p className="form-error" role="alert">{error}</p>}
    {overview && <div className="result-stats">
      {([["Users", overview.users], ["Active users", overview.active_users], ["Organizations", overview.organizations], ["Subscriptions", overview.subscriptions], ["Active subscriptions", overview.active_subscriptions], ["Reviews", overview.reviews], ["Demo requests", overview.demo_requests], ["Pending requests", overview.pending_demo_requests], ["Approved demos", overview.approved_demo_requests]] as [string, number][]).map(([label, value]) => <div className="panel stat-card" key={label}><span>{label}</span><strong>{value.toLocaleString()}</strong></div>)}
    </div>}
    <section className="panel result-section"><h2>Demo access requests</h2>
      {requests.length === 0 ? <p>No demo requests have been submitted.</p> : <div className="table-scroll"><table className="preview-table"><thead><tr><th>Requester</th><th>Organization</th><th>Message</th><th>Status</th><th>Actions</th></tr></thead><tbody>
        {requests.map((request) => <tr key={request.id}><td><strong>{request.name}</strong><br />{request.email}<br />{request.role}</td><td>{request.organization}</td><td>{request.message}</td><td>{request.status}</td><td>
          {request.status !== "approved" && <button className="button button-secondary" disabled={!!busy} onClick={() => void decide(request.id, "approve")}>{busy === request.id ? "Saving..." : "Approve"}</button>}
          {request.status === "approved" && <button className="button button-secondary" disabled={!!busy} onClick={() => void decide(request.id, "revoke")}>{busy === request.id ? "Saving..." : "Revoke"}</button>}
          {request.status === "pending" && <button className="button button-secondary" disabled={!!busy} onClick={() => void decide(request.id, "reject")}>Reject</button>}
        </td></tr>)}
      </tbody></table></div>}
    </section>
    <section className="panel result-section"><h2>Complaints and support</h2><p>{overview?.complaints_note || "Complaint tracking is not implemented yet."}</p></section>\n    <section className="panel result-section"><h2>Subscription usage</h2><p>{overview?.subscription_usage_note || "Usage metering is not implemented yet."}</p></section>
  </div></main>;
}
