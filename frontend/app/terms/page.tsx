import type { Metadata } from "next";
export const metadata: Metadata = { title: "Terms & Conditions", description: "Terms governing access to the CompatFlow public demonstration." };
const operatorName = process.env.NEXT_PUBLIC_OPERATOR_NAME || "CompatFlow";
const contactEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "Contact email not configured";
export default function TermsPage() {
 return <main id="main" className="legal-page"><div className="container legal-container">
  <header className="legal-hero"><span className="eyebrow">LEGAL / TERMS</span><h1>Terms &amp; Conditions</h1><p>Please read these terms before using the CompatFlow public demonstration.</p><span className="legal-updated">Last updated: 13 November 2026</span></header>
  <div className="legal-layout"><aside className="legal-aside"><span>ON THIS PAGE</span><a href="#service">The demonstration</a><a href="#acceptable-use">Acceptable use</a><a href="#data">Files and data</a><a href="#outputs">Results and decisions</a><a href="#ownership">Intellectual property</a><a href="#availability">Availability and disclaimers</a><a href="#changes">Changes and contact</a></aside>
   <article className="legal-content">
    <section id="service"><h2>1. The demonstration</h2><p>CompatFlow is an early-stage product demonstration operated by {operatorName}. The current public demo provides CSV validation only. Other capabilities described on the website may be planned, incomplete or unavailable. The demo is not a production catalog-management service.</p></section>
    <section id="acceptable-use"><h2>2. Acceptable use</h2><p>You may use the demonstration only for lawful evaluation and testing. You must not attempt to disrupt the service, bypass its safeguards, upload malicious files, probe systems without authorization or access information that does not belong to you.</p></section>
    <section id="data"><h2>3. Files and data</h2><p>The public demo accepts CSV files for validation. Files are processed in memory by the application and are not saved as catalog records or imported into a production system.</p><div className="legal-callout">Do not upload confidential supplier files, personal information, credentials or real customer catalog data.</div></section>
    <section id="outputs"><h2>4. Results and business decisions</h2><p>Validation results and sample outputs are provided to help evaluate data quality. You are responsible for independently checking product specifications, compatibility, regulatory requirements and any information before relying on it for commercial, safety-related or purchasing decisions.</p></section>
    <section id="ownership"><h2>5. Intellectual property</h2><p>The CompatFlow software, brand elements and original materials are protected by applicable intellectual property laws. These terms grant you a limited, revocable right to access the demonstration; they do not transfer ownership or grant broader rights to the underlying product.</p></section>
    <section id="availability"><h2>6. Availability and disclaimers</h2><p>The demonstration is provided on an as-available basis. Availability, features and outputs may change without notice. No uninterrupted service, error-free operation, accuracy or fitness for a particular purpose is promised.</p></section>
    <section id="changes"><h2>7. Changes and contact</h2><p>These terms may be updated as CompatFlow develops. Continued use after an updated version is published constitutes use under the revised terms, to the extent permitted by applicable law. For questions, contact {contactEmail}.</p></section>
   </article>
  </div>
 </div></main>;
}