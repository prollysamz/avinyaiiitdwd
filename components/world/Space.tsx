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
  useFrame((state) => {
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
      <mesh name="earth-surface"><sphereGeometry args={[R, 96, 64]} /><meshStandardMaterial ref={surface} map={map} emissiveMap={map} emissive="#ffffff" emissiveIntensity={0.4} normalMap={normalMap} normalScale={new THREE.Vector2(0.22, 0.22)} roughness={0.82} metalness={0} transparent /></mesh>
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
      <Suspense fallback={null}><FlightAstronaut /></Suspense>
    </group>
  );
}

