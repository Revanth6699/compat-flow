"use client";

import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/components/auth-provider";
import { RequestDemoLink } from "@/components/request-demo-link";

export function SiteFooter() {
  const { user } = useAuth();
  return <footer className="site-footer editorial-footer">
    <div className="footer-inner">
      <div className="footer-capsule">
        <Link href="/" className="footer-capsule-brand" aria-label="CompatFlow home"><Image src="/compatflow-logo.svg" alt="CompatFlow" width={34} height={34}/></Link>
        <nav aria-label="Footer quick navigation"><Link href="/#capabilities">Capabilities</Link><Link href="/#workflow">How it works</Link><Link href="/pricing">Pricing</Link><Link href="/about">About</Link><Link href="/contact">Contact</Link></nav>
        <Link className="footer-capsule-cta" href={user ? "/workspace" : "/contact?intent=demo"}>{user ? "Open workspace" : "Request a demo"} ↗</Link>
      </div>
      <div className="footer-monogram"><Image src="/compatflow-logo.svg" alt="CompatFlow" width={112} height={112}/><p>Clearer supplier data. More controlled catalog workflows.</p></div>
      <div className="footer-columns">
        <div><strong>Product</strong><Link href="/workspace">Workspace</Link><Link href="/catalog/import">Catalog import</Link><Link href="/catalog/sources">Data sources</Link><Link href="/catalog/validations">Validation</Link></div>
        <div><strong>Explore</strong><Link href="/pricing">Plans & pricing</Link><Link href="/about">About CompatFlow</Link>{!user && <Link href="/reviews">Customer reviews</Link>}<RequestDemoLink /></div>
        <div><strong>Support</strong><Link href="/contact">Contact us</Link><Link href="/help/account">Account help</Link><Link href="/settings">Profile & settings</Link></div>
        <div><strong>Legal</strong><Link href="/privacy">Privacy policy</Link><Link href="/terms">Terms & conditions</Link><Link href="/refund-cancellation">Refund & cancellation</Link></div>
      </div>
      <div className="footer-bottom"><span>© {new Date().getFullYear()} CompatFlow. All rights reserved.</span><span>Supplier catalog change operations</span></div>
    </div>
  </footer>;
}
