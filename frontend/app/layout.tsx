import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Melo AI — Song Recommendations",
  description:
    "Find songs that sound like the ones you love. Melo AI uses audio features and a KNN model trained on 250k tracks.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="font-display antialiased">{children}</body>
    </html>
  );
}
