"use client";

import Link from "next/link";
import { useAuth } from "@/components/auth-provider";
export function SiteFooter() {
 const { user } = useAuth();
 return <footer className="site-footer"><div className="container footer">
  <div className="footer-brand">
   <Link className="footer-brand-name" href="/">compatflow</Link>
   <span>Supplier catalog operations</span>
   <p className="footer-summary">A product in development focused on helping commerce teams work with more consistent supplier catalog data.</p>
  </div>
  <div className="footer-column"><strong>Explore</strong><div className="footer-links">
   {!user && <Link href="/contact?intent=demo">Request a demo</Link>}<Link href="/pricing">Pricing</Link><Link href="/about">About Us</Link>{!user && <Link href="/reviews">Customer reviews</Link>}
  </div></div>
  <div className="footer-column"><strong>Information</strong><div className="footer-links">
   <Link href="/contact">Contact Us</Link><Link href="/privacy">Privacy Notice</Link><Link href="/privacy/requests">Data rights request</Link><Link href="/terms">Terms &amp; Conditions</Link><Link href="/help/account">Account help</Link><Link href="/privacy#grievance">Grievance contact</Link><button type="button" onClick={() => window.dispatchEvent(new Event("compatflow:manage-privacy"))}>Manage privacy preferences</button>
  </div></div>
  <span className="footer-copyright">© {new Date().getFullYear()} CompatFlow</span>
 </div></footer>;
}