import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "O2C Context Graph",
  description: "SAP Order-to-Cash context graph with AI-powered analytics",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased">{children}</body>
    </html>
  );
}
