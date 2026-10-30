import Link from "next/link";

export default function NotFound() {
  return (
    <main className="grid min-h-screen place-items-center bg-[#071217] px-5 text-center text-foam">
      <div>
        <p className="font-mono text-xs uppercase tracking-[.3em] text-lagoon">Signal lost · 404</p>
        <h1 className="mt-4 font-display text-[clamp(3rem,12vw,9rem)] font-black leading-[.85] tracking-[-.05em]">Off the map.</h1>
        <p className="mx-auto mt-6 max-w-md text-base text-white/70">This page isn&apos;t on any chart we know. Turn the boat around and head back to the voyage.</p>
        <Link href="/" className="mt-10 inline-block border border-lagoon px-7 py-4 font-mono text-xs uppercase tracking-[.25em] text-lagoon hover:bg-lagoon hover:text-ink">Back to sea ↑</Link>
      </div>
    </main>
  );
}
