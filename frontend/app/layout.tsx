import type { Metadata } from "next";

import "./globals.css";
import React from "react";

export const metadata: Metadata = {
  title: "NexusForge AI | Autonomous AI Engineering OS",
  description: "Upload any codebase. Watch 6 AI agents understand, review, debug, document, and scale it — live.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased min-h-screen flex flex-col">
        {children}
      </body>
    </html>
  );
}
