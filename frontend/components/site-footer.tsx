"use client";\n\nimport Link from "next/link";\nimport { useAuth } from "@/components/auth-provider";
export function SiteFooter() {
 return <footer className="site-footer"><div className="container footer">
  <div className="footer-brand">
   <Link className="footer-brand-name" href="/">compatflow</Link>
   <span>Supplier catalog operations</span>
   <p className="footer-summary">A product in development focused on helping commerce teams work with more consistent supplier catalog data.</p>
  </div>
  <div className="footer-column"><strong>Explore</strong><div className="footer-links">
   {!user && <Link href="/contact?intent=demo">Request a demo</Link>}<Link href="/pricing">Pricing</Link><Link href="/about">About Us</Link><Link href="/reviews">Customer reviews</Link>{user && <Link href="/reviews/write">Write a review</Link>}
  </div></div>
  <div className="footer-column"><strong>Information</strong><div className="footer-links">
   <Link href="/contact">Contact Us</Link><Link href="/privacy">Privacy Policy</Link><Link href="/terms">Terms &amp; Conditions</Link><Link href="/help/account">Account help</Link>
  </div></div>
  <span className="footer-copyright">© {new Date().getFullYear()} CompatFlow</span>
 </div></footer>;
}