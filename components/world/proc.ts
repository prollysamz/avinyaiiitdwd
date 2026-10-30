import * as THREE from "three";

/* ------------------------------------------------------------------ math */
export const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const mix = (a: number, b: number, t: number) => a + (b - a) * t;
export const smoothstep = (a: number, b: number, x: number) => {
  const t = clamp((x - a) / (b - a));
  return t * t * (3 - 2 * t);
};

export function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* ----------------------------------------------------------------- noise */
const P = new Uint8Array(512);
(() => {
  const r = rng(1337);
  const a = Array.from({ length: 256 }, (_, i) => i);
  for (let i = 255; i > 0; i--) {
    const j = Math.floor(r() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  for (let i = 0; i < 512; i++) P[i] = a[i & 255];
})();

const fade = (t: number) => t * t * t * (t * (t * 6 - 15) + 10);
function grad(h: number, x: number, y: number) {
  switch (h & 7) {
    case 0: return x + y;
    case 1: return -x + y;
    case 2: return x - y;
    case 3: return -x - y;
    case 4: return x;
    case 5: return -x;
    case 6: return y;
    default: return -y;
  }
}

/** Perlin noise in roughly [-1,1]; px/py > 0 makes it tile with that lattice period. */
export function noise2(x: number, y: number, px = 0, py = px): number {
  const xi = Math.floor(x), yi = Math.floor(y);
  const xf = x - xi, yf = y - yi;
  let x0 = xi, x1 = xi + 1, y0 = yi, y1 = yi + 1;
  if (px > 0) { x0 = ((x0 % px) + px) % px; x1 = ((x1 % px) + px) % px; }
  if (py > 0) { y0 = ((y0 % py) + py) % py; y1 = ((y1 % py) + py) % py; }
  x0 &= 255; x1 &= 255; y0 &= 255; y1 &= 255;
  const aa = P[P[x0] + y0], ab = P[P[x0] + y1], ba = P[P[x1] + y0], bb = P[P[x1] + y1];
  const u = fade(xf), v = fade(yf);
  const l1 = grad(aa, xf, yf) + (grad(ba, xf - 1, yf) - grad(aa, xf, yf)) * u;
  const l2 = grad(ab, xf, yf - 1) + (grad(bb, xf - 1, yf - 1) - grad(ab, xf, yf - 1)) * u;
  return (l1 + (l2 - l1) * v) * 1.4142;
}

export function fbm(x: number, y: number, oct = 5, px = 0, py = px, gain = 0.5): number {
  let a = 1, f = 1, s = 0, n = 0;
  for (let i = 0; i < oct; i++) {
    s += a * noise2(x * f, y * f, px * f, py * f);
    n += a; a *= gain; f *= 2;
  }
  return s / n;
}

export function ridged(x: number, y: number, oct = 5, px = 0, py = px): number {
  let a = 1, f = 1, s = 0, n = 0;
  for (let i = 0; i < oct; i++) {
    const v = 1 - Math.abs(noise2(x * f, y * f, px * f, py * f));
    s += a * v * v; n += a; a *= 0.5; f *= 2;
  }
  return s / n;
}

function hash3(i: number, j: number, k: number) {
  let n = Math.imul(i, 374761393) + Math.imul(j, 668265263) + Math.imul(k, 1274126177);
  n = Math.imul(n ^ (n >>> 13), 1274126177);
  return ((n ^ (n >>> 16)) >>> 0) / 4294967295;
}
export function noise3(x: number, y: number, z: number) {
  const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
  const xf = fade(x - xi), yf = fade(y - yi), zf = fade(z - zi);
  const l = (a: number, b: number, t: number) => a + (b - a) * t;
  return l(
    l(l(hash3(xi, yi, zi), hash3(xi + 1, yi, zi), xf), l(hash3(xi, yi + 1, zi), hash3(xi + 1, yi + 1, zi), xf), yf),
    l(l(hash3(xi, yi, zi + 1), hash3(xi + 1, yi, zi + 1), xf), l(hash3(xi, yi + 1, zi + 1), hash3(xi + 1, yi + 1, zi + 1), xf), yf),
    zf,
  ) * 2 - 1;
}
export function fbm3(x: number, y: number, z: number, oct = 4) {
  let a = 1, f = 1, s = 0, n = 0;
  for (let i = 0; i < oct; i++) { s += a * noise3(x * f, y * f, z * f); n += a; a *= 0.5; f *= 2; }
  return s / n;
}

/* -------------------------------------------------------------- textures */
type Px = [number, number, number] | [number, number, number, number];
const cache = new Map<string, unknown>();
function once<T>(key: string, make: () => T): T {
  if (!cache.has(key)) cache.set(key, make());
  return cache.get(key) as T;
}

function finish(canvas: HTMLCanvasElement, srgb: boolean) {
  const t = new THREE.CanvasTexture(canvas);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  t.anisotropy = 8;
  t.needsUpdate = true;
  return t;
}

function paint(w: number, h: number, fn: (x: number, y: number, u: number, v: number) => Px, srgb = true) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  const ctx = c.getContext("2d")!;
  const img = ctx.createImageData(w, h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const p = fn(x, y, x / w, y / h);
    const i = (y * w + x) * 4;
    img.data[i] = clamp(p[0]) * 255; img.data[i + 1] = clamp(p[1]) * 255; img.data[i + 2] = clamp(p[2]) * 255;
    img.data[i + 3] = (p[3] ?? 1) * 255;
  }
  ctx.putImageData(img, 0, 0);
  return finish(c, srgb);
}

function heights(w: number, h: number, fn: (u: number, v: number) => number) {
  const out = new Float32Array(w * h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) out[y * w + x] = fn(x / w, y / h);
  return out;
}

function normalMap(hf: Float32Array, w: number, h: number, strength: number) {
  return paint(w, h, (x, y) => {
    const l = hf[y * w + ((x - 1 + w) % w)], r = hf[y * w + ((x + 1) % w)];
    const d = hf[((y - 1 + h) % h) * w + x], u = hf[((y + 1) % h) * w + x];
    const nx = (l - r) * strength, ny = (u - d) * strength;
    const len = Math.hypot(nx, ny, 1);
    return [(nx / len) * 0.5 + 0.5, (ny / len) * 0.5 + 0.5, (1 / len) * 0.5 + 0.5];
  }, false);
}

export function rep(t: THREE.Texture, x: number, y = x) {
  const c = t.clone();
  c.repeat.set(x, y);
  c.needsUpdate = true;
  return c;
}

/** Wind-rippled sand. */
export const sandTextures = () => once("sand", () => {
  const S = 256;
  const hf = heights(S, S, (u, v) => {
    const w = fbm(u * 5, v * 5, 4, 5);
    const rip = Math.sin((u * 26 + w * 3.2) * Math.PI * 2) * 0.5 + 0.5;
    return rip * 0.3 + fbm(u * 48, v * 48, 3, 48) * 0.3 + w * 0.3;
  });
  const map = paint(S, S, (x, y) => {
    const g = 0.74 + hf[y * S + x] * 0.26 + noise2(x * 0.9, y * 0.9, S * 0.9) * 0.04;
    return [g, g * 0.98, g * 0.94];
  });
  return { map, normalMap: normalMap(hf, S, S, 3.2) };
});

export const rockTextures = () => once("rock", () => {
  const S = 256;
  const hf = heights(S, S, (u, v) => ridged(u * 4, v * 4, 5, 4) * 0.7 + fbm(u * 18, v * 18, 4, 18) * 0.3);
  const map = paint(S, S, (x, y) => {
    const g = 0.55 + hf[y * S + x] * 0.45;
    return [g, g * 0.96, g * 0.92];
  });
  return { map, normalMap: normalMap(hf, S, S, 5) };
});

export const woodTextures = () => once("wood", () => {
  const W = 256, H = 256, planks = 6;
  const hf = heights(W, H, (u, v) => {
    const pi = Math.floor(v * planks), lv = v * planks - pi;
    const seam = smoothstep(0, 0.07, lv) * smoothstep(1, 0.93, lv);
    const grain = noise2(u * 3 + pi * 5.3, v * planks * 38, 0, 0) * 0.5 + 0.5;
    const grain2 = noise2(u * 6 + pi * 2.1, v * planks * 90, 0, 0) * 0.5 + 0.5;
    return seam * (0.35 + grain * 0.4 + grain2 * 0.25);
  });
  const map = paint(W, H, (x, y, u, v) => {
    const pi = Math.floor(v * planks), lv = v * planks - pi;
    const seam = smoothstep(0, 0.06, lv) * smoothstep(1, 0.94, lv);
    const tone = 0.82 + noise2(pi * 7.7, 3.1) * 0.18;
    const g = hf[y * W + x];
    const k = (0.32 + g * 0.8) * tone * (0.35 + seam * 0.65);
    return [k * 1.0, k * 0.66, k * 0.4];
  });
  return { map, normalMap: normalMap(hf, W, H, 2.4) };
});

export const clothTextures = () => once("cloth", () => {
  const S = 256;
  const hf = heights(S, S, (u, v) => {
    const weave = Math.sin(u * Math.PI * 2 * 64) * Math.sin(v * Math.PI * 2 * 64) * 0.5 + 0.5;
    const seam = smoothstep(0, 0.012, Math.abs(((v * 5) % 1) - 0.0)) ;
    return weave * 0.5 + fbm(u * 8, v * 8, 3, 8) * 0.2 + (1 - seam) * -0.6;
  });
  const map = paint(S, S, (x, y, u, v) => {
    const seamLine = 1 - smoothstep(0.0, 0.012, Math.abs(((v * 5) % 1)));
    const k = 0.84 + hf[y * S + x] * 0.14 - seamLine * 0.22 + noise2(u * 12, v * 12, 12) * 0.05;
    return [k, k * 0.97, k * 0.9];
  });
  return { map, normalMap: normalMap(hf, S, S, 1.3) };
});

export const concreteTextures = () => once("concrete", () => {
  const S = 256;
  const hf = heights(S, S, (u, v) => {
    const panel = Math.min(smoothstep(0, 0.012, Math.abs(((u * 4) % 1) - 0.0)), smoothstep(0, 0.012, Math.abs(((v * 4) % 1) - 0.0)));
    return panel * (0.55 + fbm(u * 10, v * 10, 5, 10) * 0.3 + noise2(u * 90, v * 90, 90) * 0.08);
  });
  const map = paint(S, S, (x, y, u, v) => {
    const g = 0.5 + hf[y * S + x] * 0.5 + noise2(u * 5 + 9, v * 5, 5) * 0.08;
    return [g, g * 0.97, g * 0.93];
  });
  return { map, normalMap: normalMap(hf, S, S, 2.2) };
});

export const fabricNormal = () => once("fabricN", () => {
  const S = 128;
  return normalMap(heights(S, S, (u, v) => (Math.sin(u * Math.PI * 2 * 24) * Math.sin(v * Math.PI * 2 * 24)) * 0.4 + fbm(u * 6, v * 6, 3, 6) * 0.3), S, S, 1.6);
});

/** Lit-window grid: grayscale emissive (tinted by material.emissive). */
export const windowTexture = () => once("windows", () => {
  const S = 128, cells = 8, r = rng(7);
  const lit = Array.from({ length: cells * cells }, () => (r() > 0.42 ? 0.35 + r() * 0.65 : 0));
  return paint(S, S, (x, y) => {
    const cs = S / cells;
    const cx = Math.floor(x / cs), cy = Math.floor(y / cs);
    const lx = (x % cs) / cs, ly = (y % cs) / cs;
    const inside = lx > 0.2 && lx < 0.8 && ly > 0.25 && ly < 0.75;
    const v = inside ? lit[cy * cells + cx] : 0;
    return [v, v, v];
  });
});

export const gridFloor = () => once("gridFloor", () => {
  const S = 512;
  return paint(S, S, (x, y) => {
    const g = (n: number) => 1 - smoothstep(0, 1.6, Math.min(n % (S / 8), S / 8 - (n % (S / 8))));
    const l = Math.max(g(x), g(y));
    const f = Math.max(g(x * 2 + 0), g(y * 2)) * 0.25;
    return [Math.max(l, f) * 1.0, Math.max(l, f) * 1.0, Math.max(l, f) * 1.0];
  });
});

export function neonSign(text: string, color: string, w = 512, h = 160) {
  return once(`sign-${text}-${color}`, () => {
    const c = document.createElement("canvas");
    c.width = w; c.height = h;
    const ctx = c.getContext("2d")!;
    ctx.fillStyle = "#04030a"; ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = color; ctx.lineWidth = 5; ctx.shadowColor = color; ctx.shadowBlur = 24;
    ctx.strokeRect(14, 14, w - 28, h - 28);
    ctx.font = `800 ${Math.floor(h * 0.5)}px "Arial Black", Impact, sans-serif`;
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillStyle = "#fff"; ctx.shadowBlur = 30;
    ctx.fillText(text, w / 2, h / 2 + 4);
    ctx.shadowBlur = 0; ctx.fillStyle = color; ctx.globalAlpha = 0.5;
    ctx.fillText(text, w / 2, h / 2 + 4);
    return finish(c, true);
  });
}

export function stripedCanvas(a: string, b: string, n = 10) {
  return once(`stripe-${a}-${b}-${n}`, () => {
    const c = document.createElement("canvas");
    c.width = 256; c.height = 64;
    const ctx = c.getContext("2d")!;
    for (let i = 0; i < n; i++) { ctx.fillStyle = i % 2 ? b : a; ctx.fillRect((i * 256) / n, 0, 256 / n + 1, 64); }
    // weave noise
    const img = ctx.getImageData(0, 0, 256, 64);
    for (let i = 0; i < img.data.length; i += 4) {
      const n2 = (Math.random() - 0.5) * 22;
      img.data[i] += n2; img.data[i + 1] += n2; img.data[i + 2] += n2;
    }
    ctx.putImageData(img, 0, 0);
    return finish(c, true);
  });
}

export const waterNormals = () => once("waterN", () => {
  const S = 512, r = rng(99);
  const waves: { fx: number; fy: number; a: number; p: number }[] = [];
  for (let i = 0; i < 34; i++) {
    const f = Math.floor(2 + Math.pow(r(), 1.5) * 20);
    const ang = r() * Math.PI * 2;
    waves.push({ fx: Math.round(Math.cos(ang) * f), fy: Math.round(Math.sin(ang) * f), a: (1 / (1 + f * 0.35)) * (0.5 + r()), p: r() * 6.28 });
  }
  return paint(S, S, (x, y, u, v) => {
    let dx = 0, dy = 0;
    for (const w of waves) {
      const ph = (w.fx * u + w.fy * v) * Math.PI * 2 + w.p;
      const s = Math.sin(ph), c = Math.cos(ph);
      // sharpened crest: derivative of |sin|-ish blend
      const d = c * (0.65 + 0.35 * s) * w.a * Math.PI * 2;
      dx += d * w.fx; dy += d * w.fy;
    }
    const k = 0.05;
    const nx = -dx * k, ny = -dy * k, len = Math.hypot(nx, ny, 1);
    return [(nx / len) * 0.5 + 0.5, (ny / len) * 0.5 + 0.5, (1 / len) * 0.5 + 0.5];
  }, false);
});

export const glowTexture = () => once("glow", () => {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const ctx = c.getContext("2d")!;
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, "rgba(255,255,255,1)"); g.addColorStop(0.18, "rgba(255,255,255,.55)");
  g.addColorStop(0.5, "rgba(255,255,255,.12)"); g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g; ctx.fillRect(0, 0, 128, 128);
  return finish(c, true);
});

