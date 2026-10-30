"use client";

import { RoundedBox, Sparkles, useGLTF } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { Suspense, useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { mergeGeometries, mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import {
  barkTexture, clamp, clothTextures, concreteTextures, fbm, fbm3, foamTexture, frondTexture, glowTexture, gridFloor, mix, rep, ridged,
  rng, scallopTexture, smoothstep, stripedCanvas, windowTexture, woodTextures,
} from "./proc";
import { world } from "./sky";
import { coastalShader, useCoastalSurface, useCoastalTerrain } from "./coastal";

export const ISLANDS = {
  outpost: new THREE.Vector3(24, 0, -46),
  pandemonium: new THREE.Vector3(23, 0, -84),
  carnival: new THREE.Vector3(24, 0, -121),
};

/** Islands rise out of the sea as the boat approaches and sink once passed (presence computed by the rig). */
function Emerge({ index, children }: { index: number; children: React.ReactNode }) {
  const g = useRef<THREE.Group>(null!);
  useFrame(() => {
    const k = world.islandK[index];
    g.current.visible = k > 0.01;
    g.current.scale.y = Math.max(k, 0.001);
  });
  return <group ref={g}>{children}</group>;
}

/* ----------------------------------------------------------------- utils */
const _c = new THREE.Color();
const hexCache = new Map<string, THREE.Color>();
const hx = (s: string) => { let c = hexCache.get(s); if (!c) { c = new THREE.Color(s); hexCache.set(s, c); } return c; };
const lerpC = (a: string, b: string, t: number) => _c.copy(hx(a)).lerp(hx(b), clamp(t));

function makeTerrain(size: number, seg: number, hFn: (x: number, z: number) => number, cFn: (x: number, z: number, h: number, ny: number) => THREE.Color, uvScale: number) {
  const g = new THREE.PlaneGeometry(size, size, seg, seg);
  g.rotateX(-Math.PI / 2);
  const p = g.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < p.count; i++) p.setY(i, hFn(p.getX(i), p.getZ(i)));
  g.computeVertexNormals();
  const n = g.attributes.normal as THREE.BufferAttribute;
  const uv = g.attributes.uv as THREE.BufferAttribute;
  const col = new Float32Array(p.count * 3);
  for (let i = 0; i < p.count; i++) {
    const c = cFn(p.getX(i), p.getZ(i), p.getY(i), n.getY(i));
    col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
    uv.setXY(i, p.getX(i) / uvScale, p.getZ(i) / uvScale);
  }
  g.setAttribute("color", new THREE.BufferAttribute(col, 3));
  return g;
}

function rockGeo(seed: number, sx = 1, sy = 1, sz = 1, detail = 4) {
  let g: THREE.BufferGeometry = new THREE.IcosahedronGeometry(1, detail);
  g.deleteAttribute("normal"); g.deleteAttribute("uv");
  g = mergeVertices(g, 1e-4);
  const p = g.attributes.position as THREE.BufferAttribute;
  const col = new Float32Array(p.count * 3), uv = new Float32Array(p.count * 2);
  const v = new THREE.Vector3();
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i);
    // Joint planes and a broader upper face give fractured shore rock rather
    // than uniformly rounded, inflated spheres.
    const box = Math.max(Math.abs(v.x), Math.abs(v.y), Math.abs(v.z));
    v.multiplyScalar(1 / Math.pow(Math.max(box, 0.01), 0.26));
    const n = fbm3(v.x * 1.5 + seed, v.y * 1.5, v.z * 1.5 + seed * 0.7, 4);
    const r = 1 + n * 0.26 + (1 - Math.abs(fbm3(v.x * 3 + seed, v.y * 3, v.z * 3, 3))) * 0.08;
    v.multiplyScalar(r);
    v.x = Math.min(v.x, 0.88 - v.y * 0.18);
    v.z = Math.max(v.z, -0.82 + v.y * 0.13);
    v.y = Math.min(v.y, 0.78 + v.x * 0.16 - v.z * 0.11);
    v.x *= sx; v.y *= sy; v.z *= sz;
    if (v.y < -0.25 * sy) v.y = -0.25 * sy + (v.y + 0.25 * sy) * 0.15;
    p.setXYZ(i, v.x, v.y, v.z);
    const strata = Math.sin(v.y * 5.5 + n * 2.5) * 0.5 + 0.5;
    const c = lerpC("#847a6d", "#ada18e", strata * 0.65 + n * 0.25);
    col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
    uv[i * 2] = (Math.atan2(v.z, v.x) / (Math.PI * 2)) * 3; uv[i * 2 + 1] = v.y * 0.5;
  }
  g.setAttribute("color", new THREE.BufferAttribute(col, 3));
  g.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
  g.computeVertexNormals();
  return g;
}

const UP = new THREE.Vector3(0, 1, 0);
const V = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);
function beamGeo(a: THREE.Vector3, b: THREE.Vector3, r: number, seg = 6) {
  const d = b.clone().sub(a);
  const g = new THREE.CylinderGeometry(r, r, d.length(), seg, 1);
  g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(UP, d.normalize()));
  g.translate((a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2);
  return g;
}

/** Sand and rock go dark and glossy where the sea wets them. */
const wetShore = (sh: { vertexShader: string; fragmentShader: string }) => {
  sh.vertexShader = sh.vertexShader
    .replace("#include <common>", "#include <common>\nvarying float vWetY;")
    .replace("#include <worldpos_vertex>", `#include <worldpos_vertex>
      vec4 shorePosition = vec4(transformed, 1.0);
      #ifdef USE_INSTANCING
        shorePosition = instanceMatrix * shorePosition;
      #endif
      vWetY = (modelMatrix * shorePosition).y;`);
  sh.fragmentShader = sh.fragmentShader
    .replace("#include <common>", "#include <common>\nvarying float vWetY;")
    .replace("#include <roughnessmap_fragment>", "#include <roughnessmap_fragment>\nfloat wet = 1.0 - smoothstep(0.04, 0.6, vWetY);\nroughnessFactor = mix(roughnessFactor, 0.16, wet * 0.85);\ndiffuseColor.rgb *= mix(1.0, 0.6, wet);");
};

