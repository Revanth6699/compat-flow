"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import Script from "next/script";
import { AuthRequired } from "@/components/auth-required";
import { apiRequest } from "@/lib/auth-client";

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayCheckoutOptions) => { open: () => void };
  }
}

type RazorpayCheckoutOptions = {
  key: string;
  subscription_id: string;
  name: string;
  description: string;
  handler: (response: {
    razorpay_payment_id: string;
    razorpay_subscription_id: string;
    razorpay_signature: string;
  }) => void;
  modal: { ondismiss: () => void };
  theme: { color: string };
};

type Subscription = {
  id: string;
  plan_code: string;
  provider: string | null;
  status: string;
  billing_interval: string;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
};

type SubscriptionResponse = { subscription: Subscription | null };
type CreateResponse = {
  local_subscription_id: string;
  razorpay_subscription_id: string;
  razorpay_key_id: string;
  plan_code: string;
  billing_interval: string;
  status: string;
  short_url?: string | null;
};

const plans = [
  { code: "starter", name: "Starter", price: "$27", description: "For small teams validating supplier product data." },
  { code: "growth", name: "Growth", price: "$64", description: "For recurring supplier catalog updates." },
  { code: "business", name: "Business", price: "$153", description: "For teams coordinating catalog quality." },
];

function BillingContent() {
  const search = useSearchParams();
  const requestedPlan = search.get("plan");
  const initialPlan = requestedPlan && plans.some(plan => plan.code === requestedPlan) ? requestedPlan : "starter";
  const [role, setRole] = useState<string | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [selectedPlan, setSelectedPlan] = useState(initialPlan);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [scriptReady, setScriptReady] = useState(false);

  const loadSubscription = useCallback(async () => {
    setError("");
    try {
      const [result, profile] = await Promise.all([
        apiRequest<SubscriptionResponse>("/api/v1/billing/subscription"),
        apiRequest<{ role: string }>("/api/v1/auth/me"),
      ]);
      setSubscription(result.subscription);
      setRole(profile.role);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load subscription details.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void Promise.resolve().then(() => loadSubscription()); }, [loadSubscription]);

  async function startCheckout() {
    setError("");
    setMessage("");
    if (!scriptReady || !window.Razorpay) {
      setError("The secure Razorpay Checkout library has not loaded. Refresh the page and try again.");
      return;
    }
    setBusy(true);
    try {
      const created = await apiRequest<CreateResponse>("/api/v1/billing/subscriptions", {
        method: "POST",
        body: JSON.stringify({ plan_code: selectedPlan, billing_interval: "month", total_count: 12 }),
      });
      const checkout = new window.Razorpay({
        key: created.razorpay_key_id,
        subscription_id: created.razorpay_subscription_id,
        name: "CompatFlow",
        description: `${created.plan_code.charAt(0).toUpperCase() + created.plan_code.slice(1)} monthly subscription`,
        theme: { color: "#00689C" },
        modal: { ondismiss: () => setBusy(false) },
        handler: async (response) => {
          try {
            const verified = await apiRequest<{ verified: boolean; message: string }>(
              "/api/v1/billing/subscriptions/verify-checkout",
              {
                method: "POST",
                body: JSON.stringify({
                  subscription_id: created.local_subscription_id,
                  razorpay_payment_id: response.razorpay_payment_id,
                  razorpay_subscription_id: response.razorpay_subscription_id,
                  razorpay_signature: response.razorpay_signature,
                }),
              },
            );
            setMessage(verified.message);
            await loadSubscription();
          } catch (err) {
            setError(err instanceof Error ? err.message : "Checkout verification failed.");
          } finally {
            setBusy(false);
          }
        },
      });
      checkout.open();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the subscription checkout.");
      setBusy(false);
    }
  }

  async function cancelSubscription() {
    if (!subscription || !window.confirm("Request cancellation at the end of the current billing cycle?")) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await apiRequest<{ message: string }>(
        `/api/v1/billing/subscriptions/${subscription.id}/cancel`,
        { method: "POST", body: JSON.stringify({ cancel_at_cycle_end: true }) },
      );
      setMessage(result.message);
      await loadSubscription();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not request cancellation.");
    } finally {
      setBusy(false);
    }
  }

  const isOwner = role === "owner";
  const subscriptionLocked = !!(subscription && ["active", "trialing", "pending", "past_due"].includes(subscription.status));

  return (
    <>
      <Script
        src="https://checkout.razorpay.com/v1/checkout.js"
        strategy="afterInteractive"
        onLoad={() => setScriptReady(true)}
        onError={() => setError("Razorpay Checkout could not be loaded. Check your network and content-security settings.")}
      />
      <main id="main" className="page">
        <div className="container account-settings">
          <header className="workspace-heading">
            <div><span className="eyebrow">ORGANIZATION</span><h1>Billing and subscription</h1><p>Review your organization subscription and billing status.</p></div>
            <Link className="button button-secondary" href="/workspace">Back to workspace</Link>
          </header>

          {error && <p className="auth-error" role="alert">{error}</p>}
          {message && <p className="auth-success" role="status">{message}</p>}

          <section className="panel settings-panel">
            <h2>Current subscription</h2>
            {loading ? <p>Loading subscription details…</p> : subscription ? (
              <>
                <dl className="workspace-profile">
                  <div><dt>Plan</dt><dd>{subscription.plan_code.charAt(0).toUpperCase() + subscription.plan_code.slice(1)}</dd></div>
                  <div><dt>Status</dt><dd>{subscription.status}</dd></div>
                  <div><dt>Billing interval</dt><dd>{subscription.billing_interval}</dd></div>
                  <div><dt>Provider</dt><dd>{subscription.provider || "Not set"}</dd></div>
                  <div><dt>Current period ends</dt><dd>{subscription.current_period_end ? new Date(subscription.current_period_end).toLocaleString() : "Not yet provided by provider"}</dd></div>
                  <div><dt>Cancellation at period end</dt><dd>{subscription.cancel_at_period_end ? "Requested" : "No"}</dd></div>
                </dl>
                {subscription.provider === "razorpay" && ["active", "pending", "past_due", "trialing"].includes(subscription.status) && !subscription.cancel_at_period_end && isOwner && (
                  <button className="button button-secondary" disabled={busy} onClick={() => void cancelSubscription()}>
                    {busy ? "Processing…" : "Request cancellation"}
                  </button>
                )}
              </>
            ) : <p>No subscription record is currently associated with this organization.</p>}
          </section>

          <section className="panel settings-panel">
            <h2>Choose a monthly plan</h2>
            <p className="settings-description">Checkout is available to the organization owner only. Prices below are the current reference prices in USD; payment availability and final currency depend on your Razorpay merchant account and configured plan IDs.</p>
            {!isOwner && <p className="notice">Only the organization owner can create or cancel a subscription. Contact your owner to manage billing.</p>}
            {subscriptionLocked && <p className="notice">Your organization already has a subscription in progress. Self-service upgrades and downgrades are not enabled yet; plan selection is locked until the current subscription is resolved.</p>}
            <div className="pricing-grid">
              {plans.map((plan) => (
                <button
                  type="button"
                  key={plan.code}
                  className={selectedPlan === plan.code ? "pricing-card billing-plan selected" : "pricing-card billing-plan"}
                  aria-pressed={selectedPlan === plan.code}
                  onClick={() => setSelectedPlan(plan.code)}
                  disabled={!isOwner || busy}
                >
                  <strong>{plan.name}</strong><span className="pricing-amount">{plan.price}<small> / month</small></span><span>{plan.description}</span>
                </button>
              ))}
            </div>
            <p className="settings-description">Enterprise remains a custom commercial plan and is not available through self-service checkout. Annual billing is not enabled until annual prices and provider plans are explicitly configured.</p>
            <button className="button auth-submit" disabled={!isOwner || busy || loading || subscriptionLocked} onClick={() => void startCheckout()}>
              {busy ? "Please wait…" : "Continue to secure checkout"}
            </button>
            <p className="settings-description">A successful checkout signature does not activate access by itself. CompatFlow waits for a verified Razorpay subscription webhook before treating the subscription as active.</p>
          </section>
        </div>
      </main>
    </>
  );
}

export default function BillingPage() {
  return <Suspense fallback={<main id="main" className="page">Loading billing…</main>}><AuthRequired><BillingContent /></AuthRequired></Suspense>;
}
