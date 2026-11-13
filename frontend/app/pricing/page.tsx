"use client";

import Link from "next/link";

const plans = [
  {
    name: "Starter",
    price: "₹1,999",
    description: "For teams that need a straightforward starting point for supplier file quality.",
    items: [
      ["CSV catalog validation", "Demo available"],
      ["Required-field checks", "Demo available"],
      ["Duplicate SKU detection", "Demo available"],
      ["Validation summary", "Demo available"],
    ],
  },
  {
    name: "Professional",
    price: "₹5,999",
    description: "For teams managing multiple supplier catalogs and more structured review workflows.",
    items: [
      ["Everything in Starter", "Planned"],
      ["Multiple catalogs and suppliers", "Planned"],
      ["Catalog change detection", "Planned"],
      ["Custom validation rules", "Planned"],
      ["Scheduled validation and API access", "Planned"],
    ],
  },
  {
    name: "Business",
    price: "₹14,999",
    description: "For teams that need controlled catalog operations across business workflows.",
    items: [
      ["Everything in Professional", "Planned"],
      ["Product data transformations", "Planned"],
      ["Approval workflows", "Planned"],
      ["SFTP and catalog synchronization", "Planned"],
      ["Audit logs", "Planned"],
    ],
  },
  {
    name: "Enterprise",
    price: "Custom",
    description: "For organizations with specific integration, governance and deployment requirements.",
    items: [
      ["Custom integrations", "Planned"],
      ["Deployment options", "Planned"],
      ["Governance controls", "Planned"],
      ["SLA and dedicated support", "Planned"],
    ],
  },
];

export default function PricingPage() {
  return (
    <>

      <main id="main" className="page pricing-page">
        <div className="container">
          <section className="pricing-intro">
            <div className="eyebrow">Simple, capability-based plans</div>
            <h1>Pricing that grows with your catalog operations.</h1>
            <p>
              Indicative monthly pricing for the planned CompatFlow platform.
              The public product is currently an early-stage CSV validation demo;
              paid plans and subscription billing are not yet available.
            </p>
            <div className="pricing-note" role="note">
              <strong>Pricing status:</strong> These are proposed prices, not
              active offers. Annual pricing has not been published.
            </div>
          </section>

          <section className="pricing-grid" aria-label="Indicative pricing plans">
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
                <div className="pricing-includes">Planned plan scope</div>
                <ul className="pricing-feature-list">
                  {plan.items.map(([item, status]) => (
                    <li key={item}>
                      <span>{item}</span>
                      <span className={status === "Demo available" ? "pricing-status available" : "pricing-status planned"}>
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
              The public demo currently supports CSV uploads, required-column
              checks, row validation, duplicate SKU checks and a validation
              preview. Files are processed in memory and are not saved. The
              advanced capabilities listed above are planned and should not be
              treated as currently available plan features.
            </p>
            <p>
              Do not upload confidential supplier data, personal information
              or production catalog files to the public demo.
            </p>
            <Link className="pricing-text-link" href="/catalog/import">
              Explore the current CSV demo
            </Link>
          </section>
        </div>
      </main>


    </>
  );
}
