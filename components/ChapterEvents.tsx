import { eventsForDay } from "@/data/events";
import { slotOf } from "@/lib/plan";
import styles from "./ChapterEvents.module.css";

const TYPE_LABEL = { TECH: "Tech", CULTURAL: "Cultural", DESIGN: "Design" } as const;

/** The day's lineup, shown inside its chapter. Large enough to read against the 3D scene. */
export default function ChapterEvents({ day }: { day: 1 | 2 | 3 }) {
  const slots = eventsForDay(day).map((e) => slotOf(e)).sort((a, b) => a.start - b.start);
  return (
    <div className={styles.events}>
      <h3>On day {day}</h3>
      <ul>
        {slots.map((s) => (
          <li key={s.event.id}>
            <time>{s.time}</time>
            <span className={styles.name}>{s.event.title}</span>
            <span className={styles.type}>{TYPE_LABEL[s.event.type]}</span>
          </li>
        ))}
      </ul>
      <a href="#events" className={styles.plan}>Add these to your plan</a>
    </div>
  );
}
