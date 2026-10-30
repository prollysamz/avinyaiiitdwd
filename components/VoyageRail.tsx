"use client";

import { useEffect, useState } from "react";
import styles from "./VoyageRail.module.css";

const STOPS = [
  { id: "islands", label: "The Last Outpost", day: "Day 1" },
  { id: "pandemonium", label: "The Pandemonium", day: "Day 2" },
  { id: "carnival", label: "The Carnival Island", day: "Day 3" },
  { id: "hack", label: "Hack2Future", day: "Orbit" },
] as const;

/** Where you are on the voyage, and a way to jump to any stop. Shown only while the 3D chapters are on screen. */
export default function VoyageRail() {
  const [active, setActive] = useState<string | null>(null);
  const [show, setShow] = useState(false);

  useEffect(() => {
    const first = document.getElementById("islands");
    const end = document.getElementById("events");
    const upd = () => {
      if (!first || !end) return;
      const mid = window.innerHeight * 0.5;
      // viewport-relative, so it doesn't matter which ancestor is the offsetParent
      setShow(first.getBoundingClientRect().top < mid + window.innerHeight * 0.6 && end.getBoundingClientRect().top > mid);
      // the current stop is the last chapter whose top has passed the middle of the screen
      let current: string | null = null;
      for (const s of STOPS) {
        const el = document.getElementById(s.id);
        if (el && el.getBoundingClientRect().top <= mid) current = s.id;
      }
      setActive(current);
    };
    upd();
    window.addEventListener("scroll", upd, { passive: true });
    window.addEventListener("resize", upd);
    return () => { window.removeEventListener("scroll", upd); window.removeEventListener("resize", upd); };
  }, []);

  return (
    <nav className={styles.rail} data-show={show} aria-label="Voyage stops">
      <ol>
        {STOPS.map((s) => (
          <li key={s.id}>
            <a href={`#${s.id}`} aria-current={active === s.id ? "location" : undefined} tabIndex={show ? 0 : -1}>
              <span className={styles.label}><b>{s.day}</b> {s.label}</span>
              <span className={styles.dot} aria-hidden="true" />
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
