import type { Metadata } from "next";
import { Bodoni_Moda, DM_Sans, JetBrains_Mono, Orbitron, Chakra_Petch, Rye } from "next/font/google";
import "./globals.css";

const display = Bodoni_Moda({ subsets: ["latin"], variable: "--font-display" });
const sans = DM_Sans({ subsets: ["latin"], variable: "--font-sans" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

const orbit = Orbitron({ subsets: ["latin"], variable: "--font-orbit" });
const cyber = Chakra_Petch({ subsets: ["latin"], weight: ["500", "700"], variable: "--font-cyber" });
const carnival = Rye({ subsets: ["latin"], weight: "400", variable: "--font-carnival" });

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
