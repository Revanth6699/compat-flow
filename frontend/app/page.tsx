import Link from "next/link";

const capabilities = [
  {
    number: "01",
    title: "Catalog validation",
    description:
      "Check supplier files for required fields, malformed values and duplicate SKUs before data moves further into your workflow.",
    status: "Available in demo",
    available: true,
  },
  {
    number: "02",
    title: "Product data normalization",
    description:
      "Create a more consistent product data foundation across supplier formats, naming conventions and catalog structures.",
    status: "Planned",
    available: false,
  },
  {
    number: "03",
    title: "Catalog change review",
    description:
      "Build a controlled way to understand supplier-driven product changes before they affect downstream commerce systems.",
    status: "Planned",
    available: false,
  },
];

const workflow = [
  {
    number: "01",
    title: "Receive supplier data",
    description: "Start with a supplier catalog file and its product information.",
  },
  {
    number: "02",
    title: "Check data quality",
    description: "Identify missing fields, inconsistent values and duplicate product identifiers.",
  },
  {
    number: "03",
    title: "Review what needs attention",
    description: "Understand which records are ready and which need correction.",
  },
];

export default function HomePage() {
  return (
    <>
      <header className="site-header">
        <div className="container header-inner">
          <Link className="brand" href="/" aria-label="CompatFlow home">
            compat<span className="brand-mark">flow</span>
          </Link>
          <nav className="nav" aria-label="Main navigation">
            <Link href="/catalog/import">Catalog demo</Link>
            <a href="#capabilities">Capabilities</a>
            <a href="#workflow">How it works</a>
            <Link href="/pricing">Pricing</Link>
            <Link href="/catalog/import">Get started</Link>
          </nav>
        </div>
      </header>

      <main id="main" className="home-page">
        <section className="home-hero">
          <div className="container home-hero-grid">
            <div className="home-hero-copy">
              <div className="eyebrow">Supplier catalog operations</div>
              <h1>Product data deserves a more consistent workflow.</h1>
              <p className="home-hero-description">
                CompatFlow is being built to help commerce teams validate,
                organize and review supplier catalog data before product
                changes move into downstream workflows.
              </p>
              <div className="home-hero-actions">
                <Link className="button" href="/catalog/import">
                  Try the CSV demo
                </Link>
                <a className="button button-secondary" href="#capabilities">
                  Explore the platform
                </a>
              </div>
              <p className="home-hero-note">
                Early-stage product · Public demo currently supports CSV validation
              </p>
            </div>

            <div className="home-visual" aria-label="Illustrative CompatFlow catalog interface preview">
              <div className="home-visual-top">
                <span className="home-visual-title">CATALOG WORKSPACE / PREVIEW</span>
                <span className="home-visual-live">
                  <span className="home-visual-dot" />
                  Interface concept
                </span>
              </div>
              <div className="home-visual-body">
                <div className="eyebrow">Supplier file overview</div>
                <div className="home-visual-metric">Catalog review</div>
                <div className="home-visual-caption">
                  An example of how product records could be organized for review.
                </div>
                <div className="home-visual-stats">
                  <div className="home-visual-stat">
                    <strong>SKU</strong>
                    <span>Product identifier</span>
                  </div>
                  <div className="home-visual-stat valid">
                    <strong>Data</strong>
                    <span>Field completeness</span>
                  </div>
                  <div className="home-visual-stat invalid">
                    <strong>Review</strong>
                    <span>Needs attention</span>
                  </div>
                </div>
                <table className="home-visual-table">
                  <thead>
                    <tr>
                      <th>Product record</th>
                      <th>Supplier data</th>
                      <th>Review</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>BRK-100 · Brake pad</td>
                      <td>Sample record</td>
                      <td><span className="home-visual-tag">Example</span></td>
                    </tr>
                    <tr>
                      <td>FLT-210 · Oil filter</td>
                      <td>Sample record</td>
                      <td><span className="home-visual-tag">Example</span></td>
                    </tr>
                    <tr>
                      <td>BRK-099 · Brake pad</td>
                      <td>Sample record</td>
                      <td><span className="home-visual-tag">Example</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div className="home-visual-footer">
                <span>Illustrative interface preview</span>
                <span>Not live catalog data</span>
              </div>
            </div>
          </div>
        </section>

        <div className="home-proof-strip" aria-label="Product focus">
          <span>Supplier data</span>
          <span>Product catalogs</span>
          <span>Data quality</span>
          <span>Commerce operations</span>
        </div>

        <section className="home-section" id="capabilities">
          <div className="container">
            <div className="home-section-heading">
              <div className="eyebrow">The platform</div>
              <h2>A clearer way to work with supplier product data.</h2>
              <p>
                Supplier files often arrive in different structures and levels
                of quality. CompatFlow is focused on making those catalog
                workflows easier to inspect and manage.
              </p>
            </div>
            <div className="home-capability-grid">
              {capabilities.map((item) => (
                <article className="home-capability-card" key={item.number}>
                  <div className="home-card-number">{item.number}</div>
                  <h3>{item.title}</h3>
                  <p>{item.description}</p>
                  <span className={item.available ? "home-capability-status" : "home-capability-status planned"}>
                    {item.status}
                  </span>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="home-section" id="workflow">
          <div className="container">
            <div className="home-section-heading">
              <div className="eyebrow">A practical workflow</div>
              <h2>From supplier file to informed review.</h2>
              <p>
                The intended workflow is simple: bring in supplier data,
                identify quality issues and make the next action clearer.
              </p>
            </div>
            <div className="home-steps-grid">
              {workflow.map((item) => (
                <article className="home-step" key={item.number}>
                  <div className="home-card-number">STEP {item.number}</div>
                  <h3>{item.title}</h3>
                  <p>{item.description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="home-section">
          <div className="container">
            <div className="home-demo-cta">
              <div>
                <div className="eyebrow">Explore the current demo</div>
                <h2>Start with a supplier CSV.</h2>
                <p>
                  Upload a non-confidential sample file to check required
                  columns, row values and duplicate SKUs. The current public
                  demo validates files in memory and does not save catalog data.
                </p>
              </div>
              <Link className="button home-cta-button" href="/catalog/import">
                Open CSV validator
              </Link>
            </div>
          </div>
        </section>

        <section className="home-final-cta">
          <div className="container">
            <div className="eyebrow">CompatFlow</div>
            <h2>Make supplier catalog changes easier to understand.</h2>
            <p>
              Explore the current validation demo and see the first part of
              the CompatFlow workflow.
            </p>
            <div className="home-hero-actions">
              <Link className="button" href="/catalog/import">
                Try the CSV demo
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="site-footer">
        <div className="container footer">
          <div className="footer-brand">
            <Link className="footer-brand-name" href="/">compatflow</Link>
            <span>Supplier catalog operations</span>
          </div>
          <div className="footer-links">
            <Link href="/catalog/import">CSV demo</Link>
            <Link href="/privacy">Privacy Policy</Link>
            <Link href="/terms">Terms &amp; Conditions</Link>
          </div>
          <span className="footer-copyright">© {new Date().getFullYear()} CompatFlow</span>
        </div>
      </footer>
    </>
  );
}
