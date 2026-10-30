import * as THREE from "three";

/** Everything that changes between the four "chapters" of the voyage. */
export interface Preset {
  top: THREE.Color; mid: THREE.Color; horizon: THREE.Color; ground: THREE.Color;
  sun: THREE.Color; fog: THREE.Color; deep: THREE.Color; shallow: THREE.Color;
  cloudLit: THREE.Color; cloudDark: THREE.Color; light: THREE.Color; hemiSky: THREE.Color; hemiGround: THREE.Color;
  sunDir: THREE.Vector3;
  sunCos: number; sunInt: number; stars: number; stripes: number; cloudAmt: number; haze: number;
  fogD: number; lightI: number; envI: number; hemiI: number; glint: number;
}

const C = (h: string) => new THREE.Color(h);
const mk = (o: Omit<Preset, "sunDir"> & { dir: [number, number, number] }): Preset => ({ ...o, sunDir: new THREE.Vector3(...o.dir).normalize() });

export const PRESETS: Preset[] = [
  // I — Last Outpost: dusty Arrakis golden hour
  mk({
    top: C("#5f86ad"), mid: C("#d9a577"), horizon: C("#f7c98e"), ground: C("#b98a5c"),
    sun: C("#ffd9a0"), fog: C("#efc08c"), deep: C("#0e4650"), shallow: C("#3e9b97"),
    cloudLit: C("#fff0d0"), cloudDark: C("#a9684a"), light: C("#ffd9a8"), hemiSky: C("#a8c4e0"), hemiGround: C("#8a5a3a"),
    dir: [-0.55, 0.3, -0.78], sunCos: 0.9984, sunInt: 40, stars: 0, stripes: 0, cloudAmt: 0.35, haze: 1,
    fogD: 0.0062, lightI: 4.4, envI: 0.85, hemiI: 0.55, glint: 1,
  }),
  // II — Pandemonium: synthwave dusk
  mk({
    top: C("#0b0330"), mid: C("#4a1485"), horizon: C("#ff3d94"), ground: C("#240845"),
    sun: C("#ff5cb0"), fog: C("#7a1f86"), deep: C("#13052c"), shallow: C("#3b1478"),
    cloudLit: C("#ff77c8"), cloudDark: C("#2a0b55"), light: C("#ff6fc0"), hemiSky: C("#7a3cff"), hemiGround: C("#ff2e8a"),
    dir: [0.12, 0.13, -1], sunCos: 0.9946, sunInt: 2.6, stars: 0.55, stripes: 1, cloudAmt: 0.5, haze: 1.4,
    fogD: 0.0095, lightI: 1.3, envI: 0.75, hemiI: 0.7, glint: 1,
  }),
  // III — Carnival Island: lantern-lit sunset
  mk({
    top: C("#1d2860"), mid: C("#a4466a"), horizon: C("#ffa24c"), ground: C("#4a2230"),
    sun: C("#ffb15e"), fog: C("#c7704a"), deep: C("#141c38"), shallow: C("#355a82"),
    cloudLit: C("#ffa56a"), cloudDark: C("#4a2349"), light: C("#ffb067"), hemiSky: C("#7d8bd8"), hemiGround: C("#b3552e"),
    dir: [-0.66, 0.22, -0.58], sunCos: 0.9978, sunInt: 14, stars: 0.18, stripes: 0, cloudAmt: 0.55, haze: 1.1,
    fogD: 0.0075, lightI: 4.4, envI: 1.0, hemiI: 0.95, glint: 1,
  }),
  // IV — Hack2Future: orbit
  mk({
    top: C("#000104"), mid: C("#010510"), horizon: C("#061738"), ground: C("#0a2145"),
    sun: C("#f4f8ff"), fog: C("#02050c"), deep: C("#01060f"), shallow: C("#04152b"),
    cloudLit: C("#8fb0ff"), cloudDark: C("#04081a"), light: C("#eaf2ff"), hemiSky: C("#5a6f96"), hemiGround: C("#0b0c12"),
    dir: [0.82, 0.3, 0.38], sunCos: 0.9992, sunInt: 60, stars: 1, stripes: 0, cloudAmt: 0, haze: 0.2,
    fogD: 0.0018, lightI: 3.6, envI: 0.6, hemiI: 0.35, glint: 0.4,
  }),
];

export function makePreset(): Preset {
  return {
    top: new THREE.Color(), mid: new THREE.Color(), horizon: new THREE.Color(), ground: new THREE.Color(),
    sun: new THREE.Color(), fog: new THREE.Color(), deep: new THREE.Color(), shallow: new THREE.Color(),
    cloudLit: new THREE.Color(), cloudDark: new THREE.Color(), light: new THREE.Color(), hemiSky: new THREE.Color(), hemiGround: new THREE.Color(),
    sunDir: new THREE.Vector3(0, 1, 0),
    sunCos: 1, sunInt: 0, stars: 0, stripes: 0, cloudAmt: 0, haze: 0, fogD: 0, lightI: 0, envI: 0, hemiI: 0, glint: 1,
  };
}

