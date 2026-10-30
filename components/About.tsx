import Image from "next/image";
import { DAYS } from "@/data/events";
import styles from "./About.module.css";

const ISLANDS = [
  { id: "islands", img: "/images/islands/outpost.webp", w: 915, h: 960, alt: "The Last Outpost: a desert fortress with a tall keep, crenellated wall and windtrap tower on a floating rock island" },
  { id: "pandemonium", img: "/images/islands/pandemonium.webp", w: 1157, h: 1100, alt: "The Pandemonium: a dense neon city of lit skyscrapers on a floating rock island" },
  { id: "carnival", img: "/images/islands/carnival.webp", w: 979, h: 990, alt: "The Carnival Island: a Ferris wheel and striped tents on a floating rock island" },
] as const;

export default function About() {
  return (
    <section id="voyage" className={styles.section} aria-labelledby="about-title">
      <div className={styles.wrap}>
        <div className={styles.intro}>
          <h2 id="about-title">A festival across <span className={styles.hot}>three islands.</span></h2>
          <p>Avinya is the techno-cultural fest of IIIT Dharwad. From 12 to 14 March 2027, each day happens on its own island with its own theme, and Hack2Future, the college’s national-level hackathon, runs through the festival.</p>
        </div>
        <ul className={styles.islands}>
          {DAYS.map((day, i) => (
            <li key={day.day} className={styles.island} data-island={i}>
              <a href={`#${ISLANDS[i].id}`} className={styles.card}>
                <span className={styles.sky} aria-hidden="true" />
                <span className={styles.art}>
                  <Image src={ISLANDS[i].img} width={ISLANDS[i].w} height={ISLANDS[i].h} alt={ISLANDS[i].alt} sizes="(max-width: 900px) 90vw, 32vw" />
                </span>
                <span className={styles.text}>
                  <span className={styles.when}>Day {day.day}<i>{day.date.replace(" 2027", "")}</i></span>
                  <span className={styles.name}>{day.name}</span>
                  <span className={styles.theme}>{day.theme}</span>
                  <span className={styles.blurb}>{day.blurb}</span>
                </span>
              </a>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
