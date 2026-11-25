"use client";

import Link from "next/link";
import { useAuth } from "@/components/auth-provider";

const capabilities = [
  ["01 / INGEST", "Bring supplier data together", "Import supplier catalogs and keep incoming product data organized by workflow."],
  ["02 / VALIDATE", "Find catalog issues earlier", "Check structure, required fields, product attributes and data consistency."],
  ["03 / REVIEW", "Turn findings into action", "Inspect exceptions, recommendations and validation outcomes in one workspace."],
];
const steps = [
  ["01", "Connect or import", "Bring supplier catalogs through the available file and source workflows."],
  ["02", "Normalize and validate", "Map incoming fields and check product data against a validation profile."],
  ["03", "Review the results", "Inspect issues, recommendations and validation outcomes."],
  ["04", "Act with confidence", "Use reviewed output to guide catalog operations and supplier follow-up."],
];

function ProductPreview() {
  return <div className="editorial-preview" aria-label="Illustrative CompatFlow workspace preview">
    <div className="preview-topbar"><div className="preview-brand"><span className="preview-brand-mark">C</span> COMPATFLOW / WORKSPACE</div><span className="preview-status"><i /> WORKSPACE OVERVIEW</span></div>
    <div className="preview-content">
      <div className="preview-heading"><div><span className="preview-kicker">CATALOG OPERATIONS</span><h3>Supplier data overview</h3><p>One place to inspect incoming catalog work.</p></div><span className="preview-date">CURRENT WORKSPACE</span></div>
      <div className="preview-metrics"><div><span>WORKFLOW</span><strong>Import → Validate</strong><small>Structured catalog review</small></div><div><span>DATA SOURCES</span><strong>Connected inputs</strong><small>Files and configured sources</small></div><div><span>OUTPUT</span><strong>Review-ready</strong><small>Issues and recommendations</small></div></div>
      <div className="preview-table-wrap"><div className="preview-table-title"><strong>Workflow stages</strong><span>PROCESS OVERVIEW</span></div>
        {[[ "01", "Import", "Supplier catalog intake", "Input" ],["02","Validation","Structure and attribute checks","Checks"],["03","Review","Exceptions and recommendations","Action"]].map(row=><div className="preview-table-row" key={row[0]}><span><b className="preview-index">{row[0]}</b> {row[1]}</span><span>{row[2]}</span><em>{row[3]}</em></div>)}
      </div>
    </div><div className="preview-bottom"><span>SUPPLIER CATALOG CHANGE OPERATIONS</span><span>COMPATFLOW</span></div>
  </div>;
}

export default function HomePage() {
  const { user } = useAuth();
  const primaryHref = user ? "/workspace" : "/contact?intent=demo";
  const primaryText = user ? "Open workspace" : "Request a demo";
  return <main id="main" className="editorial-home">
    <section className="editorial-hero">
      <div className="editorial-eyebrow"><span /> SUPPLIER CATALOG CHANGE OPERATIONS</div>
      <h1>Bring every product catalog into focus.</h1>
      <p className="editorial-lede">A structured workspace to import supplier data, validate product information and review catalog issues before they become operational problems.</p>
      <div className="editorial-actions"><Link className="editorial-button editorial-button-dark" href={primaryHref}>{primaryText}<span>↗</span></Link><Link className="editorial-text-link" href="#workflow">Explore the workflow <span>↓</span></Link></div>
      <div className="editorial-hero-visual"><ProductPreview /></div>
    </section>
    <section className="editorial-trust"><span>BUILT AROUND THE WORK THAT MATTERS</span><div><b>Supplier catalogs</b><b>Product attributes</b><b>Data validation</b><b>Catalog review</b></div></section>
    <section className="editorial-collage"><div className="collage-center"><span className="collage-mark">C</span><strong>One clear view<br/>of catalog quality.</strong></div><div className="collage-card collage-card-a"><span>01 / INPUT</span><strong>Supplier files</strong><p>Bring product data into a consistent starting point.</p><div className="file-lines"><i/><i/><i/></div></div><div className="collage-card collage-card-b"><span>02 / QUALITY</span><strong>Validation checks</strong><p>Identify missing, inconsistent and malformed attributes.</p><div className="quality-bars"><i/><i/><i/></div></div><div className="collage-orbit">↗</div></section>
    <section className="editorial-manifesto"><span className="editorial-eyebrow">THE PROBLEM WE SOLVE</span><h2>Supplier data arrives in different shapes. Your catalog workflow should not have to.</h2><p>CompatFlow gives product and commerce teams a repeatable process for receiving, checking and reviewing supplier catalog changes—without losing sight of the data behind each decision.</p></section>
    <section className="editorial-feature-section" id="capabilities">
      <div className="editorial-feature-visual"><div className="feature-window"><div className="feature-window-head"><span>CATALOG REVIEW</span><span>● READY TO INSPECT</span></div><div className="feature-window-body"><div className="feature-file-icon">▤</div><strong>Supplier catalog</strong><p>Incoming product information</p><div className="feature-rule"/><div className="feature-list"><span><i/> Field structure</span><span><i/> Required attributes</span><span><i/> Data consistency</span><span><i/> Review findings</span></div></div></div></div>
      <div className="editorial-feature-copy"><span className="editorial-eyebrow">A PRACTICAL FOUNDATION</span><h2>Catalog operations, with more clarity at every step.</h2><div className="editorial-feature-list">{capabilities.map(([n,title,body])=><article key={n}><span>{n}</span><div><h3>{title}</h3><p>{body}</p></div></article>)}</div></div>
    </section>
    <section className="editorial-workflow" id="workflow"><div className="editorial-section-heading"><span className="editorial-eyebrow">HOW COMPATFLOW WORKS</span><h2>From supplier input to informed review.</h2><p>A clear sequence for the recurring work of product-data teams.</p></div><div className="editorial-step-grid">{steps.map(([n,title,body])=><article key={n}><span>STEP {n}</span><div className="step-symbol">{n === "01" ? "⇧" : n === "02" ? "⌁" : n === "03" ? "◫" : "↗"}</div><h3>{title}</h3><p>{body}</p></article>)}</div></section>
    <section className="editorial-teams"><div className="editorial-section-heading"><span className="editorial-eyebrow">DESIGNED FOR CATALOG TEAMS</span><h2>Useful across the product data lifecycle.</h2></div><div className="editorial-team-grid"><article><span>01</span><h3>Ecommerce operations</h3><p>Keep product listings and supplier updates organized before publication.</p></article><article><span>02</span><h3>Product information teams</h3><p>Review attribute completeness and consistency across incoming catalogs.</p></article><article><span>03</span><h3>Supplier management</h3><p>Make data gaps and follow-up requirements easier to identify.</p></article><article><span>04</span><h3>Data operations</h3><p>Establish a repeatable validation process across catalog inputs.</p></article></div></section>
    <section className="editorial-cta"><div className="cta-mark">C</div><span className="editorial-eyebrow">SEE THE WORKFLOW IN CONTEXT</span><h2>Make supplier catalog work easier to see—and easier to manage.</h2><p>Explore CompatFlow or request a guided walkthrough of the current product workflows.</p><div className="editorial-actions"><Link className="editorial-button editorial-button-light" href={primaryHref}>{primaryText}<span>↗</span></Link><Link className="editorial-cta-link" href="/pricing">View plans</Link></div></section>
  </main>;
}
