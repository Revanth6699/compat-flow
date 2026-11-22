"use client";

import Link from "next/link";
import { useAuth } from "@/components/auth-provider";

type Plan = {
  name: string;
  code?: string;
  price: string;
  description: string;
  features: string[];
  action: string;
  href: string;
  custom?: boolean;
};

const plans: Plan[] = [
  {
    name: "Demo",
    price: "Free",
    description: "Request access to evaluate the catalog validation workflow.",
    features: [
      "CSV uploads up to 5 MB",
      "Required-field and duplicate checks",
      "Catalog data-quality validations",
      "On-screen quality metrics",
      "Issue details and recommendations",
    ],
    action: "Request demo access",
    href: "/contact?intent=demo",
  },
  {
    name: "Starter",
    code: "starter",
    price: "$27",
    description: "For small teams that need repeatable validation and shareable results.",
    features: [
      "CSV, XLS and XLSX uploads up to 10 MB",
      "Required-field, duplicate and catalog data-quality checks",
      "Validation metrics, issue details and recommendations",
      "Downloadable validation reports",
      "Organization workspace",
      "Up to 3 total team seats",
    ],
    action: "Choose Starter",
    href: "/billing?plan=starter",
  },
  {
    name: "Growth",
    code: "growth",
    price: "$64",
    description: "For teams working with multiple supplier feeds and connected data sources.",
    features: [
      "All Starter validation capabilities",
      "JSON and XML inputs, in addition to all Starter formats",
      "Uploads up to 20 MB",
      "REST API, SFTP and SQL Server connections",
      "Multiple supplier catalog imports",
      "Up to 10 total team seats",
    ],
    action: "Choose Growth",
    href: "/billing?plan=growth",
  },
  {
    name: "Business",
    code: "business",
    price: "$153",
    description: "For operations teams coordinating catalog quality across departments.",
    features: [
      "All Growth validation and import capabilities",
      "Uploads up to 100 MB",
      "REST API, SFTP and SQL Server connections",
      "Multiple supplier catalog imports",
      "Up to 25 total team seats",
    ],
    action: "Choose Business",
    href: "/billing?plan=business",
  },
  {
    name: "Enterprise",
    price: "Custom",
    description: "For organizations with custom scale and integration requirements.",
    features: [
      "Custom file-size limits",
      "Custom team-seat allowance",
      "Plan configuration based on agreed requirements",
    ],
    action: "Discuss Enterprise",
    href: "/contact?intent=pricing&plan=enterprise",
    custom: true,
  },
];

export default function PricingPage() {
  const { user, loading } = useAuth();
  return (
    <main id="main" className="page pricing-page">
      <div className="container">
        <section className="pricing-intro">
          <div className="eyebrow">Plans built around your workflow</div>
          <h1>{user ? "Choose a plan for your organization." : "Start with a demo. Upgrade when your catalog operations need more."}</h1>
          <p>{user
            ? "Compare organization plans and select the subscription that matches your catalog operations. Paid checkout is subject to provider configuration and verified payment activation."
            : "Reference prices are in USD per month. Subscription access is activated after payment verification."}</p>
        </section>
        <section className="pricing-grid" aria-label="CompatFlow plans">
          {plans.filter(plan => !user || plan.name !== "Demo").map(plan => {
            const href = plan.code
              ? (user ? `/billing?plan=${plan.code}` : `/sign-up?plan=${plan.code}`)
              : plan.href;
            const action = plan.code && user ? "Select plan" : plan.action;
            return (
              <article className="pricing-card" key={plan.name}>
                <div className="pricing-card-top">
                  <div className="eyebrow">{plan.name === "Demo" ? "Approval required" : plan.name === "Starter" ? "For small teams" : plan.name === "Growth" ? "For growing teams" : plan.custom ? "Custom requirements" : "For operations teams"}</div>
                  <h2>{plan.name}</h2><p>{plan.description}</p>
                  <div className="pricing-amount"><strong>{plan.price}</strong>{plan.price !== "Free" && plan.price !== "Custom" && <span>/ month</span>}</div>
                </div>
                <div className="pricing-includes">Available features</div>
                <ul className="pricing-feature-list">
                  {plan.features.map(feature => (
                    <li key={`${plan.name}-${feature}`}>
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
                <div className="pricing-card-action">
                  <Link className="button button-secondary" href={href} aria-disabled={loading && !!plan.code}>
                    {loading && plan.code ? "Checking account…" : action}
                  </Link>
                </div>
              </article>
            );
          })}
        </section>
        {!user && <section className="pricing-footnote">
          <h2>Demo access</h2>
          <p>Demo access requires approval. Approved demo accounts can upload CSV files up to 5 MB and review results on screen.</p>
          <p>Paid subscriptions are activated after the payment provider confirms the transaction through a verified webhook.</p>
          <Link className="pricing-text-link" href="/catalog/import">Try the public demo</Link>
        </section>}
      </div>
    </main>
  );
}
