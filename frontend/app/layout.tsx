import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aarogya One Connect",
  description: "Clinic voice-to-prescription and records for Aarogya One Connect",
  robots: { index: false, follow: false },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased font-sans">{children}</body>
    </html>
  );
}
