import type { Metadata, Viewport } from "next";
import "./globals.css";
import { CookieConsent } from "@/components/cookie-consent";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "CompatFlow — Supplier Catalog Change Operations",
    template: "%s | CompatFlow",
  },
  description:
    "Import, normalize, reconcile and prepare supplier catalog changes for ecommerce product data workflows.",
  applicationName: "CompatFlow",
  openGraph: {
    type: "website",
    siteName: "CompatFlow",
    title: "CompatFlow — Supplier Catalog Change Operations",
    description: "Keep supplier-driven product catalog changes organized and controlled.",
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "CompatFlow supplier catalog operations" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "CompatFlow — Supplier Catalog Change Operations",
    description: "Import, reconcile and prepare supplier catalog changes.",
    images: ["/opengraph-image"],
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f7f8fa",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">Skip to content</a>
        {children}
        <CookieConsent />
      </body>
    </html>
  );
}
