import type { Metadata } from "next";
import { Barlow, Barlow_Condensed } from "next/font/google";
import "./globals.css";

const body = Barlow({ variable: "--font-body", subsets: ["latin"], weight: ["400", "500", "600"] });
const display = Barlow_Condensed({ variable: "--font-display", subsets: ["latin"], weight: ["700"] });

export const metadata: Metadata = {
  title: "Haggle",
  description: "AI agents haggle over a price, live.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${body.variable} ${display.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