/** Soft contact shadow under a structure. */
function Blob({ x, y, z, sx, sz, o = 0.5 }: { x: number; y: number; z: number; sx: number; sz: number; o?: number }) {
  const tex = useMemo(() => glowTexture(), []);
  return (
    <mesh position={[x, y, z]} rotation={[-Math.PI / 2, 0, 0]} scale={[sx, sz, 1]} renderOrder={2}>
      <planeGeometry args={[1, 1]} />
      <meshBasicMaterial map={tex} color="#000000" transparent opacity={o} depthWrite={false} polygonOffset polygonOffsetFactor={-4} />
    </mesh>
  );
}

/** Scattered boulders and pebbles along the shore. */
function Debris({ h, seed, count, radius, tint }: { h: (x: number, z: number) => number; seed: number; count: number; radius: [number, number]; tint: string }) {
  const rock = useCoastalSurface("rock");
  const geo = useMemo(() => rockGeo(seed, 1, 0.62, 1, 2), [seed]);
  const ref = useRef<THREE.InstancedMesh>(null!);
  const placed = useMemo(() => {
    const r = rng(seed * 97), out: THREE.Matrix4[] = [];
    for (let i = 0; i < count * 6 && out.length < count; i++) {
      const a = r() * Math.PI * 2, d = radius[0] + r() * (radius[1] - radius[0]);
      const x = Math.cos(a) * d, z = Math.sin(a) * d, y = h(x, z);
      if (y < -0.3 || y > 1.2) continue;
      const sc = 0.12 + Math.pow(r(), 2.5) * 0.55;
      const support = Math.min(y, h(x + sc, z), h(x - sc, z), h(x, z + sc), h(x, z - sc));
      out.push(new THREE.Matrix4().compose(V(x, support - sc * 0.2, z), new THREE.Quaternion().setFromEuler(new THREE.Euler(r() * 0.5, r() * 6.28, r() * 0.5)), V(sc, sc, sc)));
    }
    return out;
  }, [h, seed, count, radius]);
  useLayoutEffect(() => {
    placed.forEach((m, i) => ref.current.setMatrixAt(i, m));
    ref.current.instanceMatrix.needsUpdate = true;
  }, [placed]);
  return (
    <instancedMesh ref={ref} args={[geo, undefined, placed.length]} castShadow receiveShadow>
      <meshStandardMaterial vertexColors color={tint} map={rock.map} normalMap={rock.normalMap} roughness={0.92} onBeforeCompile={wetShore} />
    </instancedMesh>
  );
}

function ShoreGeology({ h, seed, tint }: { h: (x: number, z: number) => number; seed: number; tint: string }) {
  const mesh = useRef<THREE.InstancedMesh>(null!);
  const count = world.compact ? 180 : 540;
  const geometry = useMemo(() => rockGeo(seed, 1, 1, 1, 2), [seed]);
  const texture = useCoastalSurface("rock");
  useLayoutEffect(() => {
    const random = rng(seed), dummy = new THREE.Object3D();
    for (let i = 0; i < count; i++) {
      const angle = random() * Math.PI * 2;
      let radius = 7;
      // Find the actual waterline instead of scattering rocks in a circular ring.
      for (let r = 7; r < 24; r += .2) { if (h(Math.cos(angle) * r, Math.sin(angle) * r) < .15) { radius = r; break; } }
      radius += (random() - .5) * 2.8;
      const x = Math.cos(angle) * radius, z = Math.sin(angle) * radius;
      const size = .07 + Math.pow(random(), 3) * .45;
      // Nest rocks into the lowest supporting ground to avoid floating on cliffs.
      const ground = Math.min(h(x, z), h(x + size, z), h(x - size, z), h(x, z + size), h(x, z - size));
      dummy.position.set(x, ground - size * .12, z);
      dummy.rotation.set(random() * .45, random() * 6.28, random() * .3);
      dummy.scale.set(size * (1.2 + random()), size * (.35 + random() * .6), size);
      dummy.updateMatrix(); mesh.current.setMatrixAt(i, dummy.matrix);
      mesh.current.setColorAt(i, new THREE.Color(tint).multiplyScalar(.65 + random() * .55));
    }
    mesh.current.instanceMatrix.needsUpdate = true;
    if (mesh.current.instanceColor) mesh.current.instanceColor.needsUpdate = true;
    mesh.current.computeBoundingSphere();
  }, [h, seed, count, tint]);
  return <instancedMesh ref={mesh} args={[geometry, undefined, count]} castShadow receiveShadow><meshStandardMaterial map={texture.map} normalMap={texture.normalMap} roughnessMap={texture.roughnessMap} roughness={.92} onBeforeCompile={wetShore} /></instancedMesh>;
}

function CoastalGrass() {
  const ref = useRef<THREE.InstancedMesh>(null!);
  const count = world.compact ? 700 : 2200;
  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const vertices: number[] = [];
    for (let i = 0; i < 3; i++) {
      const a = i * Math.PI / 3, x = Math.cos(a) * .035, z = Math.sin(a) * .035;
      vertices.push(-x, 0, -z, x, 0, z, x * 2.5, .32 + i * .04, z * 2.5);
    }
    g.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
    g.computeVertexNormals(); return g;
  }, []);
  useLayoutEffect(() => {
    const random = rng(867), dummy = new THREE.Object3D();
    let placed = 0;
    for (let attempt = 0; attempt < count * 12 && placed < count; attempt++) {
      const angle = random() * Math.PI * 2, radius = 8.5 + random() * 6;
      const x = Math.cos(angle) * radius, z = Math.sin(angle) * radius, y = carnivalHeight(x, z);
      if (y < .65 || y > 1.75 || Math.hypot(x - WHEEL.x, z - WHEEL.z) < 5 || fbm(x * .9, z * .9, 2) < -.12) continue;
      dummy.position.set(x, y - .025, z);
      dummy.rotation.set(0, random() * Math.PI * 2, (random() - .5) * .25);
      dummy.scale.setScalar(.5 + random() * .75); dummy.updateMatrix();
      ref.current.setMatrixAt(placed, dummy.matrix);
      ref.current.setColorAt(placed, new THREE.Color().lerpColors(hx("#525b32"), hx("#a59b62"), random()));
      placed++;
    }
    ref.current.count = placed; ref.current.instanceMatrix.needsUpdate = true;
    if (ref.current.instanceColor) ref.current.instanceColor.needsUpdate = true;
    ref.current.computeBoundingSphere();
  }, [count]);
  return <instancedMesh ref={ref} args={[geometry, undefined, count]} receiveShadow><meshStandardMaterial roughness={1} side={THREE.DoubleSide} /></instancedMesh>;
}

