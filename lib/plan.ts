import type { AvinyaEvent } from "../data/events";

/** Placeholder duration until the organisers publish real end times. */
export const DEFAULT_MINUTES = 90;

export interface Slot { event: AvinyaEvent; start: number; end: number; venue: string; time: string }

/** "10:00 · ALGORITHM ARENA" → minutes from midnight + a readable venue. */
export function slotOf(event: AvinyaEvent, minutes = DEFAULT_MINUTES): Slot {
  const [time, rawVenue = ""] = event.meta.split(" · ");
  const [hh, mm] = time.split(":").map(Number);
  const start = hh * 60 + mm;
  const venue = rawVenue.toLowerCase().replace(/\b[a-z]/g, (c) => c.toUpperCase());
  return { event, start, end: start + minutes, venue, time };
}

/** Selected events on the same day whose time ranges intersect. Back-to-back is not a conflict. */
export function conflictsFor(slot: Slot, others: Slot[]): Slot[] {
  return others.filter((o) => o.event.id !== slot.event.id && o.event.day === slot.event.day && o.start < slot.end && slot.start < o.end);
}

export function groupByDay(slots: Slot[]): Map<number, Slot[]> {
  const out = new Map<number, Slot[]>();
  for (const s of [...slots].sort((a, b) => a.event.day - b.event.day || a.start - b.start)) {
    out.set(s.event.day, [...(out.get(s.event.day) ?? []), s]);
  }
  return out;
}

const pad = (n: number) => String(n).padStart(2, "0");
const stamp = (d: Date) => `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}00Z`;
const esc = (s: string) => s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");

/** One calendar file for the whole plan. Times are IST (UTC+5:30); dates are 12–14 March 2027. */
export function buildIcs(slots: Slot[], venue: string, now = new Date()): string {
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Avinya 2027//Plan//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"];
  for (const s of slots) {
    const start = new Date(Date.UTC(2027, 2, 11 + s.event.day, 0, s.start - 330));
    const end = new Date(Date.UTC(2027, 2, 11 + s.event.day, 0, s.end - 330));
    lines.push(
      "BEGIN:VEVENT",
      `UID:avinya27-${s.event.id}@iiitdwd`,
      `DTSTAMP:${stamp(now)}`,
      `DTSTART:${stamp(start)}`,
      `DTEND:${stamp(end)}`,
      `SUMMARY:${esc(`${s.event.title} · Avinya 2027`)}`,
      `LOCATION:${esc(`${s.venue}, ${venue}`)}`,
      `DESCRIPTION:${esc("Preview timing; the organisers will confirm the final schedule.")}`,
      "END:VEVENT",
    );
  }
  lines.push("END:VCALENDAR");
  return lines.join("\r\n");
}

export function planText(slots: Slot[], dayNames: string[], dates: string[]): string {
  const grouped = groupByDay(slots);
  const out: string[] = ["My Avinya 2027 plan"];
  for (const [day, items] of grouped) {
    out.push("", `${dayNames[day - 1]} — ${dates[day - 1]}`);
    for (const s of items) out.push(`${s.time}  ${s.event.title} (${s.venue})`);
  }
  return out.join("\n");
}
