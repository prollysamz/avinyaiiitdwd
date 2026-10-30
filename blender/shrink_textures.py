"""
Downsize the images embedded in a .glb without touching anything else (geometry, morph targets,
node names, meshopt streams are copied byte-for-byte; only image buffer views are re-encoded).

  python blender/shrink_textures.py in.glb out.glb [max_px=1024] [quality=82]
"""
import io
import json
import struct
import sys

from PIL import Image

src, dst = sys.argv[1], sys.argv[2]
MAX = int(sys.argv[3]) if len(sys.argv) > 3 else 1024
Q = int(sys.argv[4]) if len(sys.argv) > 4 else 82

data = open(src, "rb").read()
assert data[:4] == b"glTF"
jlen = struct.unpack_from("<I", data, 12)[0]
doc = json.loads(data[20:20 + jlen])
bstart = 20 + jlen
blen = struct.unpack_from("<I", data, bstart)[0]
bin0 = data[bstart + 8:bstart + 8 + blen]

# which buffer views hold images, and how to re-encode them
image_views = {}
for img in doc.get("images", []):
    if "bufferView" in img:
        image_views[img["bufferView"]] = img.get("mimeType", "image/webp")


def shrink(raw, mime):
    im = Image.open(io.BytesIO(raw))
    if max(im.size) > MAX:
        s = MAX / max(im.size)
        im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    out = io.BytesIO()
    if mime == "image/png":
        im.save(out, "PNG", optimize=True)
    elif mime == "image/jpeg":
        im.convert("RGB").save(out, "JPEG", quality=Q, optimize=True)
    else:
        im.save(out, "WEBP", quality=Q, method=6)
    new = out.getvalue()
    return new if len(new) < len(raw) else raw


# Every region of buffer 0 that something points at: plain buffer views, and the compressed
# streams that EXT_meshopt_compression keeps in buffer 0 (their parent view points at a fallback buffer).
out = bytearray()


def place(chunk):
    while len(out) % 4:
        out.append(0)
    off = len(out)
    out.extend(chunk)
    return off


for i, bv in enumerate(doc["bufferViews"]):
    ext = bv.get("extensions", {}).get("EXT_meshopt_compression")
    if ext and ext.get("buffer", 0) == 0:
        chunk = bin0[ext.get("byteOffset", 0):ext.get("byteOffset", 0) + ext["byteLength"]]
        ext["byteOffset"] = place(chunk)
    if bv.get("buffer", 0) == 0 and not (ext and doc["buffers"][bv["buffer"]].get("extensions", {}).get("EXT_meshopt_compression", {}).get("fallback")):
        chunk = bin0[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]
        if i in image_views:
            before = len(chunk)
            chunk = shrink(chunk, image_views[i])
            print(f"  image view {i}: {before // 1024} KB -> {len(chunk) // 1024} KB")
        bv["byteOffset"] = place(chunk)
        bv["byteLength"] = len(chunk)

while len(out) % 4:
    out.append(0)
doc["buffers"][0]["byteLength"] = len(out)

js = json.dumps(doc, separators=(",", ":")).encode()
js += b" " * ((4 - len(js) % 4) % 4)
total = 12 + 8 + len(js) + 8 + len(out)
with open(dst, "wb") as f:
    f.write(struct.pack("<III", 0x46546C67, 2, total))
    f.write(struct.pack("<I", len(js)) + b"JSON" + js)
    f.write(struct.pack("<I", len(out)) + b"BIN\x00" + bytes(out))
print(f"{src}: {len(data) // 1024} KB -> {total // 1024} KB")