function Foam({ h, extent }: { h: (x: number, z: number) => number; extent: number }) {
  const tex = useMemo(() => foamTexture(h, extent, 256), [h, extent]);
  const mat = useRef<THREE.MeshBasicMaterial>(null!);
  useFrame(() => { if (mat.current) mat.current.opacity = 0.28 + Math.sin(world.time * 0.9) * 0.09; });
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.035, 0]}>
      <planeGeometry args={[extent, extent]} />
      <meshBasicMaterial ref={mat} map={tex} transparent depthWrite={false} color="#fff6e8" />
    </mesh>
  );
}

/* ================================================================ ISLAND I */
const PAD = { x: 3.2, z: 3.4 };
export const OUTPOST_PAD = PAD;
function duneHeight(x: number, z: number) {
  const r = Math.hypot(x, z);
  const R = 13 + fbm(x * 0.07 + 11, z * 0.07 + 5, 3) * 3.2;
  const m = smoothstep(R + 3.4, R - 4.2, r);
  const a = 0.5, cx = x * Math.cos(a) - z * Math.sin(a), cz = x * Math.sin(a) + z * Math.cos(a);
  const warp = fbm(cx * 0.05, cz * 0.05, 3) * 6;
  const crest = Math.pow(1 - Math.abs(Math.sin(cx * 0.17 + warp)), 2.4);
  const big = fbm(x * 0.045 + 4, z * 0.045, 4) * 0.5 + 0.5;
  let h = -2.4 + m * (2.9 + big * 1.5 + crest * 1.35 + fbm(x * 0.35, z * 0.35, 2) * 0.1);
  const mesa = (cx0: number, cz0: number, rad: number, ht: number) => {
    const d = Math.hypot((x - cx0) * 0.91, (z - cz0) * 1.06) + fbm(x * 0.11, z * 0.11, 3) * 1.2;
    // A broad cap with asymmetric eroded talus; avoid quantised height steps,
    // which made the old mesa walls look like melted vertical ribbons.
    const profile = smoothstep(rad + 2.6, rad - 0.6, d);
    const scarp = Math.pow(profile, 0.62) * ht;
    const ledge = Math.sin(scarp * 3.7 + fbm(x * 0.13, z * 0.13, 2) * 1.6) * 0.09;
    return scarp + ledge * smoothstep(0.0, 0.2, profile) * (1 - smoothstep(0.7, 1, profile));
  };
  const mesas = mesa(-5.5, -6.2, 4.6, 7.4) + mesa(7.8, -7.6, 2.8, 4.6) + mesa(-9.4, 3.2, 2.2, 3.6);
  // Bedrock caps stay broad; wind ripples belong on the dunes below them.
  h = mix(h, 1.0 + fbm(x * 0.075, z * 0.075, 2) * 0.15, smoothstep(2.8, 5.2, mesas)) + mesas * m;
  // wind erosion: gullies cut into the mesa walls
  h -= Math.pow(ridged(x * 0.21, z * 0.21, 3), 3) * 0.48 * smoothstep(0.6, 3.5, mesas) * m;
  // Support the citadel's complete rotated plinth, including its corners.
  const pad = smoothstep(10.0, 7.8, Math.hypot(x - PAD.x, z - PAD.z));
  const shelf = mix(h, 2.5, pad);
  const exposed = (1 - pad) * m;
  const fracture = fbm(x * 1.7 + 18, z * 1.7, 3) * .16 + fbm(x * 4.5, z * 4.5 + 8, 2) * .045;
  const channels = Math.pow(ridged(x * .8 + 12, z * .8, 3), 5) * .38;
  return shelf + exposed * (fracture - channels * smoothstep(1.5, 4, mesas));
}
function duneColor(x: number, z: number, h: number, ny: number) {
  const grain = fbm(x * 0.9, z * 0.9, 2) * 0.5 + 0.5;
  const big = fbm(x * 0.06, z * 0.06, 3) * 0.5 + 0.5;
  const sand = lerpC("#d9c29d", "#c9af89", big * 0.7 + grain * 0.3).clone();
  const crestHi = smoothstep(0.9, 1, ny) * 0.0;
  sand.lerp(hx("#f6dca8"), crestHi);
  const strata = Math.sin(h * 3.4 + fbm(x * 0.13, z * 0.13, 3) * 1.5) * 0.5 + 0.5;
  const rock = lerpC("#9c826b", "#bca184", strata * 0.65 + big * 0.35).clone().multiplyScalar(0.9 + grain * 0.2);
  const rockness = clamp(smoothstep(0.86, 0.62, ny) + smoothstep(4.2, 6, h) * 0.5);
  const col = sand.lerp(rock, rockness);
  const wet = smoothstep(0.35, -0.3, h);
  col.lerp(hx("#6e5236"), wet * 0.8);
  col.lerp(hx("#2f4a47"), smoothstep(-0.4, -1.8, h) * 0.8);
  return col;
}

/** Blender-authored Dune citadel (blender/outpost.py): baked PBR atlas, single draw call. */
useGLTF.preload("/models/outpost-realistic.glb");
function Citadel() {
  const { scene } = useGLTF("/models/outpost-realistic.glb");
  const model = useMemo(() => {
    const m = scene.clone(true);
    m.traverse((o) => { const mesh = o as THREE.Mesh; if (mesh.isMesh) { mesh.castShadow = true; mesh.receiveShadow = true; } });
    return m;
  }, [scene]);
  return <primitive object={model} position={[PAD.x, 2.42, PAD.z]} rotation={[0, -0.42, 0]} />;
}