export function foamTexture(h: (x: number, z: number) => number, extent: number, size = 256) {
  const t = paint(size, size, (px, py) => {
    const x = (px / size - 0.5) * extent, z = (py / size - 0.5) * extent;
    const hh = h(x, z);
    const n = fbm(px * 0.12, py * 0.12, 3) * 0.5 + 0.5;
    const band = smoothstep(-0.55, -0.05, hh) * smoothstep(0.55, 0.12, hh);
    const edge = smoothstep(0.04, -0.12, Math.abs(hh + 0.08) - 0.1) ;
    const a = clamp(band * (0.25 + n * 0.9)) * 0.8 + edge * 0.25;
    return [1, 1, 1, clamp(a)];
  });
  t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
  return t;
}

export const earthTextures = () => once("earth", () => {
  const W = 1024, H = 512;
  const map = paint(W, H, (x, y, u, v) => {
    const l = fbm(u * 4, v * 2, 5, 4, 2);
    const lat = Math.abs(v - 0.5) * 2;
    const landMask = smoothstep(-0.015, 0.035, l);
    const mnt = smoothstep(0.18, 0.4, l);
    const dry = smoothstep(0.6, 0.15, lat) * (0.5 + noise2(u * 9, v * 9, 9) * 0.5);
    let lr = mix(0.1, 0.62, dry), lg = mix(0.3, 0.5, dry), lb = mix(0.1, 0.27, dry);
    lr = mix(lr, 0.5, mnt * 0.6); lg = mix(lg, 0.46, mnt * 0.6); lb = mix(lb, 0.42, mnt * 0.6);
    const depth = smoothstep(0.0, -0.3, l);
    const shallow = smoothstep(-0.12, 0.0, l);
    const wr = mix(mix(0.03, 0.01, depth), 0.12, shallow * 0.8), wg = mix(mix(0.18, 0.06, depth), 0.42, shallow * 0.8), wb = mix(mix(0.4, 0.2, depth), 0.5, shallow * 0.8);
    const ice = smoothstep(0.82, 0.94, lat);
    return [mix(mix(wr, lr, landMask), 0.95, ice), mix(mix(wg, lg, landMask), 0.97, ice), mix(mix(wb, lb, landMask), 1, ice)];
  });
  const clouds = paint(W, H, (x, y, u, v) => {
    const c = fbm(u * 6 + 3, v * 3 + 1, 5, 6, 3);
    return [1, 1, 1, smoothstep(0.04, 0.4, c) * 0.9];
  });
  return { map, clouds };
});

