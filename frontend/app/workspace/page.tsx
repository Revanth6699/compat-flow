"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthRequired } from "@/components/auth-required";
import { useAuth } from "@/components/auth-provider";
import { ApiRequestError, apiRequest } from "@/lib/auth-client";

type Profile = {
  id: string; organization_id: string; email: string; role: string; is_active: boolean;
  account_type: string; plan_code: string | null; subscription_status: string | null;
};

function WorkspaceContent() {
  const { user, signOut } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [organizationName, setOrganizationName] = useState(user?.user_metadata?.organization_name || "");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [needsOrganization, setNeedsOrganization] = useState(false);

  const loadProfile = useCallback(async () => {
    setError("");
    setNeedsOrganization(false);
    try {
      const data = await apiRequest<Profile>("/api/v1/auth/me");
      setProfile(data);
      const requestedPlan = new URLSearchParams(window.location.search).get("plan");
      if (requestedPlan && ["starter", "growth", "business"].includes(requestedPlan)) {
        router.replace(`/billing?plan=${requestedPlan}`);
      }
    } catch (cause) {
      if (cause instanceof ApiRequestError && cause.status === 404 &&
          cause.message === "No CompatFlow organization is linked to this account yet.") {
        setNeedsOrganization(true);
        setProfile(null);
      } else {
        setError(cause instanceof Error ? cause.message : "Could not load your organization workspace.");
      }
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => { void Promise.resolve().then(loadProfile); }, [loadProfile]);

  async function createOrganization(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (organizationName.trim().length < 2) {
      setError("Enter an organization name with at least 2 characters.");
      return;
    }
    setCreating(true);
    try {
      await apiRequest("/api/v1/auth/organization", {
        method: "POST",
        body: JSON.stringify({ name: organizationName.trim() }),
      });
      const requestedPlan = new URLSearchParams(window.location.search).get("plan");
      if (requestedPlan && ["starter", "growth", "business"].includes(requestedPlan)) {
        router.replace(`/billing?plan=${requestedPlan}`);
        return;
      }
      await loadProfile();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create your organization.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <main id="main" className="page">
      <div className="container">
        <header className="workspace-heading">
          <div><span className="eyebrow">YOUR ORGANIZATION</span><h1>Workspace</h1><p>Signed in as {user?.email || "your account"}.</p></div>
          <div className="workspace-actions">
            <Link className="button button-secondary" href="/pricing">Plans</Link>
            <Link className="button button-secondary" href="/settings">Profile settings</Link>
            <button className="button button-secondary" onClick={() => void signOut()}>Sign out</button>
          </div>
        </header>

        {loading && <p>Loading your organization workspace…</p>}
        {!loading && needsOrganization && (
          <section className="panel settings-panel">
            <span className="eyebrow">ONE-TIME SETUP</span>
            <h2>Create your company workspace</h2>
            <p>Your account is authenticated, but it is not linked to an organization yet. Create your organization now. You will become its owner; you do not need an operator to provision it.</p>
            <form className="auth-form" onSubmit={createOrganization}>
              <label htmlFor="workspace-organization-name">Organization name</label>
              <input id="workspace-organization-name" minLength={2} maxLength={160} required value={organizationName} onChange={event => setOrganizationName(event.target.value)} placeholder="Your company name" />
              {error && <p className="auth-error" role="alert">{error}</p>}
              <button className="button auth-submit" disabled={creating}>{creating ? "Creating workspace…" : "Create organization workspace"}</button>
            </form>
            <p className="settings-description">Email verification is required. If your account has not been verified, confirm the email first and return here.</p>
          </section>
        )}
        {!loading && error && !needsOrganization && <div className="notice"><strong>Workspace could not be loaded.</strong><p>{error}</p><button className="button button-secondary" onClick={() => { setLoading(true); void loadProfile(); }}>Try again</button></div>}

        {!loading && profile && (
          <>
            <section className="panel workspace-profile">
              <div className="workspace-heading">
                <div><span className="eyebrow">ORGANIZATION ACCOUNT</span><h2>Organization overview</h2><p>Your organization owns the subscription, data and employee access. Members use the same plan.</p></div>
                <span className="pricing-status available">{profile.role}</span>
              </div>
              <dl>
                <div><dt>Organization ID</dt><dd>{profile.organization_id}</dd></div>
                <div><dt>Your account</dt><dd>{profile.email}</dd></div>
                <div><dt>Subscription</dt><dd>{profile.plan_code ? profile.plan_code.charAt(0).toUpperCase() + profile.plan_code.slice(1) : "No paid plan selected"}</dd></div>
                <div><dt>Subscription status</dt><dd>{profile.subscription_status || "Not subscribed"}</dd></div>
                <div><dt>Workspace access</dt><dd>{profile.is_active ? "Active" : "Inactive"}</dd></div>
              </dl>
              {!profile.plan_code && <div className="notice"><strong>Your organization is set up.</strong><p>Choose a subscription to unlock paid organization features. Your workspace and owner account remain available while you decide.</p><Link className="button" href="/pricing">Choose a plan</Link></div>}
            </section>

            <section className="pricing-grid" aria-label="Workspace areas">
              <article className="panel settings-panel"><span className="eyebrow">CATALOG OPERATIONS</span><h2>Catalog validation</h2><p>Open the public product-catalog validation preview. Persistent organization imports are not enabled yet.</p><Link className="button button-secondary" href="/catalog/import">Open validation preview</Link></article>
              <article className="panel settings-panel"><span className="eyebrow">CONNECTED DATA</span><h2>Data sources</h2><p>Configure eligible REST API, SFTP and SQL Server source connections.</p><Link className="button button-secondary" href="/catalog/sources">Manage data sources</Link></article>
              {(profile.role === "owner" || profile.role === "admin") && <article className="panel settings-panel"><span className="eyebrow">PEOPLE</span><h2>Team access</h2><p>Invite employees, review members and manage permitted access for this organization.</p><Link className="button button-secondary" href="/team">Manage team</Link></article>}
              <article className="panel settings-panel"><span className="eyebrow">ORGANIZATION</span><h2>Billing</h2><p>Review subscription status and payment details for this organization.</p><Link className="button button-secondary" href="/billing">Manage subscription</Link></article>
            </section>
          </>
        )}
      </div>
    </main>
  );
}

export default function WorkspacePage() {
  return <AuthRequired><WorkspaceContent /></AuthRequired>;
}