function Outpost() {
  const sand = useCoastalTerrain("desert");
  const conc = useMemo(() => concreteTextures(), []);
  const rock = useCoastalSurface("rock");
  const compact = world.compact;
  const geo = useMemo(() => makeTerrain(46, compact ? 192 : 384, duneHeight, duneColor, 11), [compact]);
  const rocks = useMemo(() => [
    { g: rockGeo(1.2, 1.6, 2.4, 1.3), p: [-12.4, -0.6, 4.6] as const, s: 1 },
    { g: rockGeo(4.8, 1.2, 1.5, 1.1), p: [10.6, -0.5, 7.4] as const, s: 1 },
    { g: rockGeo(9.1, 0.9, 1.9, 0.9), p: [-3.4, -0.4, 13.4] as const, s: 1 },
    { g: rockGeo(2.7, 0.7, 0.8, 0.7), p: [6.4, 0.3, -12.8] as const, s: 1 },
  ], []);
  const blink = useRef<THREE.MeshBasicMaterial>(null!);
  const concMat = useMemo(() => ({ color: "#d2a574", map: rep(conc.map, 1.5, 1), normalMap: rep(conc.normalMap, 1.5, 1) }), [conc]);
  const slit = <meshStandardMaterial color="#2a160a" emissive="#ffb35a" emissiveIntensity={3.2} toneMapped={false} />;
  useFrame(() => { if (blink.current) blink.current.color.setScalar(Math.sin(world.time * 2.6) > 0.55 || world.reduced ? 6 : 0.15).multiply(hx("#ff2a1a")); });
  const surface = <meshStandardMaterial {...concMat} roughness={0.92} />;
  return (
    <group position={ISLANDS.outpost}>
      <mesh geometry={geo} receiveShadow castShadow>
        <meshStandardMaterial vertexColors {...sand} normalScale={new THREE.Vector2(0.65, 0.65)} roughness={1} metalness={0} />
      </mesh>
      <Foam h={duneHeight} extent={46} />
      {rocks.map((r, i) => (
        <mesh key={i} geometry={r.g} position={[...r.p]} castShadow receiveShadow>
          <meshStandardMaterial vertexColors {...rock} color="#c5bfb4" roughness={1} onBeforeCompile={coastalShader} />
        </mesh>
      ))}
      <Debris h={duneHeight} seed={3} count={compact ? 30 : 70} radius={[9, 17]} tint="#c99a74" />
      <ShoreGeology h={duneHeight} seed={31} tint="#9b7556" />
      <Blob x={PAD.x} y={2.53} z={PAD.z} sx={9} sz={6} o={0.45} />

      <Suspense fallback={null}><Citadel /></Suspense>

      {!world.reduced && <Sparkles count={compact ? 20 : 45} scale={[30, 6, 26]} position={[0, 3, 0]} size={1.1} speed={0.22} color="#ddd3be" opacity={0.14} noise={1.2} />}
    </group>
  );
}

/* ================================================================ ISLAND II */
function cityHeight(x: number, z: number) {
  const r = Math.hypot(x, z);
  const R = 10.8 + fbm(x * 0.12, z * 0.12, 3) * 1.4;
  const cliff = smoothstep(R + 2.4, R - 0.4, r);
  return (fbm(x * 2.4, z * 2.4, 3) * .12 * smoothstep(.1, .6, cliff)) + mix(-3.4, 0.9, cliff) + fbm(x * 0.55, z * 0.55, 3) * 0.55 * (1 - smoothstep(0.7, 1, cliff) * 0) * smoothstep(0.05, 0.5, cliff);
}
function cityColor(x: number, z: number, h: number, ny: number) {
  const n = fbm(x * 0.4, z * 0.4, 3) * 0.5 + 0.5;
  const c = lerpC("#1b1727", "#33284a", n).clone();
  c.lerp(hx("#4a2a66"), smoothstep(0.8, 0.95, ny) * 0.4);
  c.lerp(hx("#0a2a3a"), smoothstep(-0.3, -1.6, h) * 0.8);
  return c;
}

