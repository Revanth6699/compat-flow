import type { Metadata } from "next";
export const metadata: Metadata = { title: "Privacy Policy", description: "How the CompatFlow public demonstration processes information." };
const operatorName = process.env.NEXT_PUBLIC_OPERATOR_NAME || "CompatFlow";
const contactEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "Contact email not configured";
export default function PrivacyPage() {
 return <main id="main" className="legal-page"><div className="container legal-container">
  <header className="legal-hero"><span className="eyebrow">LEGAL / PRIVACY</span><h1>Privacy Policy</h1><p>This policy explains what information the current CompatFlow demonstration processes and how it is handled.</p><span className="legal-updated">Last updated: 13 November 2026</span></header>
  <div className="legal-layout"><aside className="legal-aside"><span>ON THIS PAGE</span><a href="#operator">Who operates CompatFlow</a><a href="#information">Information processed</a><a href="#purpose">How information is used</a><a href="#cookies">Cookies and local storage</a><a href="#providers">Service providers</a><a href="#retention">Retention and security</a><a href="#rights">Your choices and contact</a></aside>
   <article className="legal-content">
    <section id="operator"><h2>1. Who operates CompatFlow</h2><p>CompatFlow is an early-stage product demonstration operated by {operatorName}. Questions about this policy can be sent to {contactEmail}.</p></section>
    <section id="information"><h2>2. Information processed</h2><p>When you use the public CSV validator, the CSV file you select is sent to the CompatFlow API for validation. The application processes the file in memory and does not save the uploaded file or persist catalog records.</p><p>Hosting and infrastructure providers may process technical request information, such as IP address, browser details, timestamps and service logs, when delivering and protecting the website.</p></section>
    <section id="purpose"><h2>3. How information is used</h2><p>Information is used to provide the demonstration, respond to enquiries, maintain service security and investigate reliability issues. The public demo is not intended for confidential or production information.</p><div className="legal-callout">Do not upload personal information, confidential supplier files, credentials or production catalog data.</div></section>
    <section id="cookies"><h2>4. Cookies and local storage</h2><p>The demonstration stores your cookie preference in your browser&apos;s local storage. No analytics or advertising tracking scripts are intentionally loaded by this application.</p></section>
    <section id="providers"><h2>5. Service providers</h2><p>The website and API rely on hosting and infrastructure providers to deliver the service. Those providers may process technical information under their own terms and privacy practices. Their current terms should be reviewed separately.</p></section>
    <section id="retention"><h2>6. Retention and security</h2><p>Uploaded CSV content is not persisted by the application. Technical logs may be retained by infrastructure providers under their own retention policies. Reasonable safeguards are used, but no internet service can guarantee absolute security.</p></section>
    <section id="rights"><h2>7. Your choices and contact</h2><p>Depending on applicable law, you may have rights to request access, correction, deletion or objection in relation to personal information. Contact {contactEmail} with a request or privacy question.</p></section>
    <section><h2>8. Changes to this policy</h2><p>This policy may be revised as the product, its infrastructure or its data practices change. The latest version will be published on this page.</p></section>
   </article>
  </div>
 </div></main>;
}