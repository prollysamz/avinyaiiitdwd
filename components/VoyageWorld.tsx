"use client";

import { PerformanceMonitor } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Bloom, EffectComposer, ToneMapping, Vignette } from "@react-three/postprocessing";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { ToneMappingMode } from "postprocessing";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import Boat from "./world/Boat";
import Islands, { CARNIVAL_WHEEL, ISLANDS, OUTPOST_PAD } from "./world/Islands";
import { Ocean } from "./world/Ocean";
import { smoothstep } from "./world/proc";
import { oceanGeometry } from "./world/waves";
import { blendPreset, createSkyMaterial, world } from "./world/sky";
import Space, { SPACE } from "./world/Space";

declare global {
  interface Window { __voyageProgress?: number; __voyageVelocity?: number; }
}

/* ---------------------------------------------------------- quality tiers */
/** envStep: how far the sky phase must move before the environment map is re-rendered */
interface Tier { dpr: [number, number]; mirror: number; mirrorEvery: number; shadow: number; msaa: number; envStep: number; bloom: number }
const TIERS: Tier[] = [
  { dpr: [0.7, 1], mirror: 256, mirrorEvery: 2, shadow: 0, msaa: 0, envStep: 0.12, bloom: 0.4 },
  { dpr: [1, 1.25], mirror: 512, mirrorEvery: 1, shadow: 1024, msaa: 2, envStep: 0.06, bloom: 0.55 },
  { dpr: [1, 1.6], mirror: 1024, mirrorEvery: 1, shadow: 2048, msaa: 4, envStep: 0.035, bloom: 0.6 },
];

function detectTier(): number {
  const phone = window.matchMedia("(max-width: 720px)").matches || window.matchMedia("(pointer: coarse)").matches;
  if (phone) return 0;
  const cores = navigator.hardwareConcurrency || 4;
  const mem = (navigator as Navigator & { deviceMemory?: number }).deviceMemory || 8;
  return cores <= 4 || mem <= 4 ? 1 : 2;
}

/* --------------------------------------------------------- camera journey */
const v3 = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);
/** `boat` = how far right of the view axis the boat sails, keeping it clear of the left-hand copy column. */
interface Pose { pos: THREE.Vector3; look: THREE.Vector3; phase: number; boat: number }
/** How far the camera backs off along its sight line on the narrowest (portrait) screens, so a whole island fits. */
const PORTRAIT_PULL = 40;

const POSES = {
  heroA: { pos: v3(0, 3.5, 22), look: v3(1, 1.5, -30), phase: 0, boat: 0.9 },
  heroB: { pos: v3(0, 3.7, 12), look: v3(3, 1.8, -38), phase: 0, boat: 1.6 },
  aboutEnd: { pos: v3(-1, 3.4, 2), look: v3(3, 1.8, -40), phase: 0, boat: 1.8 },
  outA: { pos: v3(-3.4, 3.2, -17), look: v3(17.5, 2.1, -46), phase: 0, boat: 2.0 },
  outB: { pos: v3(-3.8, 3.3, -26), look: v3(18, 2.3, -47), phase: 0, boat: 2.0 },
  panA: { pos: v3(-3.6, 3.5, -55), look: v3(17, 4.2, -84), phase: 1, boat: 2.0 },
  panB: { pos: v3(-3.9, 3.6, -63), look: v3(17.5, 5.2, -85), phase: 1, boat: 2.0 },
  carA: { pos: v3(-3.6, 3.7, -93), look: v3(18, 3.4, -121), phase: 2, boat: 2.0 },
  carB: { pos: v3(-3.9, 3.8, -101), look: v3(18.5, 3.8, -122), phase: 2, boat: 2.0 },
  // ascent: 1) carnival recedes below  2) atmosphere thins, horizon curves, stars  3) orbit
  rise: { pos: v3(-5, 11, -94), look: v3(8, 2.5, -124), phase: 2.3, boat: 2.0 },
  thin: { pos: v3(-2, 27, -106), look: v3(2, 29, -150), phase: 2.8, boat: 2.0 },
  hackA: { pos: v3(-0.5, 33, -115), look: v3(1.5, 41, -150), phase: 3, boat: 2.0 },
  hackB: { pos: v3(0, 37, -123), look: v3(1.2, 46.2, -148), phase: 3, boat: 2.0 },
} satisfies Record<string, Pose>;