function buildTowers() {
  const r = rng(21);
  const groups: THREE.BufferGeometry[][] = [[], [], []];
  const neon: THREE.BufferGeometry[][] = [[], [], []];
  const place: { x: number; z: number; h: number; w: number; d: number; i: number }[] = [];
  let idx = 0;
  for (let gx = -4; gx <= 4; gx++) for (let gz = -4; gz <= 4; gz++) {
    const x = gx * 2.45 + (r() - 0.5) * 0.5, z = gz * 2.45 + (r() - 0.5) * 0.5;
    const rad = Math.hypot(x, z);
    if (rad > 9.4 || (gx === 3 && gz === 3) || r() < 0.12) continue;
    const core = Math.exp(-Math.pow(rad / 6.3, 2));
    const h = 2.6 + core * (9 + r() * 7) + r() * 2.5;
    const w = 1.2 + r() * 0.9, d = 1.2 + r() * 0.9;
    place.push({ x, z, h, w, d, i: idx++ });
  }
  const scaleUV = (g: THREE.BoxGeometry, w: number, h: number, d: number) => {
    const uv = g.attributes.uv as THREE.BufferAttribute, n = g.attributes.normal as THREE.BufferAttribute;
    for (let i = 0; i < uv.count; i++) {
      if (Math.abs(n.getY(i)) > 0.5) { uv.setXY(i, 0.01, 0.01); continue; }
      const across = Math.abs(n.getX(i)) > 0.5 ? d : w;
      uv.setXY(i, uv.getX(i) * across / 3.4, uv.getY(i) * h / 3.4);
    }
  };
  for (const t of place) {
    const k = t.i % 3;
    const b = new THREE.BoxGeometry(t.w, t.h, t.d); scaleUV(b, t.w, t.h, t.d); b.translate(t.x, t.h / 2 + 0.9, t.z);
    groups[k].push(b);
    let top = t.h;
    if (r() < 0.55 && t.h > 4.5) {
      const h2 = 1.2 + r() * 2.4, w2 = t.w * 0.64, d2 = t.d * 0.64;
      const b2 = new THREE.BoxGeometry(w2, h2, d2); scaleUV(b2, w2, h2, d2); b2.translate(t.x, t.h + h2 / 2 + 0.9, t.z);
      groups[k].push(b2); top += h2;
      const ring = new THREE.BoxGeometry(t.w + 0.12, 0.09, t.d + 0.12); ring.translate(t.x, t.h + 0.9, t.z); neon[k].push(ring);
    }
    if (r() < 0.6) {
      for (let j = 0; j < 2; j++) {
        const u = new THREE.BoxGeometry(0.3 + r() * 0.3, 0.22 + r() * 0.2, 0.3 + r() * 0.3);
        u.translate(t.x + (r() - 0.5) * t.w * 0.5, top + 1.0 + 0.1, t.z + (r() - 0.5) * t.d * 0.5);
        const uvs = u.attributes.uv as THREE.BufferAttribute; for (let q = 0; q < uvs.count; q++) uvs.setXY(q, 0.01, 0.01);
        groups[k].push(u);
      }
    }
    if (r() < 0.5) {
      const ant = new THREE.CylinderGeometry(0.025, 0.04, 2 + r() * 2, 6); ant.translate(t.x, top + 0.9 + 1.3, t.z);
      const uv = ant.attributes.uv as THREE.BufferAttribute; for (let i = 0; i < uv.count; i++) uv.setXY(i, 0.01, 0.01);
      groups[k].push(ant);
    }
    if (r() < 0.38) {
      const s = r() < 0.5 ? -1 : 1;
      const strip = new THREE.BoxGeometry(0.07, t.h * 0.92, 0.07); strip.translate(t.x + s * t.w / 2, t.h / 2 + 0.9, t.z + t.d / 2); neon[k].push(strip);
    }
  }
  return { towers: groups.map((g) => mergeGeometries(g)!), neon: neon.map((g) => (g.length ? mergeGeometries(g)! : new THREE.BufferGeometry())), place };
}

/** Blender-authored skyline (blender/city.py). Tower_0/1/2 get the tiling lit-window emissive map in each neon hue. */
useGLTF.preload("/models/city-realistic.glb");
function Skyline({ win }: { win: THREE.Texture }) {
  const { scene } = useGLTF("/models/city-realistic.glb");
  const model = useMemo(() => {
    const m = scene.clone(true);
    const hues = ["#ff2ea6", "#27e6ff", "#9a5bff"];
    const seen = new Set<THREE.Material>();
    m.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      mesh.castShadow = true; mesh.receiveShadow = true;
      const mat = mesh.material as THREE.MeshStandardMaterial;
      if (seen.has(mat)) return;
      seen.add(mat);
      const t = /^Tower_(\d)$/.exec(mat.name);
      if (t) { mat.emissive = new THREE.Color(hues[+t[1]]); mat.emissiveMap = win; mat.emissiveIntensity = 1.45; }
      else if (mat.name.startsWith("Neon_") || mat.name === "Beacon") { mat.toneMapped = false; mat.emissiveIntensity = 3.2; }
      mat.needsUpdate = true;
    });
    return m;
  }, [scene, win]);
  return <primitive object={model} position={[0, 1.07, 0]} />;
}

function Pandemonium() {
  const rock = useCoastalSurface("rock");
  const concrete = useCoastalSurface("concrete");
  const win = useMemo(() => windowTexture(), []);
  const grid = useMemo(() => gridFloor(), []);
  const compact = world.compact;
  const terrain = useMemo(() => makeTerrain(40, compact ? 160 : 320, cityHeight, cityColor, 8), [compact]);
  const deckGrid = useMemo(() => rep(grid, 5, 5), [grid]);
  const beams = useRef<THREE.Group>(null!);
  const holo = useRef<THREE.Mesh>(null!);
  const glow = useMemo(() => glowTexture(), []);
  useFrame(() => {
    const t = world.time;
    if (beams.current) { beams.current.rotation.y = t * 0.35; }
    if (holo.current) { holo.current.rotation.z = t * 0.5; holo.current.rotation.x = Math.PI / 2 + Math.sin(t * 0.7) * 0.15; }
  });
  return (
    <group position={ISLANDS.pandemonium}>
      <mesh geometry={terrain} receiveShadow castShadow>
        <meshStandardMaterial vertexColors {...rock} roughness={1} metalness={0} onBeforeCompile={coastalShader} />
      </mesh>
      <Foam h={cityHeight} extent={40} />
      <mesh position={[0, 0.98, 0]} receiveShadow>
        <cylinderGeometry args={[10.4, 10.9, 0.18, 72]} />
        <meshStandardMaterial color="#3d3e45" {...concrete} metalness={0.08} roughness={0.8} emissive="#b0289a" emissiveMap={deckGrid} emissiveIntensity={0.18} />
      </mesh>
      <Suspense fallback={null}><Skyline win={win} /></Suspense>
      <mesh ref={holo} position={[0, 21, 0]}><torusGeometry args={[2.6, 0.035, 8, 80]} /><meshBasicMaterial color={hx("#27e6ff").clone().multiplyScalar(3)} toneMapped={false} /></mesh>
      <group ref={beams} position={[0, 1.2, 0]}>
        {[0, Math.PI].map((a, i) => (
          <mesh key={i} position={[Math.cos(a) * 0.4, 14, Math.sin(a) * 0.4]} rotation={[Math.cos(a) * 0.35, 0, -Math.sin(a) * 0.35 + 0.0]}>
            <cylinderGeometry args={[0.05, 1.1, 28, 20, 1, true]} />
            <meshBasicMaterial color={i ? "#27e6ff" : "#ff2ea6"} transparent opacity={0.07} depthWrite={false} blending={THREE.AdditiveBlending} side={THREE.DoubleSide} toneMapped={false} />
          </mesh>
        ))}
      </group>
      <sprite position={[0, 5, 0]} scale={[26, 18, 1]}><spriteMaterial map={glow} color="#c42a9a" transparent opacity={0.25} blending={THREE.AdditiveBlending} depthWrite={false} /></sprite>
      <Debris h={cityHeight} seed={11} count={compact ? 20 : 45} radius={[10, 13.5]} tint="#5a4e6a" />
      <ShoreGeology h={cityHeight} seed={47} tint="#5e626d" />
      {!world.reduced && <Sparkles count={compact ? 12 : 28} scale={[26, 14, 24]} position={[0, 7, 0]} size={0.9} speed={0.2} color="#b8bbce" opacity={0.14} />}
    </group>
  );
}