export const moonTextures = () => once("moon", () => {
  const W = 512, H = 256, r = rng(5);
  const craters = Array.from({ length: 90 }, () => ({ u: r(), v: 0.1 + r() * 0.8, r: 0.006 + Math.pow(r(), 2.4) * 0.07 }));
  const hf = heights(W, H, (u, v) => {
    let h = fbm(u * 6, v * 3, 5, 6, 3) * 0.35;
    for (const c of craters) {
      let du = Math.abs(u - c.u); if (du > 0.5) du = 1 - du;
      const d = Math.hypot(du * 2, v - c.v) / (c.r * 2);
      if (d < 1.4) h += d < 1 ? -(1 - d * d) * 0.55 : Math.exp(-(d - 1) * 5) * 0.2;
    }
    return h;
  });
  const map = paint(W, H, (x, y) => { const g = 0.5 + hf[y * W + x] * 0.35; return [g, g * 0.98, g * 0.95]; });
  return { map, normalMap: normalMap(hf, W, H, 3.5) };
});

export const frondTexture = () => once("frond", () => {
  const c = document.createElement("canvas");
  c.width = 256; c.height = 128;
  const ctx = c.getContext("2d")!;
  ctx.clearRect(0, 0, 256, 128);
  ctx.strokeStyle = "#6b7d2c"; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.moveTo(0, 64); ctx.lineTo(250, 64); ctx.stroke();
  for (let i = 0; i < 44; i++) {
    const x = 8 + i * 5.4, len = 56 * Math.sin((i / 44) * Math.PI * 0.9 + 0.25) + 6;
    for (const s of [-1, 1]) {
      ctx.strokeStyle = i % 2 ? "#3f6b25" : "#4d7a2b"; ctx.lineWidth = 3.2;
      ctx.beginPath(); ctx.moveTo(x, 64); ctx.quadraticCurveTo(x + 10, 64 + s * len * 0.55, x + 22, 64 + s * len); ctx.stroke();
    }
  }
  return finish(c, true);
});

