import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { CookieConsent } from "@/components/cookie-consent";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { AuthProvider } from "@/components/auth-provider";

const inter = Inter({ subsets: ["latin"], display: "swap", variable: "--font-inter" });

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
      <body className={inter.variable}>
        <AuthProvider>
        <a className="skip-link" href="#main">Skip to content</a>
        <SiteHeader />
        {children}
        <SiteFooter />
        <CookieConsent />
        </AuthProvider>
      </body>
    </html>
  );
}
