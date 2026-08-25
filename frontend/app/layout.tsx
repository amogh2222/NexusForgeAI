import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "NexusForge AI",
  description: "Autonomous AI Engineering Operating System",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  );
}
