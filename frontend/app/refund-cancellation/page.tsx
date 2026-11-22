import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Refund & Cancellation Policy",
  description: "How to cancel a CompatFlow subscription and request a refund.",
};

const contactEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "sarvasettyrevanth.66@gmail.com";
const operatorName = process.env.NEXT_PUBLIC_OPERATOR_NAME || "Individual proprietor trading as CompatFlow";
const grievanceContact = process.env.NEXT_PUBLIC_GRIEVANCE_CONTACT || "Proprietor, CompatFlow (name and designation to be published)";
const businessAddress = process.env.NEXT_PUBLIC_OPERATOR_ADDRESS || "Business address pending publication";

export default function RefundCancellationPage() {
  return (
    <main id="main" className="legal-page">
      <div className="container legal-container">
        <header className="legal-hero"><span className="eyebrow">LEGAL / BILLING</span><h1>Refund &amp; Cancellation Policy</h1><p>This policy explains how subscription renewals are stopped and how payment issues and refund requests are handled.</p><span className="legal-updated">Effective date: 22 November 2026</span></header>
        <div className="legal-layout">
          <aside className="legal-aside"><span>ON THIS PAGE</span><a href="#cancellation">Cancel a subscription</a><a href="#effect">When cancellation takes effect</a><a href="#refunds">Refund eligibility</a><a href="#processing">Refund processing</a><a href="#exceptions">Exceptions and disputes</a><a href="#contact">Request help</a></aside>
          <article className="legal-content">
            <section id="cancellation"><h2>1. How to cancel</h2><p>The organization administrator who manages the subscription may request cancellation through the billing area when that option is available. If the cancellation control is not available, email <a href={`mailto:${contactEmail}`}>{contactEmail}</a> from the account’s registered email address with the organization name and subscription reference. Do not include card numbers, CVV, UPI PINs or passwords.</p><p>Submit a cancellation request at least 24 hours before the displayed renewal time to allow the request to be reviewed before the next billing attempt. A request is not complete until you receive confirmation that the subscription has been cancelled or scheduled for cancellation.</p></section>
            <section id="effect"><h2>2. When cancellation takes effect</h2><p>Unless the cancellation confirmation expressly states that cancellation is immediate, cancellation stops the next renewal and your paid access continues until the end of the current paid billing period. No further recurring charge should be made after the cancellation has taken effect. If a renewal payment has already been initiated or processed before the cancellation is confirmed, contact us promptly so we can review it.</p><p>Cancellation does not automatically delete your CompatFlow account or organization data. Account deletion is a separate action and may be requested through account settings. Records that must be retained for legal, security, accounting or dispute-resolution purposes may be retained as described in the Privacy Policy.</p></section>
            <section id="refunds"><h2>3. Refund eligibility</h2><p>Subscription fees are generally non-refundable once a billing period has started, and we do not automatically provide partial or prorated refunds for unused time, a change of mind, reduced usage, failure to cancel before renewal, or removal of a member from an organization.</p><p>We will review refund requests where there is a duplicate charge, an incorrect amount charged by us, a payment collected after a confirmed cancellation, a verified payment-provider error, or a material failure to activate the paid subscription after successful payment that we cannot reasonably resolve. Refunds may also be issued where required by applicable law or where we approve an exception.</p><p>For a billing issue, contact us as soon as possible and ideally within 7 days of the transaction. This request window does not reduce any mandatory right or remedy available under applicable law.</p></section>
            <section id="processing"><h2>4. Refund review and processing</h2><p>We may ask for the transaction ID, subscription ID, payment date, amount and a short description of the issue to verify a request. Never send full card details, CVV, UPI PINs, passwords or one-time passcodes.</p><p>If a refund is approved, it will normally be initiated through the original payment method or payment provider, subject to provider and banking timelines. The time taken for the credit to appear depends on the payment provider and the customer’s bank. We will share the available refund reference or status when provided by the payment provider. A refund does not automatically reinstate a cancelled subscription.</p></section>
            <section id="exceptions"><h2>5. Payment disputes and statutory rights</h2><p>If you do not recognize a payment, contact us and your bank or payment provider promptly. We may temporarily restrict access while investigating suspected fraud, chargebacks or payment reversals. Nothing in this policy excludes consumer rights, remedies or refund obligations that cannot lawfully be excluded.</p></section>
            <section id="contact"><h2>6. Contact and grievance redressal</h2><p>Email <a href={`mailto:${contactEmail}`}>{contactEmail}</a> with the subject “Cancellation Request” or “Refund Request”. Include your account email, organization name and relevant payment or subscription reference. We aim to acknowledge complaints within 48 hours and resolve them within 30 days, subject to applicable law and the time required by the payment provider.</p><p>Operator and grievance contact: {grievanceContact}. Business address: {businessAddress}. The business address must be completed before live commercial launch.</p></section>
          </article>
        </div>
      </div>
    </main>
  );
}
