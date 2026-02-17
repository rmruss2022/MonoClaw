import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0a0a0f",
};

export const metadata: Metadata = {
  title: "Matthew Russell - Full-Stack Engineer | AI & Systems Architecture",
  description:
    "Full-stack engineer specializing in AI automation, systems architecture, and scalable infrastructure. Built Rust analytics engines, React data visualizations, and OpenClaw plugins. Previously at AgriVaR, BitWave, Liquid IV.",
  keywords: [
    "Matthew Russell",
    "Full-Stack Engineer",
    "AI Automation",
    "Systems Architecture",
    "OpenClaw",
    "React",
    "TypeScript",
    "Rust",
  ],
  authors: [{ name: "Matthew Russell" }],
  openGraph: {
    title: "Matthew Russell - Full-Stack Engineer",
    description:
      "Building AI-powered systems and automation tools that multiply human capability",
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "Matthew Russell - Full-Stack Engineer",
    description:
      "Building AI-powered systems and automation tools that multiply human capability",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="scroll-smooth">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased scanline`}
      >
        {children}
      </body>
    </html>
  );
}
