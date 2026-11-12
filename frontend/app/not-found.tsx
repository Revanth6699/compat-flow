
import Link from "next/link";

export default function NotFound() {
  return (
    <main className="page container">
      <p className="eyebrow">404 &middot; Page not found</p>
      <h1>This page doesn&apos;t exist.</h1>
      <p>
        The link may be outdated or the address may have been entered incorrectly.
      </p>
      <Link className="button" href="/">
        Return to CompatFlow
      </Link>
    </main>
  );
}