interface Key { y: number; pose: Pose; ease?: boolean }

function buildKeys(): Key[] | null {
  const q = (s: string) => document.querySelector<HTMLElement>(s);
  const box = (el: HTMLElement | null) => {
    if (!el) return null;
    const sp = el.parentElement?.classList.contains("pin-spacer") ? el.parentElement : el;
    const r = sp.getBoundingClientRect();
    return { t: r.top + window.scrollY, b: r.bottom + window.scrollY, h: r.height };
  };
  const hero = box(q(".hero")), out = box(q(".outpost")), pan = box(q(".pandemonium")), car = box(q(".carnival")), hack = box(q(".hack"));
  const ascent = box(q('[data-crossing="orbit"]'));
  const cross = Array.from(document.querySelectorAll<HTMLElement>('[data-crossing]:not([data-crossing="orbit"])')).map(box);
  if (!hero || !out || !pan || !car || !hack || !ascent || cross.length < 3 || cross.some((c) => !c)) return null;
  const c = cross as { t: number; b: number; h: number }[];
  const vh = window.innerHeight;
  const raw: Key[] = [
    { y: hero.t, pose: POSES.heroA },
    { y: hero.b, pose: POSES.heroB },
    { y: c[0].t, pose: POSES.aboutEnd },
    { y: c[0].b, pose: POSES.outA, ease: true },
    { y: out.b, pose: POSES.outB },
    { y: c[1].b, pose: POSES.panA, ease: true },
    { y: pan.b, pose: POSES.panB },
    { y: c[2].b, pose: POSES.carA, ease: true },
    { y: car.b, pose: POSES.carB },
    { y: ascent.t + ascent.h * 0.2, pose: POSES.rise, ease: true },
    { y: ascent.t + ascent.h * 0.55, pose: POSES.thin, ease: true },
    { y: ascent.b - 100, pose: POSES.hackA, ease: true },
    { y: hack.b - vh, pose: POSES.hackB },
  ];
  for (let i = 1; i < raw.length; i++) raw[i].y = Math.max(raw[i].y, raw[i - 1].y + 1);
  return raw;
}

const easeIO = (t: number) => 0.5 - 0.5 * Math.cos(Math.PI * t);
type Goal = { pos: THREE.Vector3; look: THREE.Vector3; phase: number; boat: number };

function samplePose(y: number, keys: Key[], out: Goal, snap: boolean) {
  let i = 0;
  while (i < keys.length - 2 && y >= keys[i + 1].y) i++;
  const a = keys[i], b = keys[i + 1];
  let t = THREE.MathUtils.clamp((y - a.y) / (b.y - a.y), 0, 1);
  if (snap) t = t < 0.5 ? 0 : 1; // reduced motion: hold each chapter's framing, no fly-throughs
  else if (b.ease) t = easeIO(t);
  out.pos.lerpVectors(a.pose.pos, b.pose.pos, t);
  out.look.lerpVectors(a.pose.look, b.pose.look, t);
  out.phase = THREE.MathUtils.lerp(a.pose.phase, b.pose.phase, t);
  out.boat = THREE.MathUtils.lerp(a.pose.boat, b.pose.boat, t);
}

/* --------------------------------------------------- chapter light pool */
// A fixed set of three point lights is re-aimed per chapter. Mounting/unmounting
// lights per island would change the light count and recompile every shader.
type LightDef = [THREE.Vector3, string, number, number]; // position, colour, intensity, distance
const at = (o: THREE.Vector3, x: number, y: number, z: number) => o.clone().add(new THREE.Vector3(x, y, z));
const CHAPTER_LIGHTS: LightDef[][] = [
  [[at(ISLANDS.outpost, OUTPOST_PAD.x, 4.5, OUTPOST_PAD.z + 2.2), "#ff9a4a", 22, 11]],
  [[at(ISLANDS.pandemonium, -5, 6, 4), "#ff2ea6", 140, 30], [at(ISLANDS.pandemonium, 5, 5, 3), "#27e6ff", 110, 28], [at(ISLANDS.pandemonium, 0, 12, -4), "#9a5bff", 90, 30]],
  [[at(ISLANDS.carnival, CARNIVAL_WHEEL.x, 6, CARNIVAL_WHEEL.z + 4), "#ff9e4d", 160, 30], [at(ISLANDS.carnival, -4, 3.5, 6), "#ffb667", 55, 16]],
  [[at(SPACE.astronaut, 0.7, 2.2, 2.4), "#8fe9ff", 34, 16]],
];

