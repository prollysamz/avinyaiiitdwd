import * as THREE from "three";
import { waveGLSL } from "./waves";

/**
 * Planar-reflection ocean. Mirror technique adapted from three.js' Water (MIT),
 * with an HDR mirror target and a physically-motivated shading model:
 * Fresnel reflection of the real scene + sky, depth-tinted body colour, sun glitter,
 * and normal-map detail that flattens with distance to avoid shimmer.
 */
export class Ocean extends THREE.Mesh {
  declare material: THREE.ShaderMaterial;
  renderTarget: THREE.WebGLRenderTarget;
  /** re-render the reflection every N frames (low tier reuses the previous one) */
  reflectEvery = 1;
  private frame = 0;

  constructor(geometry: THREE.BufferGeometry, normals: THREE.Texture, res = 1024) {
    super(geometry);
    const scope = this;
    const mirrorPlane = new THREE.Plane();
    const normal = new THREE.Vector3();
    const mirrorWorldPosition = new THREE.Vector3();
    const cameraWorldPosition = new THREE.Vector3();
    const rotationMatrix = new THREE.Matrix4();
    const lookAtPosition = new THREE.Vector3(0, 0, -1);
    const clipPlane = new THREE.Vector4();
    const view = new THREE.Vector3();
    const target = new THREE.Vector3();
    const q = new THREE.Vector4();
    const textureMatrix = new THREE.Matrix4();
    const mirrorCamera = new THREE.PerspectiveCamera();
    const eye = new THREE.Vector3();

    this.renderTarget = new THREE.WebGLRenderTarget(res, res, { type: THREE.HalfFloatType });
    const renderTarget = this.renderTarget;

    this.material = new THREE.ShaderMaterial({
      lights: true,
      fog: true,
      uniforms: THREE.UniformsUtils.merge([
        THREE.UniformsLib["fog"],
        THREE.UniformsLib["lights"],
        {
          normalSampler: { value: normals },
          mirrorSampler: { value: null },
          time: { value: 0 },
          distortionScale: { value: 1.6 },
          normalStrength: { value: 0.85 },
          textureMatrix: { value: textureMatrix },
          sunColor: { value: new THREE.Color() },
          sunDirection: { value: new THREE.Vector3(0, 1, 0) },
          eye: { value: eye },
          uDeep: { value: new THREE.Color() },
          uShallow: { value: new THREE.Color() },
          uGlint: { value: 1 },
          uBoatInverse: { value: new THREE.Matrix4() },
          uBoatMask: { value: 0 },
          uWakeStrength: { value: 0.35 },
        },
      ]),
      vertexShader: /* glsl */ `
        uniform mat4 textureMatrix;
        uniform float time;
        uniform vec3 eye;
        varying vec4 mirrorCoord;
        varying vec4 worldPosition;
        #include <common>
        #include <fog_pars_vertex>
        #include <shadowmap_pars_vertex>
        ${waveGLSL}
        void main() {
          worldPosition = modelMatrix * vec4(position, 1.0);
          float fade = 1.0 - smoothstep(180.0, 600.0, length(worldPosition.xz - eye.xz));
          worldPosition.y += seaSurface(worldPosition.xz, time).y * fade;
          // The reflection is projected onto the mean sea plane.
          mirrorCoord = textureMatrix * vec4(worldPosition.x, 0.0, worldPosition.z, 1.0);
          vec4 mvPosition = viewMatrix * worldPosition;
          gl_Position = projectionMatrix * mvPosition;
          #include <beginnormal_vertex>
          #include <defaultnormal_vertex>
          #include <fog_vertex>
          #include <shadowmap_vertex>
        }`,
      fragmentShader: /* glsl */ `
        uniform sampler2D mirrorSampler;
        uniform sampler2D normalSampler;
        uniform float time, distortionScale, normalStrength, uGlint;
        uniform mat4 uBoatInverse;
        uniform float uBoatMask, uWakeStrength;
        uniform vec3 sunColor, sunDirection, eye, uDeep, uShallow;
        varying vec4 mirrorCoord;
        varying vec4 worldPosition;
        #include <common>
        #include <packing>
        #include <bsdfs>
        #include <fog_pars_fragment>
        #include <lights_pars_begin>
        #include <shadowmap_pars_fragment>
        #include <shadowmask_pars_fragment>
        ${waveGLSL}

        vec3 waterNormal(vec2 p, float dist) {
          // Blender Ocean spectrum, with separate wind-driven capillary detail.
          vec2 a = texture2D(normalSampler, p / 64.0 + vec2(0.012, 0.007) * time).xy * 2.0 - 1.0;
          vec2 b = texture2D(normalSampler, mat2(0.8, -0.6, 0.6, 0.8) * p / 17.0 + vec2(-0.018, 0.009) * time).xy * 2.0 - 1.0;
          vec2 c = texture2D(normalSampler, p / 4.3 + vec2(0.025, -0.016) * time).xy * 2.0 - 1.0;
          float nearK = 1.0 - smoothstep(12.0, 100.0, dist);
          vec2 detail = (a * 0.65 + b * 0.28 + c * 0.13 * nearK) * normalStrength;
          float fade = 1.0 - smoothstep(180.0, 600.0, dist);
          vec2 slope = seaSurface(p, time).xz * fade;
          detail *= 1.0 - smoothstep(70.0, 500.0, dist);
          return normalize(vec3(-slope.x + detail.x, 1.0, -slope.y + detail.y));
        }

        void main() {
          // Remove the water surface inside the hull, including when it heels.
          vec3 boatLocal = (uBoatInverse * worldPosition).xyz;
          float hullU = clamp(0.5 - boatLocal.z / 4.6, 0.0, 1.0);
          float beam = hullU < 0.58 ? 0.78 * (0.66 + 0.34 * sin(hullU / 0.58 * 1.570796)) : 0.78 * pow(max(0.0, cos(min((hullU - 0.58) / 0.42, 1.0) * 1.570796)), 0.78);
          // Intersect the actual flared hull section at this wave height. A full
          // deck-width cutout left a visible air gap beside the narrower bilge.
          float sheer = 0.62 + 0.42 * hullU * hullU + 0.16 * pow(1.0 - hullU, 3.0);
          float depth = 0.78 * (1.0 - pow(hullU, 3.0) * 0.88) * (0.72 + 0.28 * sin(3.141593 * min(hullU + 0.12, 1.0)));
          float section = clamp(1.0 - (sheer - (boatLocal.y + 0.34)) / max(depth, 0.01), 0.0, 1.0);
          float side = pow(section, 1.0 / 2.3);
          float waterBeam = beam * side * (1.0 + 0.09 * (1.0 - side) * (1.0 - hullU * 0.5));
          if (uBoatMask > 0.5 && abs(boatLocal.z) < 2.3 && abs(boatLocal.x) < waterBeam * 0.98) discard;
          vec3 toEye = eye - worldPosition.xyz;
          float dist = length(toEye);
          vec3 V = toEye / dist;
          vec3 N = waterNormal(worldPosition.xz, dist);
          // Divergent Kelvin wake and the narrow, turbulent stern trail, attached
          // to the same hull transform used by the water cutout.
          float aft = max(boatLocal.z - 1.5, 0.0);
          float wakeBand = abs(abs(boatLocal.x) - (0.66 + aft * 0.354));
          float wakeEnvelope = smoothstep(0.0, 1.0, aft) * exp(-aft * 0.12) * uBoatMask;
          float wake = exp(-wakeBand * wakeBand / (0.025 + aft * 0.018)) * wakeEnvelope;
          float pulse = sin(aft * 7.5 - time * 4.4 + abs(boatLocal.x) * 3.0);
          N = normalize(N + vec3(sign(boatLocal.x) * pulse, 0.0, pulse * 0.35) * wake * 0.13 * uWakeStrength);

          // Normalized dot products can round just above 1 on the GPU.
          // A negative Fresnel pow base produces NaNs that bloom spreads
          // across the entire frame as the camera turns between islands.
          float NV = clamp(dot(N, V), 0.0, 1.0);
          float F = 0.02037 + 0.97963 * pow(1.0 - NV, 5.0);

          vec2 distortion = N.xz * (0.002 + 0.6 / dist) * distortionScale;
          // rough water smears reflections vertically; more so with distance and at grazing angles
          vec2 ruv = clamp(mirrorCoord.xy / mirrorCoord.w + distortion, vec2(0.002), vec2(0.998));
          float smear = (0.0025 + 0.012 * smoothstep(8.0, 160.0, dist)) * (0.6 + 0.8 * (1.0 - NV));
          vec3 refl = texture2D(mirrorSampler, ruv).rgb * 0.28
            + texture2D(mirrorSampler, ruv + vec2(0.0, smear)).rgb * 0.2
            + texture2D(mirrorSampler, ruv - vec2(0.0, smear)).rgb * 0.2
            + texture2D(mirrorSampler, ruv + vec2(smear * 0.25, smear * 2.2)).rgb * 0.16
            + texture2D(mirrorSampler, ruv - vec2(smear * 0.25, smear * 2.2)).rgb * 0.16;

          float tilt = 1.0 - N.y;
          vec3 body = mix(uDeep, uShallow, clamp(0.12 + max(worldPosition.y, 0.0) * 0.65 + tilt * 2.0, 0.0, 0.6));
          float sunUp = max(sunDirection.y, 0.0);
          // sub-surface glow on crests facing the sun
          float sss = pow(max(dot(normalize(vec3(sunDirection.x, 0.0, sunDirection.z)), -V), 0.0), 3.0) * clamp(tilt * 14.0, 0.0, 1.0);
          body = body * (0.8 + 0.4 * max(dot(N, sunDirection), 0.0)) + uShallow * sss * 0.8 * sunColor + refl * 0.06;
          body *= mix(0.6, 1.0, getShadowMask());

          // GGX sun glitter with derivative filtering to keep tiny facets stable.
          vec3 H = normalize(V + sunDirection);
          float NH = clamp(dot(N, H), 0.0, 1.0);
          float NL = clamp(dot(N, sunDirection), 0.0, 1.0);
          float roughness = 0.14 + smoothstep(25.0, 220.0, dist) * 0.09;
          float alpha2 = pow(roughness, 4.0) + min(dot(fwidth(N), fwidth(N)) * 0.08, 0.015);
          float denom = NH * NH * (alpha2 - 1.0) + 1.0;
          float D = alpha2 / max(3.141593 * denom * denom, 0.00001);
          float visibility = 0.5 / max(NL * sqrt(NV * NV * (1.0 - alpha2) + alpha2) + NV * sqrt(NL * NL * (1.0 - alpha2) + alpha2), 0.001);
          float VH = clamp(dot(V, H), 0.0, 1.0);
          float FH = 0.02037 + 0.97963 * pow(1.0 - VH, 5.0);
          vec3 glitter = sunColor * min(D * visibility * FH * NL, 8.0) * uGlint * 1.8 * getShadowMask();
          glitter *= smoothstep(0.0, 0.05, sunDirection.y + 0.05);

          vec3 col = mix(body, refl, F) + glitter;
          float bubbles = texture2D(normalSampler, boatLocal.xz * 0.47 + vec2(0.0, -time * 0.17)).r;
          float trail = exp(-boatLocal.x * boatLocal.x / (0.08 + aft * 0.025)) * exp(-aft * 0.24) * smoothstep(0.0, 0.7, aft) * uBoatMask;
          float foam = clamp((wake * 0.32 + trail * 0.36) * smoothstep(0.38, 0.58, bubbles) * uWakeStrength, 0.0, 0.55);
          vec3 foamColor = mix(vec3(0.45, 0.59, 0.6), sunColor * 0.65, 0.35) * (0.4 + sunUp);
          col = mix(col, foamColor, foam);

          gl_FragColor = vec4(col, 1.0);
          #include <fog_fragment>
        }`,
    });

    // merge() nulls render-target textures, so assign these after construction
    this.material.uniforms.mirrorSampler.value = renderTarget.texture;
    this.material.uniforms.normalSampler.value = normals;
    this.material.uniforms.textureMatrix.value = textureMatrix;
    this.material.uniforms.eye.value = eye;

    this.onBeforeRender = function (renderer, scene, camera) {
      mirrorWorldPosition.setFromMatrixPosition(scope.matrixWorld);
      cameraWorldPosition.setFromMatrixPosition(camera.matrixWorld);
      rotationMatrix.extractRotation(scope.matrixWorld);
      normal.set(0, 0, 1).applyMatrix4(rotationMatrix);
      view.subVectors(mirrorWorldPosition, cameraWorldPosition);
      if (view.dot(normal) > 0) return;
      scope.frame++;
      // skipped frames keep the previous reflection and the texture matrix it was rendered with
      if (scope.reflectEvery > 1 && scope.frame % scope.reflectEvery !== 0) { eye.setFromMatrixPosition(camera.matrixWorld); return; }
      view.reflect(normal).negate().add(mirrorWorldPosition);
      rotationMatrix.extractRotation(camera.matrixWorld);
      lookAtPosition.set(0, 0, -1).applyMatrix4(rotationMatrix).add(cameraWorldPosition);
      target.subVectors(mirrorWorldPosition, lookAtPosition).reflect(normal).negate().add(mirrorWorldPosition);
      mirrorCamera.position.copy(view);
      mirrorCamera.up.set(0, 1, 0).applyMatrix4(rotationMatrix).reflect(normal);
      mirrorCamera.lookAt(target);
      mirrorCamera.far = (camera as THREE.PerspectiveCamera).far;
      mirrorCamera.updateMatrixWorld();
      mirrorCamera.projectionMatrix.copy((camera as THREE.PerspectiveCamera).projectionMatrix);

      textureMatrix.set(0.5, 0, 0, 0.5, 0, 0.5, 0, 0.5, 0, 0, 0.5, 0.5, 0, 0, 0, 1);
      textureMatrix.multiply(mirrorCamera.projectionMatrix).multiply(mirrorCamera.matrixWorldInverse);

      mirrorPlane.setFromNormalAndCoplanarPoint(normal, mirrorWorldPosition).applyMatrix4(mirrorCamera.matrixWorldInverse);
      clipPlane.set(mirrorPlane.normal.x, mirrorPlane.normal.y, mirrorPlane.normal.z, mirrorPlane.constant);
      const pm = mirrorCamera.projectionMatrix;
      q.x = (Math.sign(clipPlane.x) + pm.elements[8]) / pm.elements[0];
      q.y = (Math.sign(clipPlane.y) + pm.elements[9]) / pm.elements[5];
      q.z = -1;
      q.w = (1 + pm.elements[10]) / pm.elements[14];
      clipPlane.multiplyScalar(2 / clipPlane.dot(q));
      pm.elements[2] = clipPlane.x; pm.elements[6] = clipPlane.y; pm.elements[10] = clipPlane.z + 1; pm.elements[14] = clipPlane.w;

      eye.setFromMatrixPosition(camera.matrixWorld);

      const prevTarget = renderer.getRenderTarget();
      const prevXr = renderer.xr.enabled;
      const prevShadow = renderer.shadowMap.autoUpdate;
      scope.visible = false;
      renderer.xr.enabled = false;
      renderer.shadowMap.autoUpdate = false;
      renderer.setRenderTarget(renderTarget);
      renderer.state.buffers.depth.setMask(true);
      if (renderer.autoClear === false) renderer.clear();
      renderer.render(scene, mirrorCamera);
      scope.visible = true;
      renderer.xr.enabled = prevXr;
      renderer.shadowMap.autoUpdate = prevShadow;
      renderer.setRenderTarget(prevTarget);
    };
  }
}
