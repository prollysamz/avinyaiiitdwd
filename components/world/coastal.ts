import { useTexture } from "@react-three/drei";
import { useMemo } from "react";
import * as THREE from "three";

type Surface = "sand" | "rock" | "ground" | "concrete";
type Shader = { vertexShader: string; fragmentShader: string; uniforms: Record<string, THREE.IUniform> };

/** Blender-baked four-metre surfaces, projected on all three axes so vertical
 * cliffs retain their grain instead of stretching a top-down UV into stripes. */
export function useCoastalSurface(kind: Surface) {
  const textures = useTexture([
    `/textures/coast/${kind}-color.jpg`,
    `/textures/coast/${kind}-normal.jpg`,
    `/textures/coast/${kind}-roughness.jpg`,
  ]);
  return useMemo(() => {
    textures.forEach((t, i) => {
      t.wrapS = t.wrapT = THREE.RepeatWrapping;
      t.colorSpace = i === 0 ? THREE.SRGBColorSpace : THREE.NoColorSpace;
      t.anisotropy = 8;
      t.needsUpdate = true;
    });
    return { map: textures[0], normalMap: textures[1], roughnessMap: textures[2] };
  }, [textures]);
}

/** Sand collects on the flatter desert shelves and low beach; exposed slopes
 * retain the rock/soil surface. Both layers share the same world-scale mapping. */
export function useCoastalTerrain(kind: "desert" | "meadow") {
  const base = useCoastalSurface(kind === "desert" ? "rock" : "ground");
  const sand = useCoastalSurface("sand");
  return useMemo(() => ({
    ...base,
    customProgramCacheKey: () => `coastal-${kind}-v2`,
    onBeforeCompile: (shader: Shader) => {
      coastalShader(shader);
      shader.uniforms.uCoastSand = { value: sand.map };
      shader.uniforms.uCoastSandNormal = { value: sand.normalMap };
      shader.uniforms.uCoastSandRoughness = { value: sand.roughnessMap };
      shader.fragmentShader = shader.fragmentShader
        .replace("#include <common>", `#include <common>
          uniform sampler2D uCoastSand, uCoastSandNormal, uCoastSandRoughness;`)
        .replace("diffuseColor *= coastSample(map, vCoastPosition, coastW);", `
          float coastBeach = ${kind === "desert"
            ? "smoothstep(0.72, 0.94, coastN.y) * (1.0 - smoothstep(2.7, 4.0, vCoastHeight))"
            : "1.0 - smoothstep(0.35, 1.05, vCoastHeight)"};
          diffuseColor *= mix(coastSample(map, vCoastPosition, coastW),
            coastSample(uCoastSand, vCoastPosition, coastW), coastBeach);`)
        .replace("float roughnessFactor = roughness * coastSample(roughnessMap, vCoastPosition, coastW).g;", `
          float roughnessFactor = roughness * mix(coastSample(roughnessMap, vCoastPosition, coastW).g,
            coastSample(uCoastSandRoughness, vCoastPosition, coastW).g, coastBeach);`)
        .replace("tx.xy *= normalScale;", `
          tx = mix(tx, texture2D(uCoastSandNormal, vCoastPosition.zy / 4.0).xyz * 2.0 - 1.0, coastBeach);
          ty = mix(ty, texture2D(uCoastSandNormal, vCoastPosition.xz / 4.0).xyz * 2.0 - 1.0, coastBeach);
          tz = mix(tz, texture2D(uCoastSandNormal, vCoastPosition.xy / 4.0).xyz * 2.0 - 1.0, coastBeach);
          tx.xy *= normalScale;`);
    },
  }), [base, sand, kind]);
}

