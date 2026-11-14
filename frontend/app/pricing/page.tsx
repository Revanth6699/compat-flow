"use client";

import Link from "next/link";
import { useAuth } from "@/components/auth-provider";

type FeatureStatus = "Included" | "Planned" | "Not included";
type Plan = {
  name: string; code?: string; price: string; description: string; featured?: boolean;
  features: [string, FeatureStatus][]; action: string; href: string; custom?: boolean;
};

const plans: Plan[] = [
  {
    name: "Demo", price: "Free", description: "Evaluate the core validation workflow without creating an account.",
    features: [
      ["CSV, XLS and XLSX uploads", "Included"],
      ["Required-field and duplicate checks", "Included"],
      ["On-screen quality metrics", "Included"],
      ["Issue details and recommendations", "Included"],
      ["Downloadable validation report", "Not included"],
      ["JSON and XML inputs", "Not included"],
      ["API, SFTP and database connections", "Not included"],
      ["Organization workspace", "Not included"],
    ],
    action: "Try the demo", href: "/catalog/import",
  },
  {
    name: "Starter", code: "starter", price: "$27", description: "For small teams that need repeatable validation and shareable results.", featured: true,
    features: [
      ["CSV validation", "Included"],
      ["Required-field and duplicate checks", "Included"],
      ["Validation metrics and issue details", "Included"],
      ["Downloadable validation report", "Included"],
      ["Signed-in organization workspace", "Included"],
      ["Up to 3 total team seats", "Included"],
      ["XLS, XLSX, JSON and XML inputs", "Not included"],
      ["API, SFTP and database connections", "Not included"],
    ],
    action: "Choose Starter", href: "/billing?plan=starter",
  },
  {
    name: "Growth", code: "growth", price: "$64", description: "For teams working with multiple supplier feeds and connected data sources.",
    features: [
      ["Everything in Starter", "Included"],
      ["XLS, XLSX, JSON and XML inputs", "Included"],
      ["REST API, SFTP and SQL Server connections", "Included"],
      ["Multiple supplier catalog imports", "Included"],
      ["Up to 10 total team seats", "Included"],
      ["Recurring validation and version comparison", "Planned"],
      ["Team review and issue assignment", "Planned"],
    ],
    action: "Choose Growth", href: "/billing?plan=growth",
  },
  {
    name: "Business", code: "business", price: "$153", description: "For operations teams coordinating catalog quality across departments.",
    features: [
      ["Everything in Growth", "Included"],
      ["Team review and issue assignment", "Planned"],
      ["Approval workflows", "Planned"],
      ["Audit history and governance", "Planned"],
      ["Advanced integrations", "Planned"],
      ["Up to 25 total team seats", "Included"],
    ],
    action: "Choose Business", href: "/billing?plan=business",
  },
  {
    name: "Enterprise", price: "Custom", description: "For organizations with custom scale, integration and governance requirements.",
    features: [
      ["Everything in Business", "Included"],
      ["Custom import and usage limits", "Planned"],
      ["Custom governance and security controls", "Planned"],
      ["Dedicated onboarding and support terms", "Planned"],
      ["Custom team-seat allowance", "Planned"],
    ],
    action: "Discuss Enterprise", href: "/contact?intent=pricing&plan=enterprise", custom: true,
  },
];

export default function PricingPage() {
  const { user, loading } = useAuth();
  return (
    <main id="main" className="page pricing-page">
      <div className="container">
        <section className="pricing-intro">
          <div className="eyebrow">Plans built around your workflow</div>
          <h1>Start with a demo. Upgrade when your catalog operations need more.</h1>
          <p>Reference prices are in USD per month. Paid checkout is not enabled until the Razorpay account, plan IDs and webhook are configured. Features marked Planned are not currently available.</p>
        </section>
        <section className="pricing-grid" aria-label="CompatFlow plans">
          {plans.map(plan => {
            const href = plan.code
              ? (user ? `/workspace?plan=${plan.code}` : `/sign-up?plan=${plan.code}`)
              : plan.href;
            const action = plan.code && user ? "View billing" : plan.action;
            return (
              <article className={`pricing-card${plan.featured ? " pricing-card-featured" : ""}`} key={plan.name}>
                <div className="pricing-card-top">
                  <div className="eyebrow">{plan.name === "Demo" ? "No account required" : plan.featured ? "For small teams" : plan.custom ? "Custom requirements" : "For growing operations"}</div>
                  <h2>{plan.name}</h2><p>{plan.description}</p>
                  <div className="pricing-amount"><strong>{plan.price}</strong>{plan.price !== "Free" && plan.price !== "Custom" && <span>/ month</span>}</div>
                </div>
                <div className="pricing-includes">Capabilities</div>
                <ul className="pricing-feature-list">
                  {plan.features.map(([feature, status]) => (
                    <li key={`${plan.name}-${feature}`}>
                      <span>{feature}</span>
                      <span className={status === "Included" ? "pricing-status available" : "pricing-status planned"}>{status}</span>
                    </li>
                  ))}
                </ul>
                <div className="pricing-card-action">
                  <Link className={plan.featured ? "button" : "button button-secondary"} href={href} aria-disabled={loading && !!plan.code}>
                    {loading && plan.code ? "Checking account…" : action}
                  </Link>
                </div>
              </article>
            );
          })}
        </section>
        <section className="pricing-footnote">
          <h2>Demo vs Starter</h2>
          <p>The public demo lets anyone test CSV and Excel validation without signing in. It is limited to 5 MB per file, shows results on screen and does not offer report downloads or an organization workspace.</p>
          <p>Starter adds an organization workspace, a 25 MB subscribed-import ceiling and downloadable validation reports. It does not unlock JSON/XML ingestion or external source connectors.</p>
          <p>Growth connector access is subject to operator-side host allowlisting and source security configuration. A plan becomes active only after a verified payment-provider webhook.</p>
          <Link className="pricing-text-link" href="/catalog/import">Try the public demo</Link>
        </section>
      </div>
    </main>
  );
}
