"use client";

import Link from "next/link";
import { useAuth } from "@/components/auth-provider";

const capabilities = [
  {
    number: "01",
    title: "Validate supplier data",
    description: "Check required product fields, inconsistent values, malformed rows and duplicate SKUs before data reaches your catalog.",
    status: "Available",
  },
  {
    number: "02",
    title: "Normalize incoming files",
    description: "Bring supplier files with different column names and structures into a consistent product-data workflow.",
    status: "Available by plan",
  },
  {
    number: "03",
    title: "Connect source systems",
    description: "Prepare catalog data from approved REST APIs, SFTP locations and SQL Server sources without manual file handoffs.",
    status: "Connector access by plan",
  },
];

const steps = [
  ["01", "Connect or upload", "Start with a CSV demo or use an authenticated workspace to access the input methods included in your plan."],
  ["02", "Validate and inspect", "Review field completeness, duplicate identifiers, rejected records and actionable validation issues."],
  ["03", "Decide what moves forward", "Use the validation output to correct supplier data before it is committed to your catalog workflow."],
];

export default function HomePage() {
  const { user } = useAuth();
  return (
    <main id="main" className="home-page">
      <section className="home-hero">
        <div className="container home-hero-grid">
          <div className="home-hero-copy">
            <div className="eyebrow">Supplier catalog operations</div>
            <h1>Make supplier product data reliable before it reaches your catalog.</h1>
            <p className="home-hero-description">
              CompatFlow gives commerce and operations teams a structured way
              to validate supplier files, identify data-quality problems and
              manage catalog inputs across teams and source systems.
            </p>
            <div className="home-hero-actions">
              {user ? <Link className="button" href="/workspace">Open workspace</Link> : <Link className="button" href="/catalog/import">Try the CSV demo</Link>}
              {user ? <Link className="button button-secondary" href="/catalog/import">Validate catalog</Link> : <Link className="button button-secondary" href="/pricing">Explore plans</Link>}
            </div>
            <p className="home-hero-note">{user ? "You are signed in. Open your workspace to manage your organization and catalog operations." : "Explore the public demo without an account. Subscription features require an authorized workspace."}</p>
          </div>
          <div className="home-visual" aria-label="CompatFlow workflow overview">
            <div className="home-visual-top">
              <span className="home-visual-title">COMPATFLOW / WORKFLOW</span>
              <span className="home-visual-live"><span className="home-visual-dot" />Data quality operations</span>
            </div>
            <div className="home-visual-body">
              <div className="eyebrow">Supplier data lifecycle</div>
              <h2 className="home-visual-metric">From source to review</h2>
              <p className="home-visual-caption">One controlled workflow for incoming catalog data.</p>
              <div className="home-steps-grid">
                <article className="home-step"><div className="home-card-number">01 / INPUT</div><h3>Supplier sources</h3><p>Files, APIs and databases</p></article>
                <article className="home-step"><div className="home-card-number">02 / CHECK</div><h3>Validation</h3><p>Structure and data quality</p></article>
                <article className="home-step"><div className="home-card-number">03 / REVIEW</div><h3>Clear outcomes</h3><p>Issues and next actions</p></article>
              </div>
            </div>
            <div className="home-visual-footer"><span>Built for product-data operations</span><span>Access depends on plan</span></div>
          </div>
        </div>
      </section>

      <div className="home-proof-strip" aria-label="Platform focus">
        <span>Supplier catalogs</span><span>Data validation</span><span>Source integrations</span><span>Operational control</span>
      </div>

      <section className="home-section" id="capabilities">
        <div className="container">
          <div className="home-section-heading">
            <div className="eyebrow">Platform capabilities</div>
            <h2>Control the quality of catalog inputs.</h2>
            <p>CompatFlow is organized around the practical work required to receive, validate and review supplier product data.</p>
          </div>
          <div className="home-capability-grid">
            {capabilities.map(item => (
              <article className="home-capability-card" key={item.number}>
                <div className="home-card-number">{item.number}</div>
                <h3>{item.title}</h3>
                <p>{item.description}</p>
                <span className="home-capability-status">{item.status}</span>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="home-section" id="workflow">
        <div className="container">
          <div className="home-section-heading">
            <div className="eyebrow">How it works</div>
            <h2>A consistent process for every supplier input.</h2>
          </div>
          <div className="home-steps-grid">
            {steps.map(([number, title, description]) => (
              <article className="home-step" key={number}>
                <div className="home-card-number">STEP {number}</div>
                <h3>{title}</h3>
                <p>{description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="home-section">
        <div className="container">
          <div className="home-demo-cta">
            <div>
              <div className="eyebrow">Start with a real workflow</div>
              <h2>Try supplier CSV validation before you sign up.</h2>
              <p>Upload a non-confidential CSV sample, review validation results on screen and see whether CompatFlow fits your workflow. Demo uploads are not saved.</p>
            </div>
            <Link className="button home-cta-button" href="/catalog/import">Open the CSV demo</Link>
          </div>
        </div>
      </section>

      <section className="home-final-cta">
        <div className="container">
          <div className="eyebrow">Move beyond manual supplier checks</div>
          <h2>Bring supplier data into a workflow your team can trust.</h2>
          <p>Compare plan access or tell us about the catalog workflow you need to support.</p>
          <div className="home-hero-actions">
            <Link className="button" href="/pricing">Compare plans</Link>
            <Link className="button button-secondary" href="/contact?intent=demo">Request a guided demo</Link>
          </div>
        </div>
      </section>
    </main>
  );
}