const COLORS = ["top", "mid", "horizon", "ground", "sun", "fog", "deep", "shallow", "cloudLit", "cloudDark", "light", "hemiSky", "hemiGround"] as const;
const NUMS = ["sunCos", "sunInt", "stars", "stripes", "cloudAmt", "haze", "fogD", "lightI", "envI", "hemiI", "glint"] as const;

export function blendPreset(out: Preset, phase: number) {
  const p = Math.min(Math.max(phase, 0), PRESETS.length - 1);
  const i = Math.min(Math.floor(p), PRESETS.length - 2);
  const t = p - i;
  const a = PRESETS[i], b = PRESETS[i + 1];
  for (const k of COLORS) out[k].lerpColors(a[k], b[k], t);
  for (const k of NUMS) (out as unknown as Record<string, number>)[k] = a[k] + (b[k] - a[k]) * t;
  out.sunDir.lerpVectors(a.sunDir, b.sunDir, t).normalize();
}

/** Mutable state shared by every part of the 3D world (read each frame). */
export const world = {
  cur: makePreset(),
  phase: 0,
  velocity: 0,
  camPos: new THREE.Vector3(),
  camFwd: new THREE.Vector3(0, 0, -1),
  compact: false,
  /** 0 low · 1 mid · 2 high (start tier; the live tier can step down at runtime) */
  quality: 2,
  /** prefers-reduced-motion: scene time is frozen and the camera holds each chapter */
  reduced: false,
  /** scene clock and step — use these instead of the R3F clock so reduced motion can freeze them */
  time: 0,
  dt: 0,
  /** 0..1 presence of each island chapter, of the orbital chapter, and of altitude */
  islandK: [0, 0, 0] as number[],
  spaceK: 0,
  altK: 0,
};

/* ------------------------------------------------------------- sky shader */
const noiseGLSL = /* glsl */ `
float h21(vec2 p){ p = fract(p*vec2(123.34,456.21)); p += dot(p,p+45.32); return fract(p.x*p.y); }
float h31(vec3 p){ p = fract(p*.3183099+.1); p *= 17.; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
float vn(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f);
  return mix(mix(h21(i),h21(i+vec2(1,0)),f.x), mix(h21(i+vec2(0,1)),h21(i+vec2(1,1)),f.x), f.y); }
float fbm2(vec2 p){ float a=.5, s=0.; for(int i=0;i<5;i++){ s+=a*vn(p); p=p*2.03+vec2(17.1,9.2); a*=.5; } return s; }
float vn3(vec3 p){ vec3 i=floor(p), f=fract(p); f=f*f*(3.-2.*f);
  return mix(mix(mix(h31(i),h31(i+vec3(1,0,0)),f.x), mix(h31(i+vec3(0,1,0)),h31(i+vec3(1,1,0)),f.x),f.y),
             mix(mix(h31(i+vec3(0,0,1)),h31(i+vec3(1,0,1)),f.x), mix(h31(i+vec3(0,1,1)),h31(i+vec3(1,1,1)),f.x),f.y), f.z); }
`;

