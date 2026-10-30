"""blender --background --python blender/preview.py -- <in.glb> <out.png> <preset>   (presets: boat, island, wheel, city)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

A = lib.args()
glb, out, preset = A[0], A[1], (A[2] if len(A) > 2 else "boat")
PRESETS = {
    "boat": {"stern": ((-6.2, -8.6, 3.0), (0, 0.2, 1.7)), "bow": ((5.5, 8.2, 2.4), (0, 0.0, 1.4)), "deck": ((-2.0, -4.0, 2.4), (0, -0.8, 0.9)), "side": ((-8.5, 0.5, 1.2), (0, 0.0, 1.7)), "top": ((-0.5, -3.5, 6.0), (0, -0.4, 0.8))},
    "island": {"front": ((-5, -17, 5.5), (0, 0, 3.6)), "close": ((-9, -9.5, 3.2), (-0.5, 0, 3.2)), "back": ((8, 15, 6), (0, 0, 3.5))},
    "wheel": {"front": ((0, -34, 7.5), (0, 0, 7.2)), "three": ((-16, -22, 6), (0, 0, 6.5)), "low": ((-5, -14, 1.5), (0, 0, 4.5))},
    "city": {"front": ((0, -34, 10), (0, 0, 8)), "three": ((-20, -26, 9), (0, 0, 7))},
}
sea = preset in ("boat",)
lib.preview_glb(glb, out, PRESETS[preset], sea=sea, samples=int(os.environ.get("SAMPLES", "40")))
