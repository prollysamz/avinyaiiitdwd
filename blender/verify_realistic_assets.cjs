// Verify the exported assets the website loads, including animation contracts.
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const root = path.resolve(__dirname, "..");
const expected = {
  boat: ["Boat_Body", "Sail_Main", "Sail_Jib", "Flag", "Rudder", "Tiller", "Lantern"],
  outpost: ["Outpost_Body"],
  city: ["City"],
  wheel: ["Wheel_Frame", "Wheel_Rotor", ...Array.from({length: 12}, (_, i) => `Cab${i}`)],
};
for (const [kind, names] of Object.entries(expected)) {
  const bytes = fs.readFileSync(path.join(root, "public/models", `${kind}-realistic.glb`));
  assert.equal(bytes.toString("ascii", 0, 4), "glTF");
  assert.equal(bytes.readUInt32LE(8), bytes.length, `${kind}: truncated GLB`);
  const json = JSON.parse(bytes.toString("utf8", 20, 20 + bytes.readUInt32LE(12)));
  const nodeNames = new Set(json.nodes.map(n => n.name));
  names.forEach(name => assert(nodeNames.has(name), `${kind}: missing animated node ${name}`));
  (json.images || []).forEach(image => assert(image.bufferView !== undefined, `${kind}: external image dependency`));
  assert(!Array.from(nodeNames).some(name => /AVINYA|^Text(?:\.\d+)?$/i.test(name || "")), `${kind}: unexpected lettering geometry`);
  if (kind === "boat") {
    for (const name of ["Sail_Main", "Sail_Jib"]) {
      const node = json.nodes.find(n => n.name === name);
      const mesh = json.meshes[node.mesh];
      assert(mesh.extras.targetNames.includes("Billow"), `${name}: missing Billow`);
      assert(mesh.extras.targetNames.includes("Flutter"), `${name}: missing Flutter`);
      assert(mesh.primitives.every(p => p.targets.length >= 2), `${name}: missing morph buffers`);
    }
  }
  console.log(`PASS ${kind}: ${names.length} required nodes; ${json.images?.length || 0} embedded maps; ${(bytes.length / 1048576).toFixed(1)} MiB`);
}
for (const kind of ["sand", "rock", "ground", "concrete"]) {
  for (const suffix of ["color", "normal", "roughness"]) {
    const bytes = fs.readFileSync(path.join(root, "public/textures/coast", `${kind}-${suffix}.png`));
    assert.equal(bytes.readUInt32BE(16), 1024);
    assert.equal(bytes.readUInt32BE(20), 1024);
  }
}
console.log("PASS coastal textures: 12 PBR maps at 1024 × 1024");
