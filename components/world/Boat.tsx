"use client";

import { useGLTF } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { clamp, glowTexture } from "./proc";
import { world } from "./sky";
import { sampleWater } from "./waves";

/**
 * Hero sailboat, authored in Blender (blender/boat.py → public/models/boat-realistic.glb).
 * Materials are baked PBR (colour, ORM, normal, emission); only the sails, flag,
 * rudder, tiller and lantern are separate nodes so they can move.
 */
useGLTF.preload("/models/boat-realistic.glb");

export default function Boat() {
  const { scene } = useGLTF("/models/boat-realistic.glb");
  const model = useMemo(() => {
    const clone = scene.clone(true);
    const materials = new Map<THREE.Material, THREE.Material>();
    clone.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      const source = mesh.material as THREE.MeshStandardMaterial;
      if (!materials.has(source)) {
        const physical = new THREE.MeshPhysicalMaterial();
        THREE.MeshStandardMaterial.prototype.copy.call(physical, source);
        physical.defines = { STANDARD: "", PHYSICAL: "" };
        if (source.name.startsWith("sail_")) {
          physical.side = THREE.DoubleSide;
          physical.sheen = 0.35;
          physical.sheenColor.set("#e3d9bd");
          physical.sheenRoughness = 0.9;
          physical.roughness = 0.9;
        } else if (source.name === "boat_mat") {
          physical.clearcoat = 0.2;
          physical.clearcoatRoughness = 0.28;
        }
        materials.set(source, physical);
      }
      mesh.material = materials.get(source)!;
    });
    return clone;
  }, [scene]);
  const hull = useRef<THREE.Group>(null!);
  const smooth = useRef({ heel: 0.05, speed: 0 });
  const glow = useMemo(() => glowTexture(), []);
  const buoyancy = useMemo(() => ({ position: new THREE.Vector3(), surface: new THREE.Vector3() }), []);

  const parts = useMemo(() => {
    const get = (n: string) => model.getObjectByName(n) as THREE.Object3D;
    const o = {
      sailMain: get("Sail_Main") as THREE.Mesh, sailJib: get("Sail_Jib") as THREE.Mesh, flag: get("Flag") as THREE.Mesh,
      rudder: get("Rudder"), tiller: get("Tiller"), lantern: get("Lantern"),
    };
    return { ...o, rest: { rudder: o.rudder.rotation.clone(), tiller: o.tiller.rotation.clone(), lantern: o.lantern.rotation.clone() }, light: null as THREE.PointLight | null };
  }, [model]);

  useEffect(() => {
    const seen = new Set<THREE.Material>();
    model.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      mesh.castShadow = true; mesh.receiveShadow = true;
      const m = mesh.material as THREE.MeshStandardMaterial;
      if (seen.has(m)) return;
      seen.add(m);
      if (m.name.startsWith("sail_") || m.name === "Flag") m.side = THREE.DoubleSide;
      if (m.name === "boat_mat") m.envMapIntensity = 1.1;
      m.needsUpdate = true;
    });
    // lantern light + glow sprite ride on the swinging node
    const light = new THREE.PointLight("#ffa24a", 1.6, 9, 2);
    light.position.set(0, -0.1, 0);
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color: "#ffa24a", transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending, depthWrite: false }));
    sprite.scale.set(1.0, 1.0, 1); sprite.position.set(0, -0.1, 0);
    parts.lantern.add(light, sprite);
    parts.light = light;
    return () => { parts.lantern.remove(light, sprite); };
  }, [model, glow, parts]);

  useFrame(() => {
    const t = world.time, dt = world.dt;
    const sm = smooth.current;
    const speed = clamp(Math.abs(world.velocity) / 2200, 0, 1);
    sm.speed += (speed - sm.speed) * Math.min(1, dt * 2.5);
    sm.heel += ((0.045 + sm.speed * 0.1) - sm.heel) * Math.min(1, dt * 1.5);

    // Sample the same travelling wave field as the ocean at the hull's location.
    if (hull.current) {
      hull.current.parent!.getWorldPosition(buoyancy.position);
      const surface = sampleWater(buoyancy.position.x, buoyancy.position.z, t, buoyancy.surface);
      const heading = hull.current.parent!.parent?.rotation.y ?? 0;
      const forwardSlope = surface.x * Math.sin(heading) + surface.z * Math.cos(heading);
      const sideSlope = surface.x * Math.cos(heading) - surface.z * Math.sin(heading);
      hull.current.position.y = surface.y + sm.speed * 0.02;
      hull.current.rotation.z = sm.heel + Math.atan(sideSlope) * 0.8;
      hull.current.rotation.x = -Math.atan(forwardSlope) * 0.8 - sm.speed * 0.03;
      hull.current.rotation.y = Math.sin(t * 0.4) * 0.03;
    }

    // sails morph between the Blender-authored calm / billow / flutter shapes
    const gust = Math.sin(t * 0.7) * 0.5 + 0.5;
    const setMorph = (m: THREE.Mesh, billow: number, flutter: number) => {
      const inf = m.morphTargetInfluences, d = m.morphTargetDictionary;
      if (!inf || !d) return;
      if (d.Billow !== undefined) inf[d.Billow] = billow;
      if (d.Flutter !== undefined) inf[d.Flutter] = flutter;
    };
    const flap = (Math.sin(t * 4.6) * 0.5 + 0.5) * (0.35 - sm.speed * 0.2);
    setMorph(parts.sailMain, 0.6 + gust * 0.35 + sm.speed * 0.2 - flap * 0.4, flap + 0.1);
    setMorph(parts.sailJib, 0.55 + (Math.sin(t * 1.1 + 1) * 0.5 + 0.5) * 0.4 + sm.speed * 0.2, (Math.sin(t * 5.3 + 2) * 0.5 + 0.5) * 0.3);
    if (parts.flag.morphTargetInfluences) parts.flag.morphTargetInfluences[0] = 0.55 + Math.sin(t * 9) * 0.4 + Math.sin(t * 5.1) * 0.15;

    // lantern swings on its chain, flame flickers
    parts.lantern.rotation.x = parts.rest.lantern.x + Math.sin(t * 1.3) * 0.08;
    parts.lantern.rotation.z = parts.rest.lantern.z + Math.sin(t * 1.7) * 0.12;
    if (parts.light) parts.light.intensity = (1.6 + Math.sin(t * 9) * 0.18 + Math.sin(t * 13.3) * 0.12) * (1 - world.cur.envI * 0.35);

    // tiller and rudder move together, as if steered
    const ta = Math.sin(t * 0.8) * 0.12 + Math.sin(t * 2.1) * 0.03 * (0.35 + sm.speed * 0.65);
    parts.tiller.rotation.y = parts.rest.tiller.y + ta;
    parts.rudder.rotation.y = parts.rest.rudder.y - ta;
  });

  // "voyage-hull" lets the ocean shader follow the hull's heave/roll when masking its footprint
  return <group><group ref={hull} name="voyage-hull"><primitive object={model} /></group></group>;
}