/* ================================================================ ISLAND III */
const WHEEL = { x: 2.6, z: -2.2 };
export const CARNIVAL_WHEEL = WHEEL;
function carnivalHeight(x: number, z: number) {
  const r = Math.hypot(x, z);
  const R = 12.4 + fbm(x * 0.09 + 3, z * 0.09, 3) * 2.2;
  const m = smoothstep(R + 3, R - 3.6, r);
  const hills = fbm(x * 0.09, z * 0.09, 4) * 0.9 + fbm(x * 0.28, z * 0.28, 2) * 0.14;
  let h = mix(-2.5, 0.85, m) + m * (hills + 0.55);
  h += m * (fbm(x * 1.8, z * 1.8, 3) * .07 + fbm(x * 5, z * 5, 2) * .025);
  h += smoothstep(3.2, 1.2, Math.hypot(x + 9.5, z + 4)) * 2.2 * m;
  return mix(h, 1.05, smoothstep(4.6, 3.0, Math.hypot(x - WHEEL.x, z - WHEEL.z)));
}
function carnivalColor(x: number, z: number, h: number, ny: number) {
  const n = fbm(x * 0.3, z * 0.3, 3) * 0.5 + 0.5;
  const grass = lerpC("#657153", "#8c9068", n).clone();
  const beach = lerpC("#d5c5a4", "#b9a07b", n).clone();
  const c = grass.lerp(beach, smoothstep(0.75, 0.3, h + fbm(x * 0.6, z * 0.6, 2) * 0.2));
  c.lerp(hx("#6b5a4a"), smoothstep(0.84, 0.6, ny));
  c.lerp(hx("#715a3f"), smoothstep(0.25, -0.25, h) * 0.8);
  c.lerp(hx("#2c4f55"), smoothstep(-0.4, -1.8, h) * 0.8);
  return c;
}

/** Blender-authored wheel (blender/wheel.py): static frame, a rotor that spins, and 12 gondolas kept upright. */
useGLTF.preload("/models/wheel-realistic.glb");
function FerrisWheel() {
  const { scene } = useGLTF("/models/wheel-realistic.glb");
  const model = useMemo(() => {
    const m = scene.clone(true);
    m.traverse((o) => { const mesh = o as THREE.Mesh; if (mesh.isMesh) { mesh.castShadow = true; mesh.receiveShadow = true; } });
    return m;
  }, [scene]);
  const rotor = useMemo(() => model.getObjectByName("Wheel_Rotor") as THREE.Object3D, [model]);
  const cabins = useMemo(() => Array.from({ length: 12 }, (_, i) => model.getObjectByName(`Cab${i}`) as THREE.Object3D), [model]);
  const lampMat = useMemo(() => {
    let mat: THREE.MeshStandardMaterial | null = null;
    rotor.traverse((o) => { const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined; if (m && m.emissiveMap) mat = m; });
    return mat as THREE.MeshStandardMaterial | null;
  }, [rotor]);
  useFrame(() => {
    const spin = 0.07 + Math.min(Math.abs(world.velocity) / 2800, 0.6);
    rotor.rotation.z -= world.dt * spin;
    cabins.forEach((c) => c && (c.rotation.z = -rotor.rotation.z));
    if (lampMat) lampMat.emissiveIntensity = 1.1 + Math.sin(world.time * 3) * 0.45;
  });
  return <primitive object={model} position={[WHEEL.x, 1.05, WHEEL.z]} rotation={[0, -0.28, 0]} />;
}

function Palm({ x, z, seed, ground }: { x: number; z: number; seed: number; ground: number }) {
  const frond = useMemo(() => frondTexture(), []);
  const bark = useMemo(() => rep(barkTexture(), 6, 1), []);
  const { trunk, fronds } = useMemo(() => {
    const r = rng(seed * 31);
    const lean = (r() - 0.5) * 1.6, hgt = 4.4 + r() * 1.6, dir = r() * 6.28;
    const pts = [0, 0.33, 0.66, 1].map((t) => new THREE.Vector3(Math.cos(dir) * lean * t * t * 1.2, t * hgt, Math.sin(dir) * lean * t * t * 1.2));
    const trunk = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 14, 0.15, 8);
    const top = pts[3];
    const fronds = Array.from({ length: 10 }, (_, i) => ({ a: (i / 10) * Math.PI * 2 + r() * 0.3, tilt: 0.35 + r() * 0.5, s: 0.85 + r() * 0.4, top }));
    return { trunk, fronds };
  }, [seed]);
  const fg = useMemo(() => {
    const g = new THREE.PlaneGeometry(2.9, 1.15, 8, 2);
    g.translate(1.45, 0, 0);
    const p = g.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < p.count; i++) p.setY(i, p.getY(i) - Math.pow(p.getX(i) / 2.9, 2) * 1.35);
    g.computeVertexNormals();
    return g;
  }, []);
  return (
    <group position={[x, ground, z]}>
      <mesh geometry={trunk} castShadow><meshStandardMaterial map={bark} color="#b49a7c" roughness={0.95} /></mesh>
      {[0, 2.1, 4.2].map((a) => <mesh key={a} position={[fronds[0].top.x + Math.cos(a) * 0.17, fronds[0].top.y - 0.18, fronds[0].top.z + Math.sin(a) * 0.17]} castShadow><sphereGeometry args={[0.14, 12, 10]} /><meshStandardMaterial color="#5a4128" roughness={0.7} /></mesh>)}
      {fronds.map((f, i) => (
        <mesh key={i} geometry={fg} position={f.top} rotation={[0, f.a, f.tilt]} scale={f.s} castShadow>
          <meshStandardMaterial map={frond} alphaTest={0.4} side={THREE.DoubleSide} roughness={0.8} color="#ffffff" />
        </mesh>
      ))}
    </group>
  );
}

