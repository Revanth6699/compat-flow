"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AuthRequired } from "@/components/auth-required";
import { apiRequest } from "@/lib/auth-client";

type SeatUsage = {
  member_seat_limit: number | null;
  active_members: number;
  pending_invitations: number;
  occupied_seats: number;
  available_seats: number | null;
  over_limit: boolean;
};
type Member = { id: string; email: string; role: string; is_active: boolean; created_at: string };
type Invitation = {
  id: string;
  email: string;
  role: string;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
};
type CreatedInvitation = { invitation_token: string; email: string; role: string; expires_at: string };

function TeamContent() {
  const [role, setRole] = useState("");
  const [seats, setSeats] = useState<SeatUsage | null>(null);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [currentUserId, setCurrentUserId] = useState("");
  const [email, setEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [createdLink, setCreatedLink] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const loadTeam = useCallback(async () => {
    setError("");
    try {
      const [seatData, invitationData, memberData, profile] = await Promise.all([
        apiRequest<SeatUsage>("/api/v1/invitations/seats"),
        apiRequest<Invitation[]>("/api/v1/invitations"),
        apiRequest<Member[]>("/api/v1/invitations/members"),
        apiRequest<{ id: string; role: string }>("/api/v1/auth/me"),
      ]);
      setSeats(seatData);
      setInvitations(invitationData);
      setMembers(memberData);
      setRole(profile.role);
      setCurrentUserId(profile.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load organization team access.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void Promise.resolve().then(loadTeam); }, [loadTeam]);

  async function updateMember(memberId: string, changes: { role?: string; is_active?: boolean }) {
    setError(""); setMessage(""); setBusy(true);
    try {
      const updated = await apiRequest<Member>(`/api/v1/invitations/members/${memberId}`, {
        method: "PATCH",
        body: JSON.stringify(changes),
      });
      setMembers(current => current.map(member => member.id === updated.id ? updated : member));
      setMessage(`Updated access for ${updated.email}.`);
      await loadTeam();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update employee access.");
    } finally {
      setBusy(false);
    }
  }

  async function createInvitation(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(""); setMessage(""); setCreatedLink("");
    setBusy(true);
    try {
      const result = await apiRequest<CreatedInvitation>("/api/v1/invitations", {
        method: "POST",
        body: JSON.stringify({ email: email.trim().toLowerCase(), role: inviteRole, expires_in_hours: 72 }),
      });
      setCreatedLink(`${window.location.origin}/invitations/accept?token=${encodeURIComponent(result.invitation_token)}`);
      setMessage(`Invitation created for ${result.email}. Copy and send the link; CompatFlow does not send invitation emails yet.`);
      setEmail("");
      await loadTeam();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create the invitation.");
    } finally {
      setBusy(false);
    }
  }

  async function revokeInvitation(id: string) {
    if (!window.confirm("Revoke this pending invitation?")) return;
    setError(""); setMessage(""); setBusy(true);
    try {
      await apiRequest<void>(`/api/v1/invitations/${id}`, { method: "DELETE" });
      setMessage("Invitation revoked.");
      await loadTeam();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not revoke the invitation.");
    } finally {
      setBusy(false);
    }
  }

  async function copyInviteLink() {
    try {
      await navigator.clipboard.writeText(createdLink);
      setMessage("Invitation link copied.");
    } catch {
      setError("Clipboard access was blocked. Select and copy the invitation link manually.");
    }
  }

  const canManage = role === "owner" || role === "admin";
  const canInviteAdmin = role === "owner";
  const canInviteWithCurrentPlan = seats?.available_seats === null || (seats?.available_seats !== undefined && seats.available_seats > 0);

  return (
    <main id="main" className="page">
      <div className="container account-settings">
        <header className="workspace-heading">
          <div><span className="eyebrow">ORGANIZATION</span><h1>Team access</h1><p>Manage who can enter this organization CompatFlow workspace.</p></div>
          <Link className="button button-secondary" href="/workspace">Back to workspace</Link>
        </header>
        {error && <p className="auth-error" role="alert">{error}</p>}
        {message && <p className="auth-success" role="status">{message}</p>}
        {loading ? <p>Loading team access…</p> : (
          <>
            {seats && <section className="panel settings-panel">
              <h2>Seat usage</h2>
              <dl className="workspace-profile">
                <div><dt>Active members</dt><dd>{seats.active_members}</dd></div>
                <div><dt>Pending invitations</dt><dd>{seats.pending_invitations}</dd></div>
                <div><dt>Occupied seats</dt><dd>{seats.occupied_seats}</dd></div>
                <div><dt>Seat limit</dt><dd>{seats.member_seat_limit ?? "Not configured"}</dd></div>
                <div><dt>Available seats</dt><dd>{seats.available_seats ?? "Not configured"}</dd></div>
              </dl>
              {seats.over_limit && <p className="notice">Your current plan has fewer seats than your existing team. Existing members remain active; new invitations may be blocked until the limit is resolved.</p>}
            </section>}
            <section className="panel settings-panel">
              <h2>Organization members</h2>
              {members.length === 0 ? <p>No members are linked to this organization yet.</p> : <div className="table-wrap"><table><thead><tr><th>Employee</th><th>Role</th><th>Access</th><th>Joined</th><th>Action</th></tr></thead><tbody>
                {members.map(member => {
                  const canEdit = canManage && member.role !== "owner" && member.id !== currentUserId && !(role === "admin" && member.role === "admin");
                  return <tr key={member.id}>
                    <td>{member.email}{member.id === currentUserId ? " (you)" : ""}</td>
                    <td><select aria-label={`Role for ${member.email}`} value={member.role} disabled={!canEdit || busy} onChange={event => void updateMember(member.id, { role: event.target.value })}>
                      {member.role === "owner" && <option value="owner">Owner</option>}
                      {(canInviteAdmin || member.role === "admin") && <option value="admin">Admin</option>}
                      <option value="member">Member</option><option value="viewer">Viewer</option>
                    </select></td>
                    <td>{member.is_active ? "Active" : "Inactive"}</td>
                    <td>{new Date(member.created_at).toLocaleDateString()}</td>
                    <td>{canEdit ? <button className="button button-secondary" disabled={busy} onClick={() => void updateMember(member.id, { is_active: !member.is_active })}>{member.is_active ? "Deactivate" : "Reactivate"}</button> : "—"}</td>
                  </tr>;
                })}
              </tbody></table></div>}
              <p className="settings-description">The owner account cannot be changed or deactivated. Administrators can manage members and viewers; only the owner can grant administrator access.</p>
            </section>
            {canManage && <section className="panel settings-panel">
              <h2>Invite an employee</h2>
              <p className="settings-description">Invitations reserve a seat for 72 hours. Seat limits include the organization owner: Starter 3, Growth 10, Business 25; Enterprise limits are configured by contract.</p>
              {!canInviteWithCurrentPlan && <p className="notice">Your organization has no available seats. Choose or upgrade a subscription before inviting employees.</p>}
              <form className="auth-form" onSubmit={createInvitation}>
                <label htmlFor="team-email">Work email</label>
                <input id="team-email" type="email" required value={email} onChange={event => setEmail(event.target.value)} placeholder="employee@company.com" />
                <label htmlFor="team-role">Access role</label>
                <select id="team-role" value={inviteRole} onChange={event => setInviteRole(event.target.value)}>
                  <option value="member">Member — catalog read and write</option>
                  <option value="viewer">Viewer — read only</option>
                  {canInviteAdmin && <option value="admin">Admin — manage members and catalog</option>}
                </select>
                <button className="button auth-submit" disabled={busy || !canInviteWithCurrentPlan}>{busy ? "Creating invitation…" : "Create invitation link"}</button>
              </form>
              {createdLink && <div className="notice"><strong>Invitation link</strong><p>Share this link only with the invited employee.</p><textarea readOnly rows={3} value={createdLink} aria-label="Invitation link" /><button className="button button-secondary" type="button" onClick={() => void copyInviteLink()}>Copy invitation link</button></div>}
            </section>}
            <section className="panel settings-panel">
              <h2>Invitations</h2>
              {invitations.length === 0 ? <p>No invitations have been created for this organization yet.</p> : <div className="table-wrap"><table><thead><tr><th>Email</th><th>Role</th><th>Status</th><th>Expires</th><th>Action</th></tr></thead><tbody>
                {invitations.map(item => {
                  const status = item.accepted_at ? "Accepted" : item.revoked_at ? "Revoked" : "Awaiting response";
                  return <tr key={item.id}><td>{item.email}</td><td>{item.role}</td><td>{status}</td><td>{new Date(item.expires_at).toLocaleString()}</td><td>{canManage && status === "Awaiting response" ? <button className="button button-secondary" disabled={busy} onClick={() => void revokeInvitation(item.id)}>Revoke</button> : "—"}</td></tr>;
                })}
              </tbody></table></div>}
              <p className="settings-description">Accepted employees are linked to this organization. Role changes and member deactivation are recorded against this organization. Invitation delivery is still manual.</p>
            </section>
          </>
        )}
      </div>
    </main>
  );
}

export default function TeamPage() {
  return <AuthRequired><TeamContent /></AuthRequired>;
}
