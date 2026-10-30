/**
 * Avinya 2027 events data.
 *
 * PLACEHOLDER: the organisers' events sheet is private, so these are sample entries
 * in the right shape. Replace this array with the real data (day: 1 | 2 | 3).
 */
export type EventType = "TECH" | "CULTURAL" | "DESIGN";

export interface AvinyaEvent {
  id: string;
  day: 1 | 2 | 3;
  type: EventType;
  title: string;
  meta: string; // "10:00 · VENUE"
  color: string;
}

export const DAYS = [
  {
    day: 1 as const, date: "12 March 2027", short: "12 MAR", name: "The Last Outpost", island: "Island 01", theme: "Dune-desert day",
    blurb: "Technology, design and competition open the festival in a desert setting.",
    accent: "#e97845",
  },
  {
    day: 2 as const, date: "13 March 2027", short: "13 MAR", name: "The Pandemonium", island: "Island 02", theme: "Synthwave cyberpunk night",
    blurb: "Music and technical challenges take over a neon-lit city on day two.",
    accent: "#ff2ea6",
  },
  {
    day: 3 as const, date: "14 March 2027", short: "14 MAR", name: "The Carnival Island", island: "Island 03", theme: "The day of the festival",
    blurb: "Cultural performances and design events bring the festival to the waterfront.",
    accent: "#ffbd4a",
  },
];

export const EVENTS: AvinyaEvent[] = [
  { id: "01", day: 1, type: "TECH", title: "Codebreakers' Regatta", meta: "10:00 · ALGORITHM ARENA", color: "#d55336" },
  { id: "02", day: 1, type: "DESIGN", title: "Rover's Last Mile", meta: "13:30 · OUTPOST YARD", color: "#e97845" },
  { id: "03", day: 1, type: "TECH", title: "Cipher at Sundown", meta: "16:00 · SIGNAL TOWER", color: "#c87a3e" },
  { id: "04", day: 2, type: "CULTURAL", title: "Neon Frequency", meta: "18:00 · DELTA STAGE", color: "#ff2ea6" },
  { id: "05", day: 2, type: "TECH", title: "Circuit Drift", meta: "21:00 · SYNTH BAY", color: "#38d7d2" },
  { id: "06", day: 2, type: "TECH", title: "Midnight Debug", meta: "23:00 · THE GRID", color: "#8b00ff" },
  { id: "07", day: 3, type: "CULTURAL", title: "Lanterns & Low Tide", meta: "17:30 · CARNIVAL PIER", color: "#ffbd4a" },
  { id: "08", day: 3, type: "DESIGN", title: "Paper Boat Atelier", meta: "11:00 · MAKER DOCK", color: "#ff7857" },
  { id: "09", day: 3, type: "CULTURAL", title: "Design Masquerade", meta: "19:00 · BIG TOP", color: "#d90429" },
];

export const eventsForDay = (day: 1 | 2 | 3) => EVENTS.filter((e) => e.day === day);

/** Fest starts 12 March 2027, 09:00 IST. */
export const FEST_START = new Date("2027-03-12T09:00:00+05:30").getTime();
export const HACK2FUTURE_URL = "https://hack2future.iiitdwd.ac.in/";
export const VENUE = "IIIT Dharwad Campus, Ittigatti Road, Near Sattur Colony, Dharwad 580009, Karnataka";
