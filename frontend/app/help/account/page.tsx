import Link from "next/link";
import type { Metadata } from "next";
export const metadata: Metadata = { title: "Account help", description: "How to create a CompatFlow account, verify your email and access an organization workspace." };
export default function AccountHelpPage() {
 return <main id="main" className="legal-page"><div className="container legal-container">
  <header className="legal-hero"><span className="eyebrow">HELP / ACCOUNTS</span><h1>Account and workspace access</h1><p>What to expect when creating a CompatFlow account and joining an organization.</p></header>
  <article className="legal-content account-help-content">
   <section><h2>1. Create an account</h2><p>Use your work email and a unique password of at least 10 characters on the <Link href="/sign-up">Create account</Link> page. If email confirmation is enabled, open the confirmation message and follow its link in the same browser profile where you started registration.</p></section>
   <section><h2>2. Verify your email and sign in</h2><p>After confirming your email, go to <Link href="/sign-in">Sign in</Link>. If you cannot access your account, use the <Link href="/forgot-password">password reset</Link> flow. Never share your password or verification links with another person.</p></section>
   <section><h2>3. Understand organization access</h2><p>Creating a login identity does not automatically create an organization, assign an organization role or grant access to a workspace. The first organization owner must be provisioned by an authorized operator. Other users must receive and accept an invitation using the email address associated with their account.</p></section>
   <section><h2>4. Accept an invitation</h2><p>Open the invitation link, sign in or create an account with the invited email address, then accept the invitation. Invitation links are credentials: keep them private and contact the inviter if a link expires or was sent to the wrong address.</p></section>
   <section><h2>5. Manage your account</h2><p>After signing in, open <Link href="/settings">Profile settings</Link> to update your display name, change your password or sign out. Your account email is currently read-only in the self-service settings page.</p></section>
   <section><h2>6. Privacy and support</h2><p>Read the <Link href="/privacy">Privacy Policy</Link> to understand account, invitation, technical and demonstration data processing. For help with organization membership or account access, contact the person who invited you or use the <Link href="/contact">Contact page</Link>.</p></section>
  </article>
 </div></main>;
}