"""The page's copies of our field photographs: kansai/img/field/<YYYYMMDD_HHMMSS>.jpg (long side 1280 px, JPEG q78)
and <…>_t.jpg (360 px, q72), orientation applied and every byte of metadata dropped (the position shown on the map
comes from manifest.json, never from the file). The name is the photograph's EXIF time, which the QA gate compares
with the time shown on the page.

    python3 publish.py <dir with manifest.json and orig/> <kansai/img/field>

Left out, after looking at every photograph: IMG_5170 and IMG_5171 (donors' names legible on the fence posts), and
three re-takes of a view taken seconds before or after: IMG_5153 (of IMG_5155), IMG_5164 (of IMG_5163) and IMG_5172
(of IMG_5173). Blurred before any copy is made (REDACT, boxes as fractions of the upright frame): the faces of two
passers-by in IMG_5177 and an address plate in IMG_5156.

Clips become <…>.mp4 (H.264, long side 1280 px, 30 fps, no sound, no metadata: the phone's location keys, device and
dates are dropped) with ingest's still at 0.5 s as <…>.jpg and <…>_t.jpg."""
import json, os, sys, shutil, subprocess
from PIL import Image, ImageOps, ImageFilter
SRC, OUT = sys.argv[1], sys.argv[2]
SKIP = {"IMG_5170.JPG", "IMG_5171.JPG", "IMG_5153.JPG", "IMG_5164.JPG", "IMG_5172.JPG"}
REDACT = {"IMG_5177.JPG": [(0.460, 0.690, 0.515, 0.760), (0.684, 0.688, 0.736, 0.756)],   # two passers-by: faces
          "IMG_5156.JPG": [(0.508, 0.395, 0.523, 0.470)]}                                # the house's address plate
def ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe: return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()
def redact(im, boxes):
    for x0, y0, x1, y1 in boxes:
        b = tuple(int(round(v)) for v in (x0 * im.width, y0 * im.height, x1 * im.width, y1 * im.height))
        r = im.crop(b); im.paste(r.resize((max(1, r.width // 24), max(1, r.height // 24))).resize(r.size).filter(ImageFilter.GaussianBlur(max(r.size) / 12)), b)
    return im
os.makedirs(OUT, exist_ok=True)
m = [x for x in json.load(open(os.path.join(SRC, "manifest.json"))) if not x.get("track")]
done = []
for x in sorted(m, key=lambda x: x["time"]):
    if x["file"] in SKIP: continue
    t = x["time"].replace(":", "").replace(" ", "_")          # 2025:09:28 10:37:32 -> 20250928_103732
    if x.get("video"):
        fv = os.path.join(OUT, f"{t}.mp4")
        subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", os.path.join(SRC, "orig", x["file"]),
                        "-map", "0:v:0", "-an", "-sn", "-dn", "-map_metadata", "-1", "-map_chapters", "-1",
                        "-vf", "scale='if(gt(iw,ih),1280,-2)':'if(gt(iw,ih),-2,1280)':flags=lanczos,fps=30",
                        "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart", fv], check=True)
        im = Image.open(os.path.join(SRC, x["web"])).convert("RGB")     # ingest's still at 0.5 s
    else:
        im = ImageOps.exif_transpose(Image.open(os.path.join(SRC, "orig", x["file"]))).convert("RGB")
    if x["file"] in REDACT: im = redact(im, REDACT[x["file"]])
    a = im.copy(); a.thumbnail((1280, 1280), Image.LANCZOS)
    fa = os.path.join(OUT, f"{t}.jpg"); a.save(fa, "JPEG", quality=78, optimize=True, progressive=True)
    b = im.copy(); b.thumbnail((360, 360), Image.LANCZOS)
    fb = os.path.join(OUT, f"{t}_t.jpg"); b.save(fb, "JPEG", quality=72, optimize=True, progressive=True)
    done.append((x["file"], os.path.basename(fa), a.size))
for d in done: print(*d)
bad = [f for f in os.listdir(OUT) if f.endswith(".jpg") and Image.open(os.path.join(OUT, f)).getexif()]
bad += [f for f in os.listdir(OUT) if f.endswith(".mp4") and any(k in open(os.path.join(OUT, f), "rb").read() for k in (b"ISO6709", b"com.apple", b"\xa9xyz"))]
print(len(done), "photographs and clips;", "metadata left in:", bad or "none")