function tentRoof(radius: number, height: number) {
  const geometry = new THREE.ConeGeometry(radius, height, 64, 16, true);
  const p = geometry.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const r = clamp(Math.hypot(p.getX(i), p.getZ(i)) / radius);
    const angle = Math.atan2(p.getZ(i), p.getX(i));
    // Tension at the mast and perimeter ropes, with shallow sag between ribs.
    p.setY(i, height * (Math.pow(1 - r, 1.18) - 0.5)
      - Math.pow(Math.sin(angle * 8), 2) * Math.sin(Math.PI * r) * 0.12);
  }
  geometry.computeVertexNormals();
  return geometry;
}

function Carnival() {
  const wood = useMemo(() => woodTextures(), []);
  const fabric = useMemo(() => clothTextures(), []);
  const bigRoof = useMemo(() => tentRoof(3, 2.5), []);
  const smallRoof = useMemo(() => tentRoof(1.35, 1.2), []);
  const sand = useCoastalTerrain("meadow");
  const compact = world.compact;
  const terrain = useMemo(() => makeTerrain(46, compact ? 160 : 320, carnivalHeight, carnivalColor, 10), [compact]);
  const stripeA = useMemo(() => stripedCanvas("#d4362d", "#f3e7cf", 14), []);
  const stripeB = useMemo(() => stripedCanvas("#f0a52a", "#f3e7cf", 10), []);
  const stripeC = useMemo(() => stripedCanvas("#2a9db4", "#f3e7cf", 10), []);
  const plank = useMemo(() => rep(wood.map, 1, 3), [wood]);
  const plankN = useMemo(() => rep(wood.normalMap, 1, 3), [wood]);
  const glow = useMemo(() => glowTexture(), []);
  const valance = useMemo(() => rep(scallopTexture("#d4362d", "#f3e7cf"), 6, 1), []);
  const guyRopes = useMemo(() => mergeGeometries(Array.from({ length: 8 }, (_, i) => {
    const a = (i / 8) * Math.PI * 2 + 0.2;
    return beamGeo(V(Math.cos(a) * 3.0, 1.72, Math.sin(a) * 3.0), V(Math.cos(a) * 4.3, -0.05, Math.sin(a) * 4.3), 0.012, 4);
  }))!, []);
  const palms = useMemo(() => {
    const r = rng(8), out: { x: number; z: number; g: number; s: number }[] = [];
    for (let i = 0; i < 9; i++) {
      const a = r() * Math.PI * 2, rad = 7 + r() * 6.5;
      const x = Math.cos(a) * rad, z = Math.sin(a) * rad, h = carnivalHeight(x, z);
      if (h > 0.25 && h < 1.4 && Math.hypot(x - WHEEL.x, z - WHEEL.z) > 7) out.push({ x, z, g: h - 0.05, s: i + 1 });
    }
    return out;
  }, []);
  const bulbs = useRef<THREE.InstancedMesh>(null!);
  const strands = useMemo(() => {
    const defs: [number[], number[]][] = [[[-6, 4.6, 5], [-1, 4.8, 8]], [[-1, 4.8, 8], [5.5, 3.8, 6]], [[-6, 4.6, 5], [-8, 3.2, -2]], [[5.5, 3.8, 6], [9, 3.4, 1]]];
    const pts: THREE.Vector3[] = [];
    const lines: THREE.BufferGeometry[] = [];
    for (const [A, B] of defs) {
      const curve: THREE.Vector3[] = [];
      for (let i = 0; i <= 14; i++) {
        const t = i / 14;
        const v = new THREE.Vector3(mix(A[0], B[0], t), mix(A[1], B[1], t) - Math.sin(Math.PI * t) * 0.9, mix(A[2], B[2], t));
        curve.push(v); if (i > 0 && i < 14) pts.push(v);
      }
      lines.push(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(curve), 24, 0.012, 4));
    }
    return { pts, lines: mergeGeometries(lines)! };
  }, []);
  useFrame(() => {
    if (!bulbs.current) return;
    const m = new THREE.Matrix4();
    strands.pts.forEach((p, i) => bulbs.current.setMatrixAt(i, m.makeTranslation(p.x, p.y - 0.06, p.z)));
    bulbs.current.instanceMatrix.needsUpdate = true;
    (bulbs.current.material as THREE.MeshBasicMaterial).color.copy(hx("#ffc873")).multiplyScalar(2.2 + Math.sin(world.time * 2.3) * 0.4);
  });
  const striped = (map: THREE.Texture) => <meshStandardMaterial map={map} normalMap={fabric.normalMap} normalScale={new THREE.Vector2(0.16, 0.16)} roughness={0.88} side={THREE.DoubleSide} emissive="#ff9a4a" emissiveIntensity={0.035} />;
  return (
    <group position={ISLANDS.carnival}>
      <mesh geometry={terrain} receiveShadow castShadow>
        <meshStandardMaterial vertexColors {...sand} normalScale={new THREE.Vector2(0.6, 0.6)} roughness={1} />
      </mesh>
      <Foam h={carnivalHeight} extent={46} />
      <Suspense fallback={null}><FerrisWheel /></Suspense>

      {/* big top */}
      <group position={[-5.2, 0.9, 5.4]}>
        <mesh position={[0, 0.85, 0]} castShadow receiveShadow><cylinderGeometry args={[2.7, 2.7, 1.7, 28, 1, true]} />{striped(stripeA)}</mesh>
        <mesh position={[0, 2.95, 0]} geometry={bigRoof} castShadow>{striped(stripeA)}</mesh>
        <mesh position={[0, 1.5, 0]}><cylinderGeometry args={[3.04, 3.04, 0.42, 40, 1, true]} /><meshStandardMaterial map={valance} alphaTest={0.5} side={THREE.DoubleSide} roughness={0.75} /></mesh>
        <mesh geometry={guyRopes}><meshStandardMaterial color="#d8c9a6" roughness={0.9} /></mesh>
        <mesh position={[0, 4.5, 0]}><cylinderGeometry args={[0.03, 0.03, 1.4, 6]} /><meshStandardMaterial color="#d9c9a5" /></mesh>
        <mesh position={[0.3, 5.0, 0]}><planeGeometry args={[0.6, 0.32]} /><meshStandardMaterial color="#ffb703" side={THREE.DoubleSide} emissive="#ff8a00" emissiveIntensity={0.4} /></mesh>
        <mesh position={[0, 0.9, 2.67]}><planeGeometry args={[1.1, 1.5]} /><meshBasicMaterial color={hx("#ffb869").clone().multiplyScalar(1.6)} toneMapped={false} /></mesh>
      </group>
      {/* small tents */}
      {[[-9.4, 0.55, -0.8, stripeB, 1.4], [6.8, 0.9, 6.2, stripeC, 1.7]].map(([x, y, z, tex, s], i) => (
        <group key={i} position={[x as number, y as number, z as number]} scale={s as number}>
          <mesh position={[0, 0.5, 0]} castShadow><cylinderGeometry args={[1.2, 1.2, 1, 20, 1, true]} />{striped(tex as THREE.Texture)}</mesh>
          <mesh position={[0, 1.55, 0]} geometry={smallRoof} castShadow>{striped(tex as THREE.Texture)}</mesh>
        </group>
      ))}
      {/* booths */}
      {[[1.5, 1.0, 7.4, 0.2], [-1.4, 0.95, 9.0, -0.1]].map(([x, y, z, r], i) => (
        <group key={i} position={[x, y, z]} rotation={[0, r, 0]}>
          <RoundedBox args={[1.9, 1.3, 1.2]} radius={0.04} position={[0, 0.65, 0]} castShadow><meshStandardMaterial color="#8d6a4a" map={plank} roughness={0.8} /></RoundedBox>
          <mesh position={[0, 1.55, 0.35]} rotation={[0.45, 0, 0]} castShadow><boxGeometry args={[2.2, 0.06, 1.2]} /><meshStandardMaterial map={stripeA} roughness={0.8} /></mesh>
          <mesh position={[0, 0.85, 0.62]}><planeGeometry args={[1.5, 0.4]} /><meshBasicMaterial color={hx("#ffcf7a").clone().multiplyScalar(1.4)} toneMapped={false} /></mesh>
        </group>
      ))}
      {/* string lights */}
      <mesh geometry={strands.lines}><meshStandardMaterial color="#1a1512" roughness={0.9} /></mesh>
      <instancedMesh ref={bulbs} args={[undefined, undefined, strands.pts.length]}><sphereGeometry args={[0.085, 10, 8]} /><meshBasicMaterial toneMapped={false} color="#ffc873" /></instancedMesh>
      {[[-6, 5], [-1, 8], [5.5, 6], [-8, -2], [9, 1]].map(([x, z], i) => (
        <mesh key={i} position={[x, 2.4, z]} castShadow><cylinderGeometry args={[0.07, 0.09, 4.6 + (i === 1 ? 0.6 : 0), 8]} /><meshStandardMaterial color="#5a4330" roughness={0.9} /></mesh>
      ))}
      {/* pier */}
      <group position={[-7.6, 0.55, 13.5]}>
        {Array.from({ length: 22 }).map((_, i) => (
          <mesh key={i} position={[0, 0, i * 0.55]} receiveShadow castShadow><boxGeometry args={[2.3, 0.12, 0.5]} /><meshStandardMaterial color="#9a7550" map={plank} normalMap={plankN} roughness={0.85} /></mesh>
        ))}
        {Array.from({ length: 8 }).map((_, i) => [-1, 1].map((s) => (
          <mesh key={`${i}${s}`} position={[s * 1.1, -0.9, i * 1.5]} castShadow><cylinderGeometry args={[0.09, 0.1, 2.6, 8]} /><meshStandardMaterial color="#4a3827" roughness={0.9} /></mesh>
        )))}
        {[0, 7].map((i) => <mesh key={i} position={[1.1, 0.9, i * 1.5]}><sphereGeometry args={[0.1, 10, 8]} /><meshBasicMaterial toneMapped={false} color={hx("#ffc873").clone().multiplyScalar(2.6)} /></mesh>)}
      </group>
      {palms.map((p) => <Palm key={p.s} x={p.x} z={p.z} ground={p.g} seed={p.s} />)}

      <Debris h={carnivalHeight} seed={7} count={compact ? 24 : 55} radius={[10, 16]} tint="#b6a08a" />
      <ShoreGeology h={carnivalHeight} seed={63} tint="#827d69" />
      <CoastalGrass />
      <Blob x={WHEEL.x} y={1.08} z={WHEEL.z} sx={10} sz={6} o={0.42} />
      <Blob x={-5.2} y={0.95} z={5.4} sx={7.5} sz={7.5} o={0.4} />
      <sprite position={[WHEEL.x, 8.5, WHEEL.z]} scale={[18, 18, 1]}><spriteMaterial map={glow} color="#ff9a3a" transparent opacity={0.2} blending={THREE.AdditiveBlending} depthWrite={false} /></sprite>
      {!world.reduced && <Sparkles count={compact ? 15 : 30} scale={[28, 9, 24]} position={[0, 5, 0]} size={1.3} speed={0.2} color="#ffd8a4" opacity={0.18} />}
    </group>
  );
}

export default function Islands() {
  return (
    <>
      <Emerge index={0}><Outpost /></Emerge>
      <Emerge index={1}><Pandemonium /></Emerge>
      <Emerge index={2}><Carnival /></Emerge>
    </>
  );
}
