"""The page's copies of our field photographs: kansai/img/field/<YYYYMMDD_HHMMSS>.jpg (long side 1280 px, JPEG q78)
and <…>_t.jpg (360 px, q72), orientation applied and every byte of metadata dropped (the position shown on the map
comes from manifest.json, never from the file). The name is the photograph's EXIF time, which the QA gate compares
with the time shown on the page.

    python3 publish.py <dir with manifest.json and orig/> <kansai/img/field>

Left out, after looking at every photograph: IMG_5170 and IMG_5171 (donors' names legible on the fence posts) and
IMG_5164 (repeats IMG_5163)."""
import json, os, sys
from PIL import Image, ImageOps
SRC, OUT = sys.argv[1], sys.argv[2]
SKIP = {"IMG_5170.JPG", "IMG_5171.JPG", "IMG_5164.JPG"}
os.makedirs(OUT, exist_ok=True)
m = [x for x in json.load(open(os.path.join(SRC, "manifest.json"))) if not x.get("track")]
done = []
for x in sorted(m, key=lambda x: x["time"]):
    if x["file"] in SKIP: continue
    t = x["time"].replace(":", "").replace(" ", "_")          # 2025:09:28 10:37:32 -> 20250928_103732
    im = ImageOps.exif_transpose(Image.open(os.path.join(SRC, "orig", x["file"]))).convert("RGB")
    a = im.copy(); a.thumbnail((1280, 1280), Image.LANCZOS)
    fa = os.path.join(OUT, f"{t}.jpg"); a.save(fa, "JPEG", quality=78, optimize=True, progressive=True)
    b = im.copy(); b.thumbnail((360, 360), Image.LANCZOS)
    fb = os.path.join(OUT, f"{t}_t.jpg"); b.save(fb, "JPEG", quality=72, optimize=True, progressive=True)
    done.append((x["file"], os.path.basename(fa), a.size))
for d in done: print(*d)
bad = [f for f in os.listdir(OUT) if Image.open(os.path.join(OUT, f)).getexif()]
print(len(done), "photographs;", "metadata left in:", bad or "none")
