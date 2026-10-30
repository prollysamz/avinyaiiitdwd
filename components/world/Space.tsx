"use client";

import { useGLTF, useTexture } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { moonTextures } from "./proc";
import { world } from "./sky";

export const SPACE = {
  astronaut: new THREE.Vector3(7.5, 43.2, -139),
  earth: new THREE.Vector3(44, 44, -250),
  moon: new THREE.Vector3(-34, 68, -215),
};

function Earth() {
  const globe = useRef<THREE.Group>(null!);
  const portraitPosition = useMemo(() => new THREE.Vector3(), []);
  const [map, normalMap] = useTexture(["/textures/earth-day.jpg", "/textures/earth-normal.jpg"]);
  useEffect(() => { map.colorSpace = THREE.SRGBColorSpace; map.anisotropy = 8; map.needsUpdate = true; }, [map]);
  const R = 38;
  const surface = useRef<THREE.MeshStandardMaterial>(null!);
  const spin = useRef<THREE.Mesh>(null!);
  useFrame((state) => {
    // One turn in roughly four minutes: slow enough to feel like distance, fast enough to notice.
    if (spin.current) spin.current.rotation.y = world.time * 0.026;
    const portrait = state.size.width / state.size.height < 0.8;
    // Keep the globe in the open upper portion of a portrait screen, clear of
    // the reading panel, rather than letting its centre sit off-screen.
    if (portrait) globe.current.position.copy(portraitPosition.set(8, 33, -130).applyMatrix4(state.camera.matrixWorld));
    else globe.current.position.copy(SPACE.earth);
    globe.current.scale.setScalar(portrait ? 0.52 : 1);
    if (surface.current) surface.current.opacity = world.spaceK;
  });
  return (
    <group ref={globe} position={SPACE.earth} rotation={[0.25, 2.6, 0.1]}>
      <mesh ref={spin} name="earth-surface"><sphereGeometry args={[R, 96, 64]} /><meshStandardMaterial ref={surface} map={map} emissiveMap={map} emissive="#ffffff" emissiveIntensity={0.4} normalMap={normalMap} normalScale={new THREE.Vector2(0.22, 0.22)} roughness={0.82} metalness={0} transparent /></mesh>
    </group>
  );
}

function Moon() {
  const m = useMemo(() => moonTextures(), []);
  const mat = useRef<THREE.MeshStandardMaterial>(null!);
  useFrame(() => { if (mat.current) mat.current.opacity = world.spaceK; });
  return (
    <mesh position={SPACE.moon} rotation={[0.2, 1.2, 0]}>
      <sphereGeometry args={[6.2, 64, 48]} />
      <meshStandardMaterial ref={mat} map={m.map} normalMap={m.normalMap} normalScale={new THREE.Vector2(1.4, 1.4)} roughness={1} transparent />
    </mesh>
  );
}


/**
 * Meteors. Each is a thin streak with a bright head and a tail that fades to nothing, drawn on a plane far behind
 * everything else, so it reads as a distant sky event, not an object in the scene. They fire at irregular intervals,
 * mostly one at a time, and cross a fraction of the screen in about a second.
 */
