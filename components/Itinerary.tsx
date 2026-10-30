"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DAYS, EVENTS, VENUE, type EventType } from "@/data/events";
import { buildIcs, conflictsFor, groupByDay, planText, slotOf } from "@/lib/plan";
import styles from "./Itinerary.module.css";

const STORAGE_KEY = "avinya27.plan.v1";
const SLOTS = EVENTS.map((e) => slotOf(e));
const BY_ID = new Map(SLOTS.map((s) => [s.event.id, s]));
const TYPES: { id: EventType; label: string }[] = [{ id: "TECH", label: "Tech" }, { id: "CULTURAL", label: "Cultural" }, { id: "DESIGN", label: "Design" }];
const DAY_NAMES = DAYS.map((d) => d.name);
const DAY_DATES = DAYS.map((d) => d.date);

function Check() {
  return <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M3 8.5 6.5 12 13 4.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square" /></svg>;
}

function loadPlan(): string[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const ids = raw ? (JSON.parse(raw) as unknown) : [];
    return Array.isArray(ids) ? ids.filter((id): id is string => typeof id === "string" && BY_ID.has(id)) : [];
  } catch {
    return [];
  }
}

export default function Itinerary() {
  const [day, setDay] = useState<0 | 1 | 2 | 3>(0);
  const [types, setTypes] = useState<EventType[]>([]);
  const [plan, setPlan] = useState<string[]>([]);
  const [ready, setReady] = useState(false);
  const [note, setNote] = useState("");
  const noteTimer = useRef<number | undefined>(undefined);

  // The plan lives on this device only. Read it after mount so the server and client markup match.
  useEffect(() => { setPlan(loadPlan()); setReady(true); }, []);
  useEffect(() => {
    if (!ready) return;
    try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(plan)); } catch { /* private mode: the plan simply won't persist */ }
  }, [plan, ready]);

  const say = useCallback((text: string) => {
    setNote(text);
    window.clearTimeout(noteTimer.current);
    noteTimer.current = window.setTimeout(() => setNote(""), 2600);
  }, []);

  const chosen = useMemo(() => plan.map((id) => BY_ID.get(id)!).filter(Boolean), [plan]);
  const grouped = useMemo(() => groupByDay(chosen), [chosen]);
  const toggle = (id: string) => setPlan((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  const days = day === 0 ? [1, 2, 3] : [day];
  const visible = (d: number) => SLOTS.filter((s) => s.event.day === d && (types.length === 0 || types.includes(s.event.type))).sort((a, b) => a.start - b.start);
  const shown = days.reduce((n, d) => n + visible(d).length, 0);
  const clashCount = chosen.filter((s) => conflictsFor(s, chosen).length > 0).length;

  const download = () => {
    const blob = new Blob([buildIcs(chosen, VENUE)], { type: "text/calendar;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: "my-avinya-2027.ics" });
    document.body.append(a); a.click(); a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    say("Calendar file downloaded.");
  };
  const copy = async () => {
    try { await navigator.clipboard.writeText(planText(chosen, DAY_NAMES, DAY_DATES)); say("Plan copied."); }
    catch { say("Couldn’t copy. Select the text in the plan instead."); }
  };

  return (
    <section id="events" className={styles.section} aria-labelledby="planner-title">
      <div className={styles.wrap}>
        <header className={styles.head}>
          <div>
            <h2 id="planner-title" className={styles.title}>Build your<br />three days.</h2>
          </div>
          <p className={styles.preview}><strong>{EVENTS.length} events</strong> in the current preview. Times may change once the organisers confirm the programme.</p>
        </header>

        <div className={styles.filters}>
          <div role="group" aria-label="Show day" className={styles.segment}>
            {([[0, "All days"], [1, "Day 1"], [2, "Day 2"], [3, "Day 3"]] as const).map(([v, label]) => (
              <button key={v} type="button" aria-pressed={day === v} onClick={() => setDay(v)}>{label}</button>
            ))}
          </div>
          <div role="group" aria-label="Event type" className={styles.chips}>
            {TYPES.map((t) => (
              <button key={t.id} type="button" aria-pressed={types.includes(t.id)} onClick={() => setTypes((cur) => (cur.includes(t.id) ? cur.filter((x) => x !== t.id) : [...cur, t.id]))}>{t.label}</button>
            ))}
          </div>
          <p className={styles.count} aria-live="polite">{shown} {shown === 1 ? "event" : "events"}</p>
        </div>

        <div className={styles.layout}>
          <div className={styles.list}>
            {days.map((d) => {
              const info = DAYS[d - 1];
              const rows = visible(d);
              if (rows.length === 0) return null;
              return (
                <section key={d} className={styles.day} style={{ "--accent": info.accent } as React.CSSProperties} aria-labelledby={`plan-day-${d}`}>
                  <h3 id={`plan-day-${d}`} className={styles.dayHead}><span className={styles.dayTag}>Day {d}</span><span className={styles.dayName}>{info.name}</span><span className={styles.dayDate}>{info.date}</span></h3>
                  <ul>
                    {rows.map((s) => {
                      const on = plan.includes(s.event.id);
                      const clash = on ? conflictsFor(s, chosen) : [];
                      return (
                        <li key={s.event.id} className={`${styles.row} ${on ? styles.rowOn : ""}`}>
                          <div className={styles.time}><time>{s.time}</time><small>IST</small></div>
                          <div className={styles.info}>
                            <p className={styles.name}>{s.event.title}</p>
                            <p className={styles.meta}>{s.venue} · {TYPES.find((t) => t.id === s.event.type)?.label}</p>
                            {clash.length > 0 && <p className={styles.clash}>Overlaps with {clash.map((c) => c.event.title).join(", ")}</p>}
                          </div>
                          <button type="button" className={styles.add} aria-pressed={on} onClick={() => toggle(s.event.id)}>
                            {on ? <><Check /> In your plan</> : "Add to plan"}<span className="sr-only">: {s.event.title}</span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              );
            })}
            {shown === 0 && <p className={styles.empty}>No events match these filters. <button type="button" onClick={() => { setDay(0); setTypes([]); }}>Show everything</button></p>}
          </div>

          <aside id="your-plan" className={styles.plan} aria-labelledby="plan-title">
            <h3 id="plan-title" className={styles.planTitle}>Your plan <span>{chosen.length}</span></h3>
            {chosen.length === 0 ? (
              <p className={styles.planEmpty}>Nothing yet. Add events from the list and they’ll appear here in time order.</p>
            ) : (
              <>
                {clashCount > 0 && <p className={styles.planWarn} role="status">{clashCount} {clashCount === 1 ? "event overlaps" : "events overlap"} another. You can keep both, or remove one.</p>}
                {[...grouped.entries()].map(([d, items]) => (
                  <div key={d} className={styles.planDay}>
                    <h4>{DAYS[d - 1].name}<span>{DAYS[d - 1].short}</span></h4>
                    <ul>
                      {items.map((s) => (
                        <li key={s.event.id}>
                          <time>{s.time}</time>
                          <span>{s.event.title}{conflictsFor(s, chosen).length > 0 && <em> (overlap)</em>}</span>
                          <button type="button" onClick={() => toggle(s.event.id)} aria-label={`Remove ${s.event.title}`}>
                            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="m4 4 8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.8" fill="none" /></svg>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
                <div className={styles.planActions}>
                  <button type="button" className={styles.primary} onClick={download}>Download calendar file</button>
                  <button type="button" className={styles.secondary} onClick={copy}>Copy as text</button>
                  <button type="button" className={styles.link} onClick={() => { setPlan([]); say("Plan cleared."); }}>Clear plan</button>
                </div>
              </>
            )}
            <p className={styles.note} role="status" aria-live="polite">{note}</p>
          </aside>
        </div>

        {chosen.length > 0 && <a href="#your-plan" className={styles.jump}>Your plan · {chosen.length}</a>}
      </div>
    </section>
  );
}