export function coastalShader(shader: Shader) {
  shader.vertexShader = shader.vertexShader
    .replace("#include <common>", `#include <common>
      varying vec3 vCoastPosition;
      varying vec3 vCoastNormal;
      varying float vCoastHeight;`)
    .replace("#include <worldpos_vertex>", `#include <worldpos_vertex>
      vCoastPosition = transformed;
      vCoastNormal = normalize(objectNormal);
      vCoastHeight = (modelMatrix * vec4(transformed, 1.0)).y;`);
  shader.fragmentShader = shader.fragmentShader
    .replace("#include <common>", `#include <common>
      uniform mat3 normalMatrix;
      varying vec3 vCoastPosition;
      varying vec3 vCoastNormal;
      varying float vCoastHeight;
      vec3 coastWeights(vec3 n) {
        vec3 w = pow(abs(n), vec3(4.0));
        return w / max(w.x + w.y + w.z, 0.0001);
      }
      vec4 coastSample(sampler2D tex, vec3 p, vec3 w) {
        return texture2D(tex, p.zy / 4.0) * w.x
          + texture2D(tex, p.xz / 4.0) * w.y
          + texture2D(tex, p.xy / 4.0) * w.z;
      }
      float coastNoise(vec3 p) {
        vec3 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
        vec4 a = vec4(dot(i,vec3(127.1,311.7,74.7))) + vec4(0.0,127.1,311.7,438.8);
        vec4 lo = fract(sin(a)*43758.5453);
        vec4 hi = fract(sin(a+74.7)*43758.5453);
        return mix(mix(mix(lo.x,lo.y,f.x),mix(lo.z,lo.w,f.x),f.y),
          mix(mix(hi.x,hi.y,f.x),mix(hi.z,hi.w,f.x),f.y),f.z);
      }
      float coastRelief(vec3 p, float slope) {
        float warp = coastNoise(p*.7);
        float seam = pow(.5+.5*sin(p.y*24.0+warp*12.0), 12.0);
        return (coastNoise(p*5.0)*.018 + coastNoise(p*17.0)*.005 - seam*.009) * slope;
      }`)
    .replace("#include <map_fragment>", `
      vec3 coastN = normalize(vCoastNormal);
      vec3 coastW = coastWeights(coastN);
      diffuseColor *= coastSample(map, vCoastPosition, coastW);
      float rockSlope = 1.0 - smoothstep(0.55, 0.93, abs(coastN.y));
      float strata = .5+.5*sin(vCoastPosition.y*24.0+coastNoise(vCoastPosition*.7)*12.0);
      diffuseColor.rgb *= mix(1.0, .87 + .16*strata, rockSlope);
      diffuseColor.rgb *= .91 + .18*coastNoise(vCoastPosition*2.3);
      // Fine salt staining above the tide, dark saturated stone beneath it.
      float salt = (1.0 - smoothstep(0.25, 0.75, vCoastHeight)) * smoothstep(0.04, 0.22, vCoastHeight);
      diffuseColor.rgb = mix(diffuseColor.rgb, diffuseColor.rgb * 1.12 + vec3(0.025), salt * 0.3);`)
    .replace("#include <roughnessmap_fragment>", `
      float roughnessFactor = roughness * coastSample(roughnessMap, vCoastPosition, coastW).g;
      float wet = 1.0 - smoothstep(0.02, 0.55, vCoastHeight);
      roughnessFactor = mix(roughnessFactor, 0.21, wet * 0.8);
      diffuseColor.rgb *= mix(1.0, 0.57, wet);`)
    .replace("#include <normal_fragment_maps>", `
      vec3 tx = texture2D(normalMap, vCoastPosition.zy / 4.0).xyz * 2.0 - 1.0;
      vec3 ty = texture2D(normalMap, vCoastPosition.xz / 4.0).xyz * 2.0 - 1.0;
      vec3 tz = texture2D(normalMap, vCoastPosition.xy / 4.0).xyz * 2.0 - 1.0;
      tx.xy *= normalScale; ty.xy *= normalScale; tz.xy *= normalScale;
      // Whiteout blending preserves the geometric normal for a flat normal map.
      vec3 nx = normalize(vec3(coastN.x * abs(tx.z), coastN.y + tx.y, coastN.z + tx.x));
      vec3 ny = normalize(vec3(coastN.x + ty.x, coastN.y * abs(ty.z), coastN.z + ty.y));
      vec3 nz = normalize(vec3(coastN.x + tz.x, coastN.y + tz.y, coastN.z * abs(tz.z)));
      vec3 localN = normalize(nx * coastW.x + ny * coastW.y + nz * coastW.z);
      normal = normalize(normalMatrix * localN) * faceDirection;
      // Screen-space surface gradient adds centimetre relief without changing
      // silhouettes or stretching the texture over a cliff face.
      float relief = coastRelief(vCoastPosition, rockSlope);
      vec3 dpdx = dFdx(-vViewPosition), dpdy = dFdy(-vViewPosition);
      vec3 rx = cross(dpdy, normal), ry = cross(normal, dpdx);
      float determinant = dot(dpdx, rx);
      normal = normalize(abs(determinant)*normal - sign(determinant)*
        (dFdx(relief)*rx + dFdy(relief)*ry));
    `);
}