export function createSkyMaterial() {
  return new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, depthTest: false, fog: false,
    uniforms: {
      uTop: { value: new THREE.Color() }, uMid: { value: new THREE.Color() }, uHorizon: { value: new THREE.Color() }, uGround: { value: new THREE.Color() },
      uSunDir: { value: new THREE.Vector3(0, 1, 0) }, uSunColor: { value: new THREE.Color() },
      uSunCos: { value: 0.998 }, uSunInt: { value: 20 }, uStars: { value: 0 }, uStripes: { value: 0 }, uHaze: { value: 1 },
      uCloudAmt: { value: 0 }, uCloudLit: { value: new THREE.Color() }, uCloudDark: { value: new THREE.Color() }, uTime: { value: 0 },
      uDip: { value: 0 }, uLimb: { value: 0 },
    },
    vertexShader: /* glsl */ `
      varying vec3 vDir;
      void main(){
        vec4 w = modelMatrix * vec4(position, 1.0);
        vDir = w.xyz - cameraPosition;
        gl_Position = projectionMatrix * viewMatrix * w;
      }`,
    fragmentShader: /* glsl */ `
      uniform vec3 uTop,uMid,uHorizon,uGround,uSunDir,uSunColor,uCloudLit,uCloudDark;
      uniform float uSunCos,uSunInt,uStars,uStripes,uHaze,uCloudAmt,uTime,uDip,uLimb;
      varying vec3 vDir;
      ${noiseGLSL}
      // Angular star positions stay fixed as the camera travels. Derivative
      // filtering keeps subpixel stars stable across screen sizes and DPRs.
      vec3 starLayer(vec2 uv, vec2 density, float threshold, float gain) {
        vec2 grid = uv * density;
        vec2 cell = floor(grid);
        float seed = h21(cell + 11.7);
        vec2 center = vec2(h21(cell + 3.1), h21(cell + 8.9)) * 0.6 + 0.2;
        float distanceToStar = length(fract(grid) - center);
        float bright = pow(h21(cell + 71.0), 7.0);
        float radius = 0.035 + bright * 0.085;
        float aa = max(length(fwidth(grid)) * 0.55, 0.015);
        float disc = 1.0 - smoothstep(max(0.0, radius - aa), radius + aa, distanceToStar);
        float energy = min(1.0, radius * radius / max(aa * aa, 0.0001));
        vec3 color = mix(vec3(0.72, 0.82, 1.0), vec3(1.0, 0.89, 0.75), h21(cell + 29.0));
        // Stars viewed from orbit are steady; atmospheric twinkle is very mild.
        float twinkle = 1.0 + sin(uTime * 0.8 + seed * 70.0) * 0.035 * (1.0 - uLimb);
        return color * disc * energy * step(threshold, seed) * (0.6 + bright * 2.0) * gain * twinkle;
      }
      void main(){
        vec3 d = normalize(vDir);
        float h = d.y + uDip; // from altitude the horizon sits below eye level
        vec3 col = mix(uHorizon, uMid, smoothstep(0.0, 0.22, h));
        col = mix(col, uTop, smoothstep(0.12, 0.85, h));
        col = mix(col, uGround, smoothstep(0.0, -0.28, h));
        float s = max(dot(d, uSunDir), 0.0);

        // atmosphere scatter around the sun
        col += uSunColor * (pow(s, 5.0) * 0.22 + pow(s, 24.0) * 0.35) * uHaze * smoothstep(-0.15, 0.2, h);

        // clouds on a projected plane
        if (uCloudAmt > 0.001 && h > 0.0) {
          vec2 cp = d.xz / (h + 0.18) * 1.15 + vec2(uTime * 0.012, uTime * 0.004);
          float c = fbm2(cp * 1.4);
          float c2 = fbm2(cp * 3.2 + 7.0);
          float cov = smoothstep(0.46, 0.78, c * 0.85 + c2 * 0.3) * uCloudAmt * smoothstep(0.0, 0.18, h) * (1.0 - smoothstep(0.55, 0.95, h) * 0.6);
          float lit = clamp(0.35 + dot(normalize(vec3(d.xz, 0.2)), normalize(vec3(uSunDir.xz, 0.2))) * 0.55 + c2 * 0.4 + pow(s, 6.0) * 0.8, 0.0, 1.5);
          vec3 cc = mix(uCloudDark, uCloudLit, clamp(lit, 0.0, 1.0));
          cc += uSunColor * pow(s, 10.0) * 0.6; // silver lining
          col = mix(col, cc, clamp(cov, 0.0, 1.0));
        }

        // sun disc (optionally synthwave-striped)
        float ang = sqrt(max(1.0 - uSunCos * uSunCos, 1e-6));
        float disc = smoothstep(uSunCos - 0.00035, uSunCos + 0.00035, s);
        vec3 sunCol = uSunColor;
        if (uStripes > 0.5) {
          float vy = (uSunDir.y - d.y) / ang;               // -1 top .. +1 bottom
          float lowerHalf = step(-0.15, vy);
          float gap = fract(vy * 6.0);
          float cutW = clamp(vy * 0.78, 0.0, 0.85);
          float cut = (1.0 - smoothstep(cutW - 0.04, cutW + 0.04, gap)) * lowerHalf * step(0.12, vy);
          disc *= 1.0 - cut;
          sunCol = mix(vec3(1.0, 0.86, 0.3), vec3(1.0, 0.12, 0.55), clamp(vy * 0.5 + 0.55, 0.0, 1.0));
        }
        col += sunCol * disc * uSunInt * smoothstep(-0.05, 0.03, h + 0.02);

        // stars + milky-way
        if (uStars > 0.01) {
          vec2 starUV = vec2(atan(d.z, d.x) / 6.2831853 + 0.5, asin(clamp(d.y, -1.0, 1.0)) / 3.1415927 + 0.5);
          vec3 stars = starLayer(starUV, vec2(900.0, 450.0), 0.971, 1.2)
            + starLayer(starUV + vec2(0.173, 0.271), vec2(360.0, 180.0), 0.986, 1.7);
          vec3 axis = normalize(vec3(0.35, 0.75, -0.55));
          float band = exp(-pow(dot(d, axis) * 3.2, 2.0));
          float mw = band * (0.25 + 0.75 * fbm2(d.xz * 5.0 + d.y * 3.0)) * (0.55 + 0.45 * vn3(d * 9.0));
          float dust = smoothstep(0.35, 0.72, vn3(d * 17.0 + 5.0));
          vec3 neb = mix(vec3(0.014, 0.019, 0.03), vec3(0.026, 0.024, 0.032), vn3(d * 4.0 + 2.0)) * mw * (0.6 + dust * 0.4);
          float vis = smoothstep(-0.05, 0.12, h);
          col += (stars + neb) * uStars * mix(vis, 1.0, uLimb);
        }
        // The real Earth mesh supplies the planetary limb. Keep orbital space
        // clear instead of drawing a second glowing horizon and white cloud layer.
        if (uLimb > 0.01) {
          col *= 1.0 - uLimb * smoothstep(0.0, -0.2, h) * 0.18;
        }
        gl_FragColor = vec4(col, 1.0);
      }`,
  });
}
