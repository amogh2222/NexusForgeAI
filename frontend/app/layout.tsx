import type { Metadata, Viewport } from "next";
import "./globals.css";
import React from "react";

export const metadata: Metadata = {
  title: "NexusForge AI | Autonomous AI Engineering OS",
  description: "Upload any codebase. Watch 6 AI agents understand, review, debug, document, and scale it — live.",
  icons: {
    icon: "/favicon.svg",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#fffcf8",
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen flex flex-col selection:bg-orange-500/20 selection:text-orange-900">
        {children}
      </body>
    </html>
  );
}
