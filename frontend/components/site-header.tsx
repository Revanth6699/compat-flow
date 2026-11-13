import Link from "next/link";
export function SiteHeader() {
 return <header className="site-header"><div className="container header-inner">
  <Link className="brand" href="/" aria-label="CompatFlow home">compat<span className="brand-mark">flow</span></Link>
  <nav className="nav" aria-label="Main navigation">
   <Link href="/">Home</Link>
   <Link href="/#capabilities">Capabilities</Link>
   <Link href="/#workflow">How it works</Link>
   <Link href="/pricing">Pricing</Link>
   <Link href="/contact?intent=demo">Request demo</Link>
   <Link href="/sign-in">Sign in</Link>
   <Link className="nav-get-started" href="/sign-up">Create account</Link>
  </nav>
 </div></header>;
}