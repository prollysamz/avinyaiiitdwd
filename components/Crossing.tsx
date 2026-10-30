import type { ReactNode } from "react";
import styles from "./Crossing.module.css";

export const accentClass = styles.accent;
export type Voice = "outpost" | "pandemonium" | "carnival" | "orbit";

/**
 * The stretch of open water between two chapters. It names where the boat is heading and when it arrives,
 * in the destination's own title style, so the island's identity shows up before the island does.
 * `data-crossing` is also what the 3D camera rig measures to time the sail between poses.
 */
export default function Crossing({ voice, destination, title, when, line }: { voice: Voice; destination: string; title?: ReactNode; when: string; line: string }) {
  return (
    <section className={styles.crossing} data-crossing={voice} data-voice={voice} aria-label={`Sailing to ${destination}`}>
      <div className={styles.stage}>
        <div className={styles.sign}>
          <p className={styles.when}>{when}</p>
          <h3 className={styles.title}>{title ?? destination}</h3>
          <p className={styles.line}>{line}</p>
        </div>
      </div>
    </section>
  );
}
