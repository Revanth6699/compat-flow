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
  ["01", "Connect or upload", "Request demo access or use an authenticated workspace to access the input methods included in your plan."],
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
            <div className="eyebrow"><span className="home-eyebrow-mark"/> SUPPLIER DATA / CATALOG CONTROL</div>
            <h1>Catch catalog issues before they become operational problems.</h1>
            <p className="home-hero-description">
              CompatFlow gives commerce and operations teams a structured way
              to validate supplier files, identify data-quality problems and
              manage catalog inputs across teams and source systems.
            </p>
            <div className="home-hero-actions">
              {user ? <Link className="button" href="/workspace">Open workspace</Link> : <Link className="button" href="/contact?intent=demo">Request demo access</Link>}
              {user ? <Link className="button button-secondary" href="/catalog/import">Validate catalog</Link> : <Link className="button button-secondary" href="/pricing">Explore plans</Link>}
            </div>
            <p className="home-hero-note">{user ? "You are signed in. Open your workspace to manage your organization and catalog operations." : "Request demo access. Demo access is reviewed and granted individually."}</p>
          </div>
          <div className="home-visual" aria-label="Illustrative supplier catalog workflow">
            <div className="home-visual-top">
              <span className="home-visual-title">CF / OPERATIONS VIEW</span>
              <span className="home-visual-live"><span className="home-visual-dot" />WORKFLOW MODEL</span>
            </div>
            <div className="home-visual-body">
              <div className="home-visual-kicker">THE CATALOG CONTROL LOOP</div>
              <h2 className="home-visual-metric">From supplier file<br/>to confident review.</h2>
              <p className="home-visual-caption">A clear sequence for every incoming product-data change.</p>
              <div className="home-flow-list">
                <div className="home-flow-row"><span className="home-flow-index">01</span><span className="home-flow-symbol">↗</span><div><strong>Receive</strong><small>CSV files · APIs · SQL sources</small></div><span className="home-flow-state">INPUT</span></div>
                <div className="home-flow-connector"><span/></div>
                <div className="home-flow-row"><span className="home-flow-index">02</span><span className="home-flow-symbol">⌕</span><div><strong>Validate</strong><small>Fields · formats · duplicates</small></div><span className="home-flow-state">CHECK</span></div>
                <div className="home-flow-connector"><span/></div>
                <div className="home-flow-row"><span className="home-flow-index">03</span><span className="home-flow-symbol">✓</span><div><strong>Review</strong><small>Findings · corrections · next steps</small></div><span className="home-flow-state">DECIDE</span></div>
              </div>
            </div>
            <div className="home-visual-footer"><span>ILLUSTRATIVE WORKFLOW</span><span>Supplier data operations</span></div>
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
            <h2>A clearer standard for every supplier feed.</h2>
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
            <h2>Three deliberate steps. One accountable workflow.</h2>
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
              <h2>Request access to supplier CSV validation.</h2>
              <p>Submit a demo request. If approved, you will receive access to the limited CSV validation workflow.</p>
            </div>
            <Link className="button home-cta-button" href="/contact?intent=demo">Request demo access</Link>
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
