import Link from "next/link";
import type { Metadata } from "next";
export const metadata: Metadata = { title: "About Us", description: "Learn about CompatFlow and its focus on supplier catalog data quality." };
export default function AboutPage() {
 return <main id="main" className="about-page">
  <section className="about-hero"><div className="container about-hero-inner"><span className="eyebrow">ABOUT COMPATFLOW</span><h1>Making supplier product data easier to work with.</h1><p>CompatFlow is an early-stage product being developed around a practical problem in commerce operations: supplier catalog data arrives in different formats, with inconsistencies that can create extra work before product information is ready for use.</p></div></section>
  <section className="container about-content">
   <div className="about-section"><span className="eyebrow">OUR FOCUS</span><h2>Bring more structure to catalog workflows.</h2><p>The product direction is to help teams inspect supplier files, identify data-quality issues and build more consistent processes for reviewing product information and supplier-driven changes.</p></div>
   <div className="about-pillars">
    <article className="about-pillar"><span>01</span><h3>Validate</h3><p>Identify missing required fields, invalid values and duplicate SKUs in supplier CSV files.</p><small>Available in current demo</small></article>
    <article className="about-pillar"><span>02</span><h3>Standardize</h3><p>Develop a consistent foundation for product data across supplier formats and structures.</p><small>Planned capability</small></article>
    <article className="about-pillar"><span>03</span><h3>Review changes</h3><p>Work toward clearer review of supplier-driven product updates before they affect downstream workflows.</p><small>Planned capability</small></article>
   </div>
   <div className="about-current"><div><span className="eyebrow">WHERE WE ARE TODAY</span><h2>An early-stage product, built transparently.</h2><p>The current public demonstration supports CSV validation, required-column checks, row validation, duplicate SKU detection and a limited preview. Advanced workflows and subscription features are still in development.</p></div><Link className="button" href="/catalog/import">Explore the CSV demo</Link></div>
   <div className="about-contact"><h2>Have a catalog workflow to discuss?</h2><p>We welcome conversations about supplier data challenges and practical product requirements.</p><a className="about-email" href="mailto:sarvasettyrevanth.66@gmail.com?subject=CompatFlow%20enquiry">Contact CompatFlow</a></div>
  </section>
 </main>;
}