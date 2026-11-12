import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "CompatFlow public demonstration privacy policy.",
};

const operatorName = process.env.NEXT_PUBLIC_OPERATOR_NAME || "Demo operator not configured";
const contactEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "Contact email not configured";

export default function PrivacyPage() {
  return (
    <main className="page container prose">
      <p className="eyebrow">Legal</p>
      <h1>Privacy Policy</h1>
      <p>Last updated: 11 November 2026</p>

      <h2>1. Who operates CompatFlow</h2>
      <p>
        CompatFlow is operated by {operatorName}. For privacy questions, contact{" "}
        {contactEmail}.
      </p>

      <h2>2. Information processed</h2>
      <p>
        When you use the public CSV validator, the CSV file you select is sent
        to the CompatFlow API for validation. The application processes the
        file in memory and does not save the uploaded file or persist catalog
        records. The website may also process basic technical request
        information, such as IP address, browser details and service logs,
        through its hosting and infrastructure providers.
      </p>

      <h2>3. Purposes</h2>
      <p>
        Information is processed to provide the demonstration, respond to
        messages, maintain service security and troubleshoot reliability.
        Do not upload personal information, confidential supplier files,
        credentials or production catalog data.
      </p>

      <h2>4. Cookies and local storage</h2>
      <p>
        The demonstration stores your cookie preference in your browser&apos;s
        local storage. No analytics or advertising tracking scripts are
        intentionally loaded by this application.
      </p>

      <h2>5. Service providers</h2>
      <p>
        The public demonstration is hosted by the providers identified in the
        deployment and infrastructure configuration. Those providers may
        process technical request data to deliver and secure the service.
      </p>

      <h2>6. Retention and security</h2>
      <p>
        Uploaded CSV content is not persisted by the application. Technical
        logs may be retained by infrastructure providers under their own
        retention policies. Reasonable safeguards are applied, but no
        internet service can guarantee absolute security.
      </p>

      <h2>7. Your rights and contact</h2>
      <p>
        Depending on applicable law, you may have rights to access, correct,
        delete or object to certain processing. Contact {contactEmail}.
      </p>

      <h2>8. Changes</h2>
      <p>This policy may be updated as the product and its data practices change.</p>

      <p><Link href="/">Return to home</Link></p>
    </main>
  );
}