/** Ringed palm bark: rings run across u (the length of a TubeGeometry). */
export const barkTexture = () => once("bark", () =>
  paint(128, 64, (x, y, u, v) => {
    const ring = Math.pow(Math.abs(Math.sin(u * Math.PI * 8)), 0.35);
    const n = noise2(u * 24, v * 6, 24, 6) * 0.5 + 0.5;
    const k = 0.45 + ring * 0.35 + n * 0.2;
    return [k * 0.62, k * 0.5, k * 0.38];
  }));

/** Striped awning valance with a scalloped lower edge (alpha-tested). */
export function scallopTexture(a: string, b: string, n = 8) {
  return once(`scallop-${a}-${b}`, () => {
    const c = document.createElement("canvas");
    c.width = 256; c.height = 64;
    const ctx = c.getContext("2d")!;
    const w = 256 / n;
    for (let i = 0; i < n; i++) {
      ctx.fillStyle = i % 2 ? b : a;
      ctx.beginPath();
      ctx.moveTo(i * w, 0); ctx.lineTo((i + 1) * w, 0); ctx.lineTo((i + 1) * w, 30);
      ctx.arc(i * w + w / 2, 30, w / 2, 0, Math.PI, false);
      ctx.closePath(); ctx.fill();
    }
    return finish(c, true);
  });
}
