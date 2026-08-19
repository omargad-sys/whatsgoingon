import type { ReactNode } from "react";
import type { Metadata, Viewport } from "next";
import "./globals.css";

import manifest from "@/public/data/manifest.json";

const SITE = "https://www.whatsgoingon.vip";

const TITLE = "What's Going On — conflict risk analyzer";
const DESCRIPTION =
  "Political violence data from ACLED, chained through an escalation forecast and " +
  "a market sensitivity model to a portfolio of index and sector ETFs. Nothing is " +
  "shown unless it clears a significance gate.";

export const metadata: Metadata = {
  // Required for the relative openGraph image path below to resolve to an
  // absolute URL. Without it, previews silently fall back to no image.
  metadataBase: new URL(SITE),
  title: TITLE,
  description: DESCRIPTION,
  applicationName: "What's Going On",
  authors: [{ name: "Omar Gad" }],
  keywords: [
    "ACLED",
    "conflict data",
    "political violence",
    "portfolio risk",
    "ETF",
    "escalation forecast",
  ],
  openGraph: {
    type: "website",
    url: SITE,
    siteName: "What's Going On",
    title: TITLE,
    description: DESCRIPTION,
    images: [
      {
        // Regenerated from the real artifacts by research/build_og.py on every
        // refresh, and stamped SYNTHETIC when the build is fixture data, so the
        // preview can never overstate what the site is showing.
        url: "/og.png",
        width: 1200,
        height: 630,
        alt: "World map of recorded conflict events with the project's headline counts",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
    images: ["/og.png"],
  },
  robots: {
    // Synthetic builds should not be indexed. A search result promising conflict
    // forecasts that resolves to fixture data is worse than no result.
    index: !manifest.synthetic,
    follow: true,
  },
};

export const viewport: Viewport = {
  themeColor: "#0d0d0d",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" data-theme="dark">
      <body>{children}</body>
    </html>
  );
}
