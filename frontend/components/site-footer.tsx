"use client";

import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/components/auth-provider";
import { RequestDemoLink } from "@/components/request-demo-link";
export function SiteFooter() {
 const { user } = useAuth();
 return <footer className="site-footer"><div className="container footer">
  <div className="footer-brand">
   <Link className="footer-logo-link" href="/" aria-label="CompatFlow home"><Image src="/compatflow-logo.svg" alt="CompatFlow" width={90} height={90} /></Link>
   <span>Supplier catalog operations</span>
   <p className="footer-summary">A product in development focused on helping commerce teams work with more consistent supplier catalog data.</p>
  </div>
  <div className="footer-column"><strong>Explore</strong><div className="footer-links">
   {!user && <Link href="/contact?intent=demo">Request a demo</Link>}<RequestDemoLink /> <Link href="/pricing">Pricing</Link><Link href="/about">About Us</Link>{!user && <Link href="/reviews">Customer reviews</Link>}
  </div></div>
  <div className="footer-column"><strong>Information</strong><div className="footer-links">
   <Link href="/contact">Contact Us</Link><Link href="/privacy">Privacy Policy</Link><Link href="/terms">Terms &amp; Conditions</Link><Link href="/refund-cancellation">Refund &amp; Cancellation Policy</Link><Link href="/help/account">Account help</Link>
  </div></div>
  <span className="footer-copyright">© {new Date().getFullYear()} CompatFlow</span>
 </div></footer>;
}
