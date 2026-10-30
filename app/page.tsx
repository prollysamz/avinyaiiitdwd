"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import About from "@/components/About";
import ChapterEvents from "@/components/ChapterEvents";
import Crossing, { accentClass } from "@/components/Crossing";
import Itinerary from "@/components/Itinerary";
import VoyageRail from "@/components/VoyageRail";
import { DAYS, FEST_START, HACK2FUTURE_URL, VENUE, eventsForDay } from "@/data/events";

const VoyageWorld = dynamic(() => import("@/components/VoyageWorld"), { ssr: false });
const CHAPTER_IDS = ["islands", "pandemonium", "carnival"] as const;

function Countdown() {
  const [left, setLeft] = useState<number | null>(null);
  useEffect(() => {
    const tick = () => setLeft(Math.max(0, FEST_START - Date.now()));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, []);
  const t = left ?? 0;
  const parts: [number, string][] = [[Math.floor(t / 864e5), "days"], [Math.floor(t / 36e5) % 24, "hours"], [Math.floor(t / 6e4) % 60, "minutes"]];
  return <div className="countdown" aria-label="Time until Avinya 2027 begins">{parts.map(([value, unit]) => <span key={unit}><strong>{left === null ? "—" : String(value).padStart(2, "0")}</strong><small>{unit}</small></span>)}</div>;
}

function Header() {
  return <header className="site-header">
    <a href="#top" className="wordmark" aria-label="Avinya 2027 home">Avinya<span>2027</span></a>
    <nav aria-label="Main navigation"><a href="#voyage">About</a><a href="#islands">Islands</a><a href="#hack">Hack2Future</a></nav>
    <a href="#events" className="button button-small header-cta">Explore events</a>
  </header>;
}

function Hero() {
  return <section id="top" className="hero">
    <div className="hero-shade" />
    <div className="hero-content">
      <p className="eyebrow">IIIT Dharwad · 12–14 March 2027</p>
      <h1>Avinya<span className="hero-year">2027</span></h1>
      <p className="hero-description">Three days of technology,<br className="desktop-break" /> culture and creativity.</p>
      <p className="hero-intro">Explore IIIT Dharwad’s techno-cultural festival, from the Last Outpost to Carnival Island, with Hack2Future along the way.</p>
      <div className="actions"><a href="#events" className="button">Explore events</a><a href="#voyage" className="text-link">About the festival</a></div>
    </div>
    <div className="hero-bottom"><p>12–14 March 2027<br /><span>IIIT Dharwad, Karnataka</span></p><div><p className="countdown-label">The festival begins in</p><Countdown /></div></div>
  </section>;
}

const VOICES = ["outpost", "pandemonium", "carnival"] as const;

function DayCrossing({ index }: { index: 0 | 1 | 2 }) {
  const day = DAYS[index];
  return <Crossing voice={VOICES[index]} destination={day.name} when={`Day ${day.day} · ${day.date.replace(" 2027", "")}`} line={day.theme} />;
}

function IslandChapter({ index }: { index: 0 | 1 | 2 }) {
  const day = DAYS[index];
  return <section id={CHAPTER_IDS[index]} className={`island ${["outpost", "pandemonium", "carnival"][index]}`} aria-labelledby={`chapter-${day.day}-title`}>
    <div className="island-scene"><div className="chapter-shade" /><article className="chapter-card">
      <div className="chapter-meta"><span>Day {day.day}</span><time dateTime={`2027-03-${11 + day.day}`}>{day.date}</time></div>
      <h2 id={`chapter-${day.day}-title`} className="island-title">{day.name}</h2>
      <p className="chapter-description">{day.blurb}</p><ChapterEvents day={day.day} />
      <a href={index < 2 ? `#${CHAPTER_IDS[index + 1]}` : "#hack"} className={`chapter-next to-${index < 2 ? VOICES[index + 1] : "orbit"}`}><span><small>{index < 2 ? "Next island" : "Next"}</small>{index < 2 ? DAYS[index + 1].name : "Hack2Future"}</span></a>
    </article></div>
  </section>;
}

function Hack2Future() {
  return <section id="hack" className="hack" aria-labelledby="hack-title"><div className="hack-scene"><div className="hack-shade" /><article className="hack-card">
    <p className="eyebrow hack-badge">National-level hackathon</p><h2 id="hack-title"><span>Hack</span><span className="hack-title-bottom">2<span>Future</span></span></h2><p className="hack-lead">Build for what comes next.</p>
    <p>Work on real problems with your team, supported by mentors and industry experts, through the three days of Avinya 2027.</p>
    <dl className="hack-details"><div><dt>When</dt><dd>12–14 March 2027</dd></div><div><dt>Where</dt><dd>IIIT Dharwad campus</dd></div></dl>
    <div className="actions"><a href={HACK2FUTURE_URL} target="_blank" rel="noopener noreferrer" className="button">Visit Hack2Future</a><a href="#events" className="text-link">Browse festival events</a></div>
  </article></div></section>;
}

function Footer() {
  return <footer className="site-footer"><div className="section-container"><div><a href="#top" className="footer-brand">Avinya 2027</a><p>12–14 March · IIIT Dharwad</p><address>{VENUE}</address></div><nav aria-label="Footer navigation"><a href="#voyage">About the festival</a><a href="#events">Event preview</a><a href={HACK2FUTURE_URL} target="_blank" rel="noopener noreferrer">Hack2Future</a><a href="#top">Back to top</a></nav></div></footer>;
}

export default function Home() {
  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);
    // Native scrolling preserves wheel, touch, keyboard, hash links and history.
    const progress = ScrollTrigger.create({ start: 0, end: "max", onUpdate: self => {
      window.__voyageProgress = self.progress;
      window.__voyageVelocity = self.getVelocity();
    } });
    const refresh = () => ScrollTrigger.refresh();
    document.fonts.ready.then(refresh);
    refresh();

    // The reading shade is a fixed layer whose strength follows how far each chapter is on screen,
    // so it eases in as the boat arrives and out as it leaves, with no panel edge ever visible.
    const shades = Array.from(document.querySelectorAll<HTMLElement>(".island, .hack")).map((section) => ({ section, shade: section.querySelector<HTMLElement>(".chapter-shade, .hack-shade")! }));
    const ease = (a: number, b: number, x: number) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
    const header = document.querySelector<HTMLElement>(".site-header");
    let lastY = window.scrollY;
    let raf = 0;
    const paint = () => {
      raf = 0;
      const y = window.scrollY;
      // Ignore tiny jitters; near the top the header always shows.
      if (Math.abs(y - lastY) > 6) { header?.classList.toggle("is-hidden", y > lastY && y > 120); lastY = y; }
      if (y <= 120) header?.classList.remove("is-hidden");
      const vh = window.innerHeight;
      for (const { section, shade } of shades) {
        const r = section.getBoundingClientRect();
        shade.style.setProperty("--k", Math.min(ease(vh * 0.95, vh * 0.2, r.top), ease(vh * 0.05, vh * 0.8, r.bottom)).toFixed(3));
      }
    };
    const queue = () => { if (!raf) raf = requestAnimationFrame(paint); };
    paint();
    window.addEventListener("scroll", queue, { passive: true });
    window.addEventListener("resize", queue);
    return () => { progress.kill(); cancelAnimationFrame(raf); window.removeEventListener("scroll", queue); window.removeEventListener("resize", queue); };
  }, []);
  return <main><a href="#events" className="skip-link">Skip to events</a><VoyageWorld /><div className="page-content"><Header /><VoyageRail /><Hero /><About />
    <DayCrossing index={0} /><IslandChapter index={0} />
    <DayCrossing index={1} /><IslandChapter index={1} />
    <DayCrossing index={2} /><IslandChapter index={2} />
    <Crossing voice="orbit" destination="Hack2Future" title={<>Hack<span className={accentClass}>2</span>Future</>} when="12–14 March · IIIT Dharwad" line="Leaving the water behind, for orbit." />
    <Hack2Future /><Itinerary /><Footer /></div></main>;
}
