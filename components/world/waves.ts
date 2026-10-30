import * as THREE from "three";

// Metres, seconds and deep-water dispersion (omega² = gk). Keep the CPU boat
// buoyancy and GPU ocean surface on exactly the same spectrum and scene clock.
const WAVES = [
  { x: 0.86, z: 0.51, length: 19, amplitude: 0.16, phase: 0.4 },
  { x: -0.38, z: 0.925, length: 11, amplitude: 0.085, phase: 2.1 },
  { x: 0.98, z: -0.199, length: 6.8, amplitude: 0.045, phase: 4.7 },
  { x: 0.65, z: 0.76, length: 3.6, amplitude: 0.018, phase: 1.3 },
];

export function sampleWater(x: number, z: number, time: number, result: THREE.Vector3) {
  let height = 0, dx = 0, dz = 0;
  for (const w of WAVES) {
    const k = Math.PI * 2 / w.length;
    const p = k * (w.x * x + w.z * z) - Math.sqrt(9.81 * k) * time + w.phase;
    height += Math.sin(p) * w.amplitude;
    dx += Math.cos(p) * w.amplitude * k * w.x;
    dz += Math.cos(p) * w.amplitude * k * w.z;
  }
  return result.set(dx, height, dz);
}

export const waveGLSL = /* glsl */ `
  vec3 seaSurface(vec2 p, float t) {
    vec3 result = vec3(0.0);
    ${WAVES.map(w => `{
      float k = ${(Math.PI * 2 / w.length).toFixed(8)};
      vec2 d = vec2(${w.x}, ${w.z});
      float phase = k * dot(d, p) - sqrt(9.81 * k) * t + ${w.phase};
      result.y += sin(phase) * ${w.amplitude};
      result.xz += cos(phase) * ${w.amplitude} * k * d;
    }`).join("\n")}
    return result;
  }
`;

/** Concentrate vertices around the viewer while retaining a continuous horizon. */
export function oceanGeometry(segments = 256) {
  const geometry = new THREE.PlaneGeometry(2, 2, segments, segments);
  const p = geometry.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i);
    p.setXY(i, Math.sign(x) * Math.pow(Math.abs(x), 3) * 2400,
      Math.sign(y) * Math.pow(Math.abs(y), 3) * 2400);
  }
  geometry.computeBoundingSphere();
  return geometry;
}
