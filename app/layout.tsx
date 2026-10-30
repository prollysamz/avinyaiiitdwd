import type { Metadata } from "next";
import { Bodoni_Moda, DM_Sans, JetBrains_Mono } from "next/font/google";
import localFont from "next/font/local";
import "./globals.css";

const display = Bodoni_Moda({ subsets: ["latin"], variable: "--font-display" });
const sans = DM_Sans({ subsets: ["latin"], variable: "--font-sans" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

// Keep the island faces in the repository, including Pandemonium's real italic.
// next/font emits and preloads these alongside every deployment's static assets.
const orbit = localFont({
  src: "./fonts/orbitron-latin.woff2", weight: "400 900", style: "normal",
  variable: "--font-orbit", display: "swap", fallback: ["sans-serif"],
});
const cyber = localFont({
  src: [
    { path: "./fonts/chakra-petch-latin-500.woff2", weight: "500", style: "normal" },
    { path: "./fonts/chakra-petch-latin-700.woff2", weight: "700", style: "normal" },
    { path: "./fonts/chakra-petch-700-italic.ttf", weight: "700", style: "italic" },
  ],
  variable: "--font-cyber", display: "swap", fallback: ["sans-serif"],
});
const carnival = localFont({
  src: "./fonts/rye-latin.woff2", weight: "400", style: "normal",
  variable: "--font-carnival", display: "swap", fallback: ["serif"],
});

export const metadata: Metadata = {
  title: "Avinya 2027 · IIIT Dharwad · 12–14 March",
  description: "Explore Avinya 2027, IIIT Dharwad’s techno-cultural festival, from 12 to 14 March. Discover the three island themes, event preview and Hack2Future.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable} ${orbit.variable} ${cyber.variable} ${carnival.variable}`}>
      <body>{children}</body>
    </html>
  );
}
