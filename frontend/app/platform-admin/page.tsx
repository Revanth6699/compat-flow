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
type AdminReview = { id: string; display_name: string; rating: number; comment: string; created_at: string; organization_id: string; user_id: string; is_published: boolean; };
type DemoRequest = {
  id: string; name: string; email: string; organization: string; role: string;
  message: string; status: string; created_at: string;
};

const metricCards = (data: Overview) => [
  { label: "Total users", value: data.users, note: `${data.active_users.toLocaleString()} active`, accent: "blue" },
  { label: "Organizations", value: data.organizations, note: "Registered workspaces", accent: "teal" },
  { label: "Subscriptions", value: data.subscriptions, note: `${data.active_subscriptions.toLocaleString()} active plans`, accent: "purple" },
  { label: "Demo requests", value: data.demo_requests, note: `${data.pending_demo_requests.toLocaleString()} awaiting review`, accent: "amber" },
  { label: "Approved demos", value: data.approved_demo_requests, note: "Access granted", accent: "green" },
  { label: "Customer reviews", value: data.reviews, note: "Published feedback", accent: "slate" },
];

export default function PlatformAdminPage() {
  const { user, loading } = useAuth();
  const [authorization, setAuthorization] = useState<{ userId: string; checked: boolean; isPlatformAdmin: boolean }>({ userId: "", checked: false, isPlatformAdmin: false });
  const authorizationChecked = !user || (authorization.userId === user.id && authorization.checked);
  const isPlatformAdmin = !!user && authorization.userId === user.id && authorization.isPlatformAdmin;
  const [overview, setOverview] = useState<Overview | null>(null);
  const [requests, setRequests] = useState<DemoRequest[]>([]);
  const [reviews, setReviews] = useState<AdminReview[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordMessage, setPasswordMessage] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);

  const load = useCallback(async () => {
    const [summary, items, reviewItems] = await Promise.all([
      apiRequest<Overview>("/api/v1/platform-admin/overview"),
      apiRequest<DemoRequest[]>("/api/v1/platform-admin/demo-requests"),
      apiRequest<AdminReview[]>("/api/v1/reviews/platform-admin/reviews"),
    ]);
    setOverview(summary);
    setRequests(items);
    setReviews(reviewItems);
  }, []);

  useEffect(() => {
    if (!user) return;
    let active = true;
    apiRequest<{ is_platform_admin?: boolean }>("/api/v1/auth/me")
      .then((profile) => {
        if (!active) return;
        const allowed = profile.is_platform_admin === true;
        setAuthorization({ userId: user.id, checked: true, isPlatformAdmin: allowed });
        if (!allowed) return;
        Promise.all([
          apiRequest<Overview>("/api/v1/platform-admin/overview"),
          apiRequest<DemoRequest[]>("/api/v1/platform-admin/demo-requests"),
          apiRequest<AdminReview[]>("/api/v1/reviews/platform-admin/reviews"),
        ]).then(([summary, items, reviewItems]) => {
          if (active) { setOverview(summary); setRequests(items); setReviews(reviewItems); }
        }).catch((err) => {
          if (active) setError(err instanceof Error ? err.message : "Platform administrator access denied.");
        });
      })
      .catch((err) => {
        if (active) {
          setAuthorization({ userId: user.id, checked: true, isPlatformAdmin: false });
          setError(err instanceof Error ? err.message : "Could not verify platform-owner access.");
        }
      });
    return () => { active = false; };
  }, [user]);

  async function changeOwnerPassword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPasswordMessage("");
    setPasswordError("");
    if (newPassword.length < 10) { setPasswordError("Use a password with at least 10 characters."); return; }
    if (newPassword !== confirmPassword) { setPasswordError("The passwords do not match."); return; }
    setPasswordBusy(true);
    try {
      await updatePassword(newPassword);
      setNewPassword("");
      setConfirmPassword("");
      setPasswordMessage("Your owner-account password has been updated.");
    } catch (cause) {
      setPasswordError(cause instanceof Error ? cause.message : "Could not update your password.");
    } finally { setPasswordBusy(false); }
  }

  async function moderateReview(id: string, decision: "publish" | "hide" | "delete") {
    setBusy(id); setError("");
    try {
      await apiRequest(`/api/v1/reviews/platform-admin/reviews/${id}/${decision}`, { method: "PATCH" });
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not update the review."); }
    finally { setBusy(""); }
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
  if (!authorizationChecked) return <main className="page"><div className="container">Verifying platform-owner access...</div></main>;
  if (!isPlatformAdmin) {
    return <main className="page"><div className="container panel"><h1>Access denied</h1><p>This account is not authorized to access platform administration.</p><Link className="button button-secondary" href="/">Return to website</Link></div></main>;
  }

  return (
    <main className="page platform-admin-page">
      <div className="container platform-admin-container">
        <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 20, flexWrap: "wrap", marginBottom: 28 }}>
          <div>
            <div className="eyebrow">COMPATFLOW / ADMINISTRATION</div>
            <h1 style={{ margin: "8px 0 5px", color: "#172B4D", fontSize: "clamp(30px,4vw,40px)", letterSpacing: "-.04em" }}>Platform dashboard</h1>
            <p style={{ margin: 0, color: "#64748B" }}>Monitor platform activity and manage access from one place.</p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 16px", border: "1px solid #E2E8F0", borderRadius: 10, background: "#fff" }}>
            <div style={{ width: 38, height: 38, borderRadius: 10, display: "grid", placeItems: "center", background: "#EAF2FB", color: "#24527D", fontWeight: 800 }}>RK</div>
            <div><strong style={{ display: "block", color: "#1E293B", fontSize: 13 }}>Sarvasetty Revanth Kumar</strong><span style={{ color: "#64748B", fontSize: 12 }}>Platform owner</span></div>
            <span style={{ marginLeft: 8, padding: "4px 8px", borderRadius: 20, background: "#ECFDF3", color: "#15803D", fontSize: 10, fontWeight: 800 }}>OWNER</span>
          </div>
        </header>

        {error && <div className="form-error" role="alert" style={{ marginBottom: 18 }}>{error}</div>}

        <section aria-label="Platform metrics" style={{ marginBottom: 28 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 13 }}>
            <h2 style={{ margin: 0, color: "#1E293B", fontSize: 18 }}>Platform at a glance</h2>
            <span style={{ color: "#64748B", fontSize: 12 }}>{overview ? "Live platform data" : "Loading platform data…"}</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(175px,1fr))", gap: 14 }}>
            {metricCards(overview || { users: 0, active_users: 0, organizations: 0, subscriptions: 0, active_subscriptions: 0, reviews: 0, demo_requests: 0, pending_demo_requests: 0, approved_demo_requests: 0, complaints: null, complaints_note: "", subscription_usage: null, subscription_usage_note: "" }).map((metric) => (
              <article key={metric.label} style={{ padding: "19px 20px", border: "1px solid #E5EAF0", borderRadius: 11, background: "#fff", boxShadow: "0 2px 8px rgba(15,23,42,.025)" }}>
                <div style={{ color: "#64748B", fontSize: 12, fontWeight: 650 }}>{metric.label}</div>
                <div style={{ margin: "9px 0 4px", color: "#172B4D", fontSize: 30, lineHeight: 1.1, fontWeight: 750 }}>{overview ? metric.value.toLocaleString() : "—"}</div>
                <div style={{ color: "#94A3B8", fontSize: 11 }}>{metric.note}</div>
              </article>
            ))}
          </div>
        </section>

        <div className="platform-admin-layout">
          <section className="panel" aria-label="Demo access requests" style={{ padding: 24, borderRadius: 11, borderColor: "#E2E8F0", boxShadow: "0 2px 8px rgba(15,23,42,.025)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 18 }}>
              <div><h2 style={{ margin: 0, color: "#1E293B", fontSize: 18 }}>Demo access requests</h2><p style={{ margin: "4px 0 0", color: "#64748B", fontSize: 12 }}>Review requests and control demo access.</p></div>
              <span style={{ padding: "5px 9px", borderRadius: 20, background: "#FFF7ED", color: "#C2410C", fontSize: 11, fontWeight: 750 }}>{overview?.pending_demo_requests ?? "—"} pending</span>
            </div>
            {requests.length === 0 ? (
              <div style={{ padding: "38px 16px", border: "1px dashed #CBD5E1", borderRadius: 9, textAlign: "center", background: "#FAFCFE" }}>
                <div style={{ marginBottom: 8, color: "#64748B", fontSize: 13, fontWeight: 700 }}>No demo requests yet</div>
                <p style={{ margin: 0, color: "#94A3B8", fontSize: 12 }}>New customer requests will appear here when submitted.</p>
              </div>
            ) : (
              <div className="table-scroll"><table className="preview-table"><thead><tr><th>Requester</th><th>Organization</th><th>Request</th><th>Status</th><th>Actions</th></tr></thead><tbody>
                {requests.map((request) => (
                  <tr key={request.id}>
                    <td><strong>{request.name}</strong><br /><span style={{ fontSize: 12 }}>{request.email}</span><br /><span style={{ fontSize: 11, color: "#64748B" }}>{request.role}</span></td>
                    <td>{request.organization}</td><td>{request.message || "—"}</td>
                    <td><span style={{ display: "inline-block", padding: "4px 8px", borderRadius: 20, background: request.status === "approved" ? "#ECFDF3" : request.status === "pending" ? "#FFF7ED" : "#F1F5F9", color: request.status === "approved" ? "#15803D" : request.status === "pending" ? "#C2410C" : "#475569", fontSize: 11, fontWeight: 750 }}>{request.status}</span></td>
                    <td style={{ minWidth: 150 }}>
                      {request.status !== "approved" && <button className="button button-secondary" style={{ minHeight: 34, padding: "0 10px", margin: "2px", fontSize: 11 }} disabled={!!busy} onClick={() => void decide(request.id, "approve")}>{busy === request.id ? "Saving…" : "Approve"}</button>}
                      {request.status === "approved" && <button className="button button-secondary" style={{ minHeight: 34, padding: "0 10px", margin: "2px", fontSize: 11 }} disabled={!!busy} onClick={() => void decide(request.id, "revoke")}>{busy === request.id ? "Saving…" : "Revoke"}</button>}
                      {request.status === "pending" && <button className="button button-secondary" style={{ minHeight: 34, padding: "0 10px", margin: "2px", fontSize: 11 }} disabled={!!busy} onClick={() => void decide(request.id, "reject")}>Reject</button>}
                    </td>
                  </tr>
                ))}
              </tbody></table></div>
            )}
          </section>

          <div style={{ display: "grid", gap: 18 }}>
            <section className="panel" aria-label="Owner account security" style={{ padding: 22, borderRadius: 11, borderColor: "#E2E8F0", boxShadow: "0 2px 8px rgba(15,23,42,.025)" }}>
              <div className="eyebrow">ACCOUNT SECURITY</div>
              <h2 style={{ margin: "7px 0 5px", color: "#1E293B", fontSize: 18 }}>Owner account</h2>
              <p style={{ margin: "0 0 17px", color: "#64748B", fontSize: 12, overflowWrap: "anywhere" }}>sarvasettyrevanth.66@gmail.com</p>
              <form className="auth-form" onSubmit={changeOwnerPassword}>
                <label htmlFor="owner-new-password">New password</label>
                <input id="owner-new-password" type="password" autoComplete="new-password" minLength={10} required value={newPassword} onChange={event => setNewPassword(event.target.value)} />
                <label htmlFor="owner-confirm-password">Confirm new password</label>
                <input id="owner-confirm-password" type="password" autoComplete="new-password" minLength={10} required value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} />
                {passwordError && <p className="auth-error" role="alert">{passwordError}</p>}
                {passwordMessage && <p className="auth-success" role="status">{passwordMessage}</p>}
                <button className="button" style={{ width: "100%" }} disabled={passwordBusy}>{passwordBusy ? "Updating…" : "Update password"}</button>
              </form>
              <p style={{ margin: "13px 0 0", fontSize: 12 }}><Link href="/forgot-password">Reset password by email</Link></p>
            </section>

            <section className="panel" aria-label="Platform operations" style={{ padding: 22, borderRadius: 11, borderColor: "#E2E8F0", boxShadow: "0 2px 8px rgba(15,23,42,.025)" }}>
              <div className="eyebrow">PLATFORM OPERATIONS</div>
              <h2 style={{ margin: "7px 0 14px", color: "#1E293B", fontSize: 18 }}>Service modules</h2>
              <div style={{ display: "grid", gap: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, paddingBottom: 12, borderBottom: "1px solid #EEF2F6" }}>
                  <div><strong style={{ display: "block", color: "#334155", fontSize: 12 }}>Complaints & support</strong><span style={{ color: "#94A3B8", fontSize: 11 }}>{overview?.complaints_note || "Tracking is not implemented yet."}</span></div>
                  <span style={{ alignSelf: "center", color: "#94A3B8", fontSize: 10, fontWeight: 750 }}>PLANNED</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                  <div><strong style={{ display: "block", color: "#334155", fontSize: 12 }}>Subscription usage</strong><span style={{ color: "#94A3B8", fontSize: 11 }}>{overview?.subscription_usage_note || "Usage metering is not implemented yet."}</span></div>
                  <span style={{ alignSelf: "center", color: "#94A3B8", fontSize: 10, fontWeight: 750 }}>PLANNED</span>
                </div>
              </div>
            </section>
          </div>
        </div>
        <section className="panel" aria-label="Customer reviews" style={{ marginTop: 18, padding: 24, borderRadius: 11, borderColor: "#E2E8F0", boxShadow: "0 2px 8px rgba(15,23,42,.025)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 18 }}>
            <div><h2 style={{ margin: 0, color: "#1E293B", fontSize: 18 }}>Customer reviews</h2><p style={{ margin: "4px 0 0", color: "#64748B", fontSize: 12 }}>Review submitted feedback, then publish, hide, or delete it.</p></div>
            <span style={{ padding: "5px 9px", borderRadius: 20, background: "#EFF6FF", color: "#1D4ED8", fontSize: 11, fontWeight: 750 }}>{reviews.length} reviews</span>
          </div>
          {reviews.length === 0 ? <div style={{ padding: "30px 16px", border: "1px dashed #CBD5E1", borderRadius: 9, textAlign: "center", color: "#64748B", fontSize: 13 }}>No customer reviews found.</div> :
            <div className="table-scroll"><table className="preview-table"><thead><tr><th>Reviewer</th><th>Rating</th><th>Review</th><th>Submitted</th><th>Visibility</th><th>Actions</th></tr></thead><tbody>
              {reviews.map((review) => <tr key={review.id}>
                <td>{review.display_name}<br /><span style={{ color: "#94A3B8", fontSize: 11 }}>{review.user_id.slice(0, 8)}…</span></td>
                <td>{review.rating}/5</td><td style={{ minWidth: 240, whiteSpace: "pre-wrap" }}>{review.comment}</td>
                <td>{new Date(review.created_at).toLocaleDateString()}</td>
                <td>{review.is_published ? "Published" : "Hidden"}</td>
                <td style={{ minWidth: 170 }}>
                  <button className="button button-secondary" style={{ minHeight: 34, padding: "0 10px", margin: 2, fontSize: 11 }} disabled={!!busy} onClick={() => void moderateReview(review.id, review.is_published ? "hide" : "publish")}>{review.is_published ? "Hide" : "Publish"}</button>
                  <button className="button button-secondary" style={{ minHeight: 34, padding: "0 10px", margin: 2, fontSize: 11 }} disabled={!!busy} onClick={() => { if (window.confirm("Permanently delete this review?")) void moderateReview(review.id, "delete"); }}>Delete</button>
                </td>
              </tr>)}
            </tbody></table></div>}
        </section>
        <p style={{ margin: "18px 0 0", color: "#94A3B8", fontSize: 11 }}>Administrative actions are validated by the platform API. Account credentials are managed securely by the authentication provider.</p>
      </div>
    </main>
  );
}