const METEOR_POOL = 2, METEOR_DEPTH = 900;
const meteorVertex = /* glsl */ `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const meteorFragment = /* glsl */ `
  varying vec2 vUv; uniform float uAlpha; uniform vec3 uTint;
  void main(){
    float along = vUv.x;                              // 0 = tail tip, 1 = head
    float across = 1.0 - abs(vUv.y * 2.0 - 1.0);
    float body = pow(along, 1.7) * pow(across, 0.9);
    float head = exp(-(1.0 - along) * 22.0) * pow(across, 0.5);
    vec3 col = mix(uTint, vec3(1.0, 0.97, 0.9), clamp(head * 1.5, 0.0, 1.0)) * 1.8;
    gl_FragColor = vec4(col, clamp(body * 1.5 + head * 1.5, 0.0, 1.0) * uAlpha);
  }`;

function Meteors() {
  const rig = useRef<THREE.Group>(null!);
  const meteors = useMemo(() => Array.from({ length: METEOR_POOL }, () => ({
    mesh: null as THREE.Mesh | null, mat: null as THREE.ShaderMaterial | null,
    wait: 1 + Math.random() * 4, age: 0, dur: 1, x: 0, y: 0, dx: 1, dy: 0, len: 100, dist: 300, active: false,
  })), []);
  useFrame((state) => {
    if (!rig.current) return;
    rig.current.matrix.copy(state.camera.matrixWorld);
    rig.current.matrixWorldNeedsUpdate = true;
    const dt = world.dt;
    const cam = state.camera as THREE.PerspectiveCamera;
    const halfH = Math.tan(THREE.MathUtils.degToRad(cam.fov / 2)) * METEOR_DEPTH, halfW = halfH * state.size.width / state.size.height;
    for (const m of meteors) {
      if (!m.mesh || !m.mat) continue;
      if (!m.active) {
        m.wait -= dt;
        m.mat.uniforms.uAlpha.value = 0; m.mesh.visible = false;
        if (m.wait > 0) continue;
        // launch: start in the upper part of the sky, head down and across at a shallow, slightly random angle
        const ltr = Math.random() < 0.5 ? 1 : -1;
        const slope = 0.25 + Math.random() * 0.55;
        const n = Math.hypot(1, slope);
        m.dx = ltr / n; m.dy = -slope / n;
        m.x = (Math.random() * 1.6 - 0.8) * halfW;
        m.y = halfH * (0.15 + Math.random() * 0.8);
        m.len = halfW * (0.22 + Math.random() * 0.2);
        m.dur = 0.55 + Math.random() * 0.6;
        m.age = 0; m.active = true;
        m.mat.uniforms.uTint.value.set(Math.random() < 0.3 ? "#ffd9b0" : "#bcd6ff");
        continue;
      }
      m.age += dt;
      const p = m.age / m.dur;
      if (p >= 1) { m.active = false; m.wait = 3.5 + Math.random() * 8; continue; }
      const travel = halfW * 1.1 * p;                                  // how far the head has moved
      const hx = m.x + m.dx * travel, hy = m.y + m.dy * travel;
      const L = m.len * (0.55 + 0.45 * Math.sin(Math.min(1, p * 1.4) * Math.PI * 0.5)); // tail grows as it ignites
      m.mesh.visible = true;
      m.mesh.position.set(hx - m.dx * L / 2, hy - m.dy * L / 2, -METEOR_DEPTH);
      m.mesh.rotation.z = Math.atan2(m.dy, m.dx);
      m.mesh.scale.set(L, halfH * 0.011, 1);
      m.mat.uniforms.uAlpha.value = Math.sin(p * Math.PI) ** 0.8 * world.spaceK;
    }
  });
  return (
    <group ref={rig} matrixAutoUpdate={false}>
      {meteors.map((m, i) => (
        <mesh key={i} ref={(o) => { m.mesh = o; }} frustumCulled={false} renderOrder={-1}>
          <planeGeometry args={[1, 1]} />
          <shaderMaterial ref={(o) => { m.mat = o; }} vertexShader={meteorVertex} fragmentShader={meteorFragment} uniforms={{ uAlpha: { value: 0 }, uTint: { value: new THREE.Color("#bcd6ff") } }}
            transparent depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
        </mesh>
      ))}
    </group>
  );
}

function FlightAstronaut() {
  const { scene } = useGLTF("/models/neil-armstrong.glb");
  const rig = useRef<THREE.Group>(null!);
  const portraitPosition = useMemo(() => new THREE.Vector3(), []);
  const model = useMemo(() => {
    const copy = scene.clone(true);
    const box = new THREE.Box3().setFromObject(copy);
    const center = box.getCenter(new THREE.Vector3());
    const scale = 6.2 / box.getSize(new THREE.Vector3()).y;
    copy.position.copy(center).multiplyScalar(-scale);
    copy.scale.setScalar(scale);
    copy.traverse((obj) => { if (obj instanceof THREE.Mesh) { obj.castShadow = true; obj.receiveShadow = true; } });
    return copy;
  }, [scene]);
  useFrame((state) => {
    const t = world.time, a = 1 - world.spaceK;
    const portrait = state.size.width / state.size.height < 0.8;
    // Portrait framing follows the camera through the orbital chapter, keeping
    // the figure above the panel even on a shorter phone screen.
    const home = portrait ? portraitPosition.set(1, 7, -30).applyMatrix4(state.camera.matrixWorld) : SPACE.astronaut;
    rig.current.position.set(home.x + Math.sin(t * .31) * .65 + a * 14 + state.pointer.x * .25, home.y + Math.sin(t * .47) * .5 + a * 6, home.z + Math.cos(t * .23) * .45 - a * 30);
    rig.current.rotation.set(.12 + Math.sin(t * .19) * .1, -.35 + Math.sin(t * .17) * .18, .25 + Math.sin(t * .29) * .12);
  });
  return <group ref={rig} name="free-flight-astronaut"><primitive object={model} /></group>;
}

export default function Space() {
  const group = useRef<THREE.Group>(null!);
  const [ready, setReady] = useState(false);
  // generate the heavy procedural textures a moment after load, while the preloader is still up
  useEffect(() => { const id = window.setTimeout(() => setReady(true), 2500); return () => window.clearTimeout(id); }, []);
  useFrame(() => { if (group.current) group.current.visible = world.spaceK > 0.005; });
  if (!ready) return null;
  return (
    <group ref={group}>
      <Suspense fallback={null}><Earth /></Suspense>
      <Moon />
      {!world.reduced && <Meteors />}
      <Suspense fallback={null}><FlightAstronaut /></Suspense>
    </group>
  );
}

