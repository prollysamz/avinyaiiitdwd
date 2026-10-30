The live ocean
==============

`ocean.blend` is the editable Blender 5.2 source. Its Ocean modifier uses a
64-metre spectral patch, 9 m/s wind, seed 23, directional waves and choppiness.
The water material has IOR 1.333, transmission and volume absorption for Blender
rendering. Existing boat and island files are independent and remain editable.

Regenerate the website's seamless, linear normal texture from the evaluated
Blender Ocean modifier:

    "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python blender/ocean.py

Run from the project root. This writes `public/textures/water/ocean-normal.png`
and saves `blender/ocean.blend`. The PNG contains signed X/Y surface normals in
red/green, encoded from [-1,1] to [0,1]; load with no sRGB conversion.

The website combines the Blender spectrum at three moving scales with four
displaced deep-water swells, planar scene reflections, Fresnel reflection with
water's 0.02037 normal-incidence reflectance, filtered GGX sunlight, and a
hull-attached wake. The wave field in `components/world/waves.ts` drives both
the mesh and boat buoyancy. Fine ripples fade with distance to reduce shimmer.
The camera-centred grid concentrates vertices nearby; mobile uses fewer cells.
Reduced motion freezes the shared scene clock, including water and the wake.

Blender's volume, simulation and node materials do not survive glTF export.
The browser therefore uses its own real-time shader, rather than a static
ocean GLB. The Blender normal field is advected and layered at runtime; this
is not a full frame-by-frame fluid simulation. The shallow tint is artistic,
not a sampled seabed-depth pass.
