"use client";

import Link from "next/link";

const plans = [
  {
    name: "Demo",
    price: "Free",
    description: "Evaluate the core validation workflow before creating an account.",
    featured: false,
    features: [
      ["CSV upload and validation", true],
      ["Required-field and duplicate checks", true],
      ["On-screen quality metrics", true],
      ["Issue details and recommendations", true],
      ["Downloadable validation report", false],
      ["Excel, JSON and XML inputs", false],
      ["Supplier API, SFTP and database connections", false],
      ["Organization workspace and team access", false],
    ],
    action: "Try the demo",
    href: "/catalog/import",
  },
  {
    name: "Starter",
    price: "$27",
    description: "For individuals and small teams that need repeatable validation and shareable results.",
    featured: true,
    features: [
      ["CSV upload and validation", true],
      ["Required-field and duplicate checks", true],
      ["On-screen quality metrics", true],
      ["Issue details and recommendations", true],
      ["Downloadable validation report", true],
      ["Excel, JSON and XML inputs", false],
      ["Supplier API, SFTP and database connections", false],
      ["Organization workspace and team access", true],
    ],
    action: "Create an account",
    href: "/sign-up",
  },
  {
    name: "Growth",
    price: "$64",
    description: "For teams handling multiple supplier feeds and structured catalog inputs.",
    featured: false,
    features: [
      ["Everything in Starter", true],
      ["Excel, JSON and XML inputs", true],
      ["Supplier API, SFTP and database connections", true],
      ["Multiple supplier catalogs", true],
      ["Recurring validation and change comparison", true],
      ["Team review and issue assignment", false],
    ],
    action: "Discuss Growth",
    href: "/contact?intent=pricing&plan=growth",
  },
  {
    name: "Business",
    price: "$153",
    description: "For operations teams coordinating catalog quality across people and systems.",
    featured: false,
    features: [
      ["Everything in Growth", true],
      ["Team review and issue assignment", true],
      ["Approval workflows and audit history", true],
      ["Advanced integrations", true],
      ["Custom governance and support", false],
    ],
    action: "Discuss Business",
    href: "/contact?intent=pricing&plan=business",
  },
];

export default function PricingPage() {
  return (
    <main id="main" className="page pricing-page">
      <div className="container">
        <section className="pricing-intro">
          <div className="eyebrow">Simple plan boundaries</div>
          <h1>Start with a demo. Upgrade when the workflow earns its place.</h1>
          <p>
            Reference prices are in USD per month. These are proposed early-access
            prices; paid checkout is not enabled yet. Feature access is enforced
            by the subscription on the backend when billing is activated.
          </p>
        </section>

        <section className="pricing-grid" aria-label="CompatFlow plans">
          {plans.map((plan) => (
            <article className={`pricing-card${plan.featured ? " pricing-card-featured" : ""}`} key={plan.name}>
              <div className="pricing-card-top">
                <div className="eyebrow">{plan.name === "Demo" ? "No account required" : plan.featured ? "For small teams" : "For growing operations"}</div>
                <h2>{plan.name}</h2>
                <p>{plan.description}</p>
                <div className="pricing-amount">
                  <strong>{plan.price}</strong>
                  {plan.price !== "Free" && <span>/ month</span>}
                </div>
              </div>
              <div className="pricing-includes">Included capabilities</div>
              <ul className="pricing-feature-list">
                {plan.features.map(([feature, included]) => (
                  <li key={feature}>
                    <span>{feature}</span>
                    <span className={included ? "pricing-status available" : "pricing-status planned"}>{included ? "Included" : "Not included"}</span>
                  </li>
                ))}
              </ul>
              <div className="pricing-card-action">
                <Link className={plan.featured ? "button" : "button button-secondary"} href={plan.href}>{plan.action}</Link>
              </div>
            </article>
          ))}
        </section>

        <section className="pricing-footnote">
          <h2>What is the difference between Demo and Starter?</h2>
          <p>
            The public demo is a limited, temporary evaluation: CSV only, no
            account, no downloadable report and no organization workspace.
            Starter adds a signed-in workspace and downloadable validation
            reports. It does not unlock connector ingestion or the additional
            structured file formats.
          </p>
          <p>
            Growth and Business capabilities shown above are plan targets, not
            claims that every workflow is currently live. Subscription checkout
            and provider configuration are still being completed.
          </p>
          <Link className="pricing-text-link" href="/catalog/import">Try the public CSV demo</Link>
        </section>
      </div>
    </main>
  );
}
