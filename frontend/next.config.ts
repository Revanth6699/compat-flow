import type { NextConfig } from "next";

if (process.env.VERCEL === "1" || process.env.COMPATFLOW_PUBLIC_BUILD === "1") {
  const apiUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "";
  const contactEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "";
  const operatorName = process.env.NEXT_PUBLIC_OPERATOR_NAME || "";
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "";

  if (!apiUrl.startsWith("https://")) {
    throw new Error("Set NEXT_PUBLIC_API_BASE_URL to the public HTTPS API URL before building for production.");
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contactEmail)) {
    throw new Error("Set NEXT_PUBLIC_CONTACT_EMAIL to a real monitored contact email before building for production.");
  }
  if (operatorName.trim().length < 2) {
    throw new Error("Set NEXT_PUBLIC_OPERATOR_NAME to the legal/operator name before building for production.");
  }
  if (!siteUrl.startsWith("https://")) {
    throw new Error("Set NEXT_PUBLIC_SITE_URL to the public HTTPS website URL before building for production.");
  }
}

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