/* --------------------------------------------------------------- the rig */
function Rig({ tier }: { tier: Tier }) {
  const { camera, scene, gl, size, invalidate } = useThree();
  const skyMat = useMemo(() => createSkyMaterial(), []);
  const normals = useMemo(() => {
    const texture = new THREE.TextureLoader().load("/textures/water/ocean-normal.png", () => invalidate());
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.colorSpace = THREE.NoColorSpace;
    texture.anisotropy = Math.min(8, gl.capabilities.getMaxAnisotropy());
    return texture;
  }, [gl, invalidate]);
  const ocean = useMemo(() => {
    const o = new Ocean(oceanGeometry(detectTier() === 0 ? 128 : 256), normals, 512);
    o.rotation.x = -Math.PI / 2; o.frustumCulled = false;
    return o;
  }, [normals]);
  useEffect(() => () => {
    ocean.geometry.dispose(); ocean.material.dispose(); ocean.renderTarget.dispose(); normals.dispose();
  }, [ocean, normals]);
  const dome = useRef<THREE.Mesh>(null!);
  const sun = useRef<THREE.DirectionalLight>(null!);
  const hemi = useRef<THREE.HemisphereLight>(null!);
  const boat = useRef<THREE.Group>(null!);
  const pool = useRef<(THREE.PointLight | null)[]>([]);
  const target = useMemo(() => new THREE.Object3D(), []);
  const keys = useRef<Key[] | null>(null);
  const smoothLook = useMemo(() => new THREE.Vector3(0, 1.5, -30), []);
  const goal = useMemo<Goal>(() => ({ pos: new THREE.Vector3(), look: new THREE.Vector3(), phase: 0, boat: 1 }), []);
  const tmp = useMemo(() => ({ fwd: new THREE.Vector3(), right: new THREE.Vector3(), aim: new THREE.Vector3(), first: true, boatSide: 1, reverse: false }), []);
  const phase = useRef(0);

  // environment lighting: PMREM of the sky, re-rendered only when the sky actually changes
  const pmrem = useMemo(() => new THREE.PMREMGenerator(gl), [gl]);
  const envScene = useMemo(() => {
    const s = new THREE.Scene();
    const m = new THREE.Mesh(new THREE.SphereGeometry(1, 32, 16), skyMat);
    m.scale.setScalar(100);
    s.add(m);
    return s;
  }, [skyMat]);
  const env = useRef<{ rt: THREE.WebGLRenderTarget | null; phase: number; alt: number; size: number }>({ rt: null, phase: -1, alt: -1, size: 0 });
  useEffect(() => () => { env.current.rt?.dispose(); pmrem.dispose(); }, [pmrem]);

  // camera keys follow layout changes, never polled from the render loop
  useEffect(() => {
    let raf = 0;
    const rebuild = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(() => { keys.current = buildKeys(); invalidate(); }); };
    rebuild();
    ScrollTrigger.addEventListener("refresh", rebuild);
    window.addEventListener("resize", rebuild);
    document.fonts?.ready.then(rebuild);
    const ro = new ResizeObserver(rebuild);
    ro.observe(document.body);
    const onScroll = () => invalidate();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      cancelAnimationFrame(raf);
      ScrollTrigger.removeEventListener("refresh", rebuild);
      window.removeEventListener("resize", rebuild);
      window.removeEventListener("scroll", onScroll);
      ro.disconnect();
    };
  }, [invalidate]);

  useEffect(() => {
    ocean.renderTarget.setSize(tier.mirror, tier.mirror);
    ocean.reflectEvery = tier.mirrorEvery;
    const s = sun.current;
    s.castShadow = tier.shadow > 0;
    if (tier.shadow > 0) {
      s.shadow.mapSize.set(tier.shadow, tier.shadow);
      s.shadow.map?.dispose();
      s.shadow.map = null as unknown as THREE.WebGLRenderTarget;
      const half = 44;
      Object.assign(s.shadow.camera, { left: -half, right: half, top: half, bottom: -half, near: 1, far: 220 });
      s.shadow.camera.updateProjectionMatrix();
      s.shadow.bias = -0.0004; s.shadow.normalBias = 0.06; s.shadow.radius = 2.2;
    }
    gl.shadowMap.type = THREE.PCFSoftShadowMap;
    env.current.phase = -1; // force an env refresh at the new size
    invalidate();
  }, [tier, ocean, gl, invalidate]);

  useFrame((state, rawDt) => {
    const dt = Math.min(rawDt, 0.05);
    const reduced = world.reduced;
    world.dt = reduced ? 0 : dt;
    world.time += world.dt;
    world.velocity = reduced ? 0 : window.__voyageVelocity || 0;

    if (keys.current) samplePose(window.scrollY, keys.current, goal, reduced);
    else { goal.pos.copy(POSES.heroA.pos); goal.look.copy(POSES.heroA.look); goal.phase = 0; goal.boat = POSES.heroA.boat; }

    // Narrow screens: the islands lie to starboard, so turn further toward them (a portrait frame is too
    // narrow to keep them off-axis), pull back so each fits the width, and aim a little low so the island
    // sits in the upper half, above the chapter text that scrolls up from the bottom.
    const aspect = size.width / size.height;
    const k = THREE.MathUtils.clamp(aspect / 1.25, 0.35, 1);
    goal.look.x = goal.pos.x + (goal.look.x - goal.pos.x) * (1 + (1 - k) * 0.95);
    tmp.aim.subVectors(goal.pos, goal.look).setY(0).normalize();
    goal.pos.addScaledVector(tmp.aim, (1 - k) * PORTRAIT_PULL);
    goal.pos.y += (1 - k) * 4;
    goal.look.y -= (1 - k) * 16;
    if (!reduced) {
      goal.pos.x += state.pointer.x * 0.5 * k;
      goal.pos.y += state.pointer.y * 0.25 + Math.sin(world.time * 0.55) * 0.05;
    }

    const snapNow = tmp.first || reduced;
    if (snapNow) { camera.position.copy(goal.pos); smoothLook.copy(goal.look); phase.current = goal.phase; tmp.boatSide = goal.boat; tmp.first = false; }
    const lam = 4.5;
    camera.position.x = THREE.MathUtils.damp(camera.position.x, goal.pos.x, lam, dt);
    camera.position.y = THREE.MathUtils.damp(camera.position.y, goal.pos.y, lam, dt);
    camera.position.z = THREE.MathUtils.damp(camera.position.z, goal.pos.z, lam, dt);
    smoothLook.x = THREE.MathUtils.damp(smoothLook.x, goal.look.x, lam, dt);
    smoothLook.y = THREE.MathUtils.damp(smoothLook.y, goal.look.y, lam, dt);
    smoothLook.z = THREE.MathUtils.damp(smoothLook.z, goal.look.z, lam, dt);
    camera.lookAt(smoothLook);
    const cam = camera as THREE.PerspectiveCamera;
    const fov = aspect < 0.8 ? 56 : 48;
    if (cam.fov !== fov) { cam.fov = fov; cam.updateProjectionMatrix(); }
    world.camPos.copy(camera.position);

    phase.current = THREE.MathUtils.damp(phase.current, goal.phase, 3, dt);
    world.phase = phase.current;
    blendPreset(world.cur, phase.current);
    const cur = world.cur;

    // chapter visibility: islands rise from the sea ahead, sink once passed, and drop away as we climb to orbit
    const camY = camera.position.y;
    const altK = smoothstep(8, 34, camY);
    world.altK = altK;
    const isl = [ISLANDS.outpost, ISLANDS.pandemonium, ISLANDS.carnival];
    // the first island is part of the hero skyline; later ones only rise once their crossing begins
    const rise = [[100, 76], [62, 46], [62, 46]];
    for (let i = 0; i < 3; i++) {
      const d = camera.position.z - isl[i].z;
      world.islandK[i] = Math.min(smoothstep(rise[i][0], rise[i][1], d), smoothstep(-70, -48, d), smoothstep(30, 18, camY));
    }
    world.spaceK = smoothstep(2.55, 2.95, phase.current) * smoothstep(24, 33, camY);

    // sky: the atmosphere thins with altitude; the horizon dips and gains a limb glow
    dome.current.position.copy(camera.position);
    const u = skyMat.uniforms;
    u.uTop.value.copy(cur.top); u.uMid.value.copy(cur.mid); u.uHorizon.value.copy(cur.horizon); u.uGround.value.copy(cur.ground);
    u.uSunDir.value.copy(cur.sunDir); u.uSunColor.value.copy(cur.sun); u.uSunCos.value = cur.sunCos; u.uSunInt.value = cur.sunInt;
    u.uStars.value = Math.max(cur.stars, altK); u.uStripes.value = cur.stripes; u.uHaze.value = cur.haze * (1 - altK * 0.8);
    u.uCloudAmt.value = cur.cloudAmt * (1 - altK); u.uCloudLit.value.copy(cur.cloudLit); u.uCloudDark.value.copy(cur.cloudDark);
    u.uTime.value = world.time; u.uDip.value = altK * 0.07; u.uLimb.value = altK;

    // ocean
    const ou = ocean.material.uniforms;
    ou.time.value = world.time;
    ou.sunColor.value.copy(cur.sun); ou.sunDirection.value.copy(cur.sunDir);
    ou.uDeep.value.copy(cur.deep); ou.uShallow.value.copy(cur.shallow); ou.uGlint.value = cur.glint;
    ocean.position.x = Math.round(camera.position.x / 16) * 16;
    ocean.position.z = Math.round(camera.position.z / 16) * 16;
    ou.uWakeStrength.value = 0.35 + Math.min(Math.abs(world.velocity) / 2200, 1) * 0.65;
    ocean.visible = altK < 0.97;

    const fog = scene.fog as THREE.FogExp2;
    if (fog) { fog.color.copy(cur.fog); fog.density = cur.fogD * (1 - altK * 0.85); }

    // env map: refresh only when the sky has visibly changed
    const e = env.current;
    if (!e.rt || Math.abs(phase.current - e.phase) > tier.envStep || Math.abs(altK - e.alt) > 0.05 || e.size !== tier.envStep) {
      const rt = pmrem.fromScene(envScene, 0, 0.1, 1000);
      scene.environment = rt.texture;
      e.rt?.dispose();
      Object.assign(e, { rt, phase: phase.current, alt: altK, size: tier.envStep });
    }
    scene.environmentIntensity = cur.envI;

    // shadow frustum glued to where we're looking
    camera.getWorldDirection(tmp.fwd);
    tmp.aim.set(Math.round(camera.position.x + tmp.fwd.x * 30), 0, Math.round(camera.position.z + tmp.fwd.z * 30));
    target.position.copy(tmp.aim);
    sun.current.position.copy(tmp.aim).addScaledVector(cur.sunDir, 90);
    sun.current.color.copy(cur.light); sun.current.intensity = cur.lightI;
    hemi.current.color.copy(cur.hemiSky); hemi.current.groundColor.copy(cur.hemiGround); hemi.current.intensity = cur.hemiI;

    // chapter light pool
    const weights = [...world.islandK, world.spaceK];
    let best = 0;
    for (let i = 1; i < 4; i++) if (weights[i] > weights[best]) best = i;
    const defs = CHAPTER_LIGHTS[best];
    pool.current.forEach((l, i) => {
      if (!l) return;
      const d = defs[i];
      if (!d) { l.intensity = 0; return; }
      l.position.copy(d[0]); l.color.set(d[1]); l.intensity = d[2] * weights[best]; l.distance = d[3];
    });

    // the boat sails ahead of the camera, offset right so it never crosses the copy column
    tmp.boatSide = THREE.MathUtils.damp(tmp.boatSide, goal.boat, 2, dt);
    tmp.fwd.set(smoothLook.x - camera.position.x, 0, smoothLook.z - camera.position.z).normalize();
    tmp.right.set(-tmp.fwd.z, 0, tmp.fwd.x);
    const dist = 15.5 + (1 - k) * (8 + PORTRAIT_PULL);
    boat.current.position.copy(camera.position).addScaledVector(tmp.fwd, dist).addScaledVector(tmp.right, tmp.boatSide * k);
    boat.current.position.y = 0;
    // All islands lie to starboard. Stay west of their entire shoreline envelope,
    // including bow length, rather than sailing along the camera's sight line.
    let clearance = 0;
    for (const island of isl) clearance = Math.max(clearance, 1 - smoothstep(24, 36, Math.abs(boat.current.position.z - island.z)));
    boat.current.position.x = THREE.MathUtils.lerp(boat.current.position.x, Math.min(boat.current.position.x, 2.2), clearance);
    // Scrolling back up sails the boat back the way it came, so it comes about and faces that way.
    // A small dead band keeps it from flip-flopping on trackpad jitter; it keeps its last heading when idle.
    if (world.velocity < -180) tmp.reverse = true;
    else if (world.velocity > 180) tmp.reverse = false;
    const heading = Math.atan2(-tmp.fwd.x * (1 - clearance), -tmp.fwd.z) + (tmp.reverse ? Math.PI : 0);
    // turn the short way round, at a pace that reads as the helm being put over
    const turn = Math.atan2(Math.sin(heading - boat.current.rotation.y), Math.cos(heading - boat.current.rotation.y));
    boat.current.rotation.y += turn * (1 - Math.exp(-1.8 * dt));
    boat.current.visible = camY < 14;
    boat.current.updateWorldMatrix(true, true);
    const hull = boat.current.getObjectByName("voyage-hull");
    ou.uBoatInverse.value.copy(hull ? hull.matrixWorld : boat.current.matrixWorld).invert();
    ou.uBoatMask.value = boat.current.visible ? 1 : 0;
  }, -1);

  return (
    <>
      <fogExp2 attach="fog" args={["#efc08c", 0.006]} />
      <hemisphereLight ref={hemi} />
      <directionalLight ref={sun} target={target} />
      <primitive object={target} />
      {[0, 1, 2].map((i) => <pointLight key={i} ref={(l) => { pool.current[i] = l; }} intensity={0} decay={2} />)}
      <mesh ref={dome} frustumCulled={false} renderOrder={-1000}>
        <sphereGeometry args={[1500, 48, 24]} />
        <primitive object={skyMat} attach="material" />
      </mesh>
      <primitive object={ocean} />
      <group ref={boat}><Suspense fallback={null}><Boat /></Suspense></group>
      <Islands />
      <Space />
      <EffectComposer key={tier.msaa} multisampling={tier.msaa}>
        <Bloom mipmapBlur luminanceThreshold={0.95} luminanceSmoothing={0.25} intensity={tier.bloom} radius={0.72} />
        <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
        <Vignette eskil={false} offset={0.18} darkness={0.55} />
      </EffectComposer>
    </>
  );
}

export default function VoyageWorld() {
  const [{ start, reduced }] = useState(() => {
    const s = detectTier();
    world.compact = s === 0;
    world.quality = s;
    world.reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    return { start: s, reduced: world.reduced };
  });
  const [tierIdx, setTierIdx] = useState(start);
  const tier = TIERS[tierIdx];
  return (
    <div className="voyage-world fixed inset-0 z-0 bg-[#0a0d14]" aria-hidden="true">
      <Canvas
        dpr={tier.dpr}
        frameloop={reduced ? "demand" : "always"}
        camera={{ fov: 48, near: 0.3, far: 4000, position: [0, 3.5, 22] }}
        shadows
        gl={{ antialias: false, powerPreference: "high-performance", toneMapping: THREE.NoToneMapping }}
      >
        <PerformanceMonitor
          flipflops={3}
          onDecline={() => setTierIdx((t) => Math.max(0, t - 1))}
          onIncline={() => setTierIdx((t) => Math.min(start, t + 1))}
          onFallback={() => setTierIdx(0)}
        />
        <Rig tier={tier} />
      </Canvas>
    </div>
  );
}
