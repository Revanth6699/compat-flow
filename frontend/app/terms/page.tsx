import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms and Conditions",
  description: "CompatFlow demonstration terms and conditions.",
};

const operatorName = process.env.NEXT_PUBLIC_OPERATOR_NAME || "Demo operator not configured";
const contactEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "Contact email not configured";

export default function TermsPage() {
  return (
    <main className="page container prose">
      <p className="eyebrow">Legal</p>
      <h1>Terms &amp; Conditions</h1>
      <p>Last updated: 11 November 2026</p>

      <h2>1. About this demonstration</h2>
      <p>
        CompatFlow is an early-stage product demonstration operated by
        {` ${operatorName}`}. Features may be incomplete, changed or unavailable.
        The demo is not a production catalog-management service.
      </p>

      <h2>2. Permitted use</h2>
      <p>
        You must use the demo lawfully and must not attempt to disrupt the
        service, upload malicious files or access data that does not belong
        to you.
      </p>

      <h2>3. Sample data and outputs</h2>
      <p>
        Sample data, validation results and workflow outputs are illustrative.
        You must independently verify product specifications and compatibility
        before making commercial, safety-related or purchasing decisions.
      </p>

      <h2>4. No production data</h2>
      <p>
        Do not upload confidential supplier files, personal information,
        credentials or real customer catalog data. The public demo only
        validates uploaded CSV files; it does not save files or import products.
      </p>

      <h2>5. Intellectual property</h2>
      <p>
        The software, branding and original materials are protected by
        applicable intellectual property laws. No rights are granted except
        the limited right to access the demonstration.
      </p>

      <h2>6. Availability and disclaimers</h2>
      <p>
        The demo is provided on an as-available basis without a promise of
        uninterrupted operation, accuracy or fitness for a particular purpose.
      </p>

      <h2>7. Changes and contact</h2>
      <p>
        These terms may be updated as the service develops. Contact {contactEmail}.
      </p>

      <p><Link href="/">Return to home</Link></p>
    </main>
  );
}
