"use client";

import Link from "next/link";

const plans = [
  {
    name: "Starter",
    price: "$27",
    description: "For small teams validating supplier product data.",
    items: [
      ["CSV catalog validation", "Available in demo"],
      ["Required-field and structure checks", "Available in demo"],
      ["Duplicate SKU detection", "Available in demo"],
      ["Validation metrics and issue report", "Available in demo"],
    ],
  },
  {
    name: "Growth",
    price: "$64",
    description: "For teams managing recurring supplier catalog updates.",
    items: [
      ["Everything in Starter", "Planned"],
      ["Multiple supplier catalogs", "Planned"],
      ["Catalog version comparison", "Planned"],
      ["Custom validation rules", "Planned"],
      ["Recurring validation", "Planned"],
    ],
  },
  {
    name: "Business",
    price: "$153",
    description: "For teams coordinating catalog quality across operations.",
    items: [
      ["Everything in Growth", "Planned"],
      ["Team review and issue assignment", "Planned"],
      ["Approval workflows", "Planned"],
      ["Audit history and exports", "Planned"],
      ["Advanced integrations", "Planned"],
    ],
  },
  {
    name: "Enterprise",
    price: "Custom",
    description: "For organizations with higher volume and integration needs.",
    items: [
      ["Custom catalog and validation limits", "Planned"],
      ["Integration and governance options", "Planned"],
      ["Security and support requirements", "Planned"],
      ["Commercial and SLA discussions", "Planned"],
    ],
  },
];

export default function PricingPage() {
  return (
    <main id="main" className="page pricing-page">
      <div className="container">
        <section className="pricing-intro">
          <div className="eyebrow">Global, capability-based plans</div>
          <h1>Pricing that grows with your catalog operations.</h1>
          <p>
            Reference prices are shown in USD per month. Local taxes may apply.
            Paid subscriptions and billing are not yet available.
          </p>
          <div className="pricing-note" role="note">
            <strong>Early-access pricing:</strong> These are proposed prices,
            not active subscription offers. Feature availability is labelled
            honestly below.
          </div>
        </section>

        <section className="pricing-grid" aria-label="CompatFlow pricing plans">
          {plans.map((plan) => (
            <article className="pricing-card" key={plan.name}>
              <div className="pricing-card-top">
                <h2>{plan.name}</h2>
                <p>{plan.description}</p>
                <div className="pricing-amount">
                  <strong>{plan.price}</strong>
                  {plan.price !== "Custom" && <span>/ month</span>}
                </div>
              </div>
              <div className="pricing-includes">Plan scope</div>
              <ul className="pricing-feature-list">
                {plan.items.map(([item, status]) => (
                  <li key={item}>
                    <span>{item}</span>
                    <span className={status === "Available in demo" ? "pricing-status available" : "pricing-status planned"}>
                      {status}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="pricing-card-action">
                {plan.name === "Starter" ? (
                  <Link className="button button-secondary" href="/catalog/import">
                    Try CSV demo
                  </Link>
                ) : (
                  <a className="button button-secondary" href="mailto:sarvasettyrevanth.66@gmail.com?subject=CompatFlow%20early%20access%20enquiry">
                    Register interest
                  </a>
                )}
              </div>
            </article>
          ))}
        </section>

        <section className="pricing-footnote">
          <h2>What is available today?</h2>
          <p>
            The current public demo supports in-memory CSV validation. Detailed
            quality metrics and issue-level recommendations are being expanded.
            Persistent imports, recurring checks, collaboration, integrations
            and subscription billing are not yet available.
          </p>
          <p>
            Do not upload confidential supplier files, personal information or
            production catalog data to the public demo.
          </p>
          <Link className="pricing-text-link" href="/catalog/import">
            Explore the current CSV demo
          </Link>
        </section>
      </div>
    </main>
  );
}
