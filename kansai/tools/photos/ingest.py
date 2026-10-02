"""Read the user's originals (JPEG/HEIC/PNG; MOV/MP4 clips; GPX/FIT tracks) → manifest.json + EXIF-free web copies.
EXIF read: DateTimeOriginal (+OffsetTimeOriginal), GPS lat/lon/alt/direction/positioning error, camera.
Clips: the QuickTime keys the phone writes (creationdate, location.ISO6709, location.accuracy), read with ffmpeg; a
clip has no compass heading, and its position is stored to as many decimals of a degree as the phone wrote ("pos_dp":
4 on an iPhone, a cell of about 11 × 9 m here). Its web copy is a still at 0.5 s.
Web copies: orientation applied, long side <= 1600 px, JPEG q82, NO metadata (GPS stays out of the
published file; the page carries only the position we choose to show)."""
import os, re, sys, json, shutil, datetime, subprocess
from PIL import Image, ExifTags, ImageOps
import pillow_heif
pillow_heif.register_heif_opener()
SRC = sys.argv[1] if len(sys.argv) > 1 else "orig"
OUT = sys.argv[2] if len(sys.argv) > 2 else "web"
os.makedirs(OUT, exist_ok=True)
GPS = {v: k for k, v in ExifTags.GPSTAGS.items()}
def rat(x):
    try: return float(x)
    except Exception:
        try: return x[0] / x[1]
        except Exception: return None
def dms(v, ref):
    if not v: return None
    d = rat(v[0]) + rat(v[1]) / 60 + rat(v[2]) / 3600
    return -d if ref in ("S", "W") else d
def read(path):
    im = Image.open(path)
    ex = im.getexif()
    base = {ExifTags.TAGS.get(k, k): v for k, v in ex.items()}
    sub = {ExifTags.TAGS.get(k, k): v for k, v in ex.get_ifd(0x8769).items()} if ex else {}
    gps = {ExifTags.GPSTAGS.get(k, k): v for k, v in ex.get_ifd(0x8825).items()} if ex else {}
    t = sub.get("DateTimeOriginal") or base.get("DateTime")
    off = sub.get("OffsetTimeOriginal") or sub.get("OffsetTime")
    lat = dms(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"))
    lon = dms(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"))
    alt = rat(gps.get("GPSAltitude")) if gps.get("GPSAltitude") is not None else None
    if alt is not None and gps.get("GPSAltitudeRef") in (1, b"\x01"): alt = -alt
    return im, {"time": t, "offset": off, "lat": lat, "lon": lon, "alt": alt,
                "dir": rat(gps.get("GPSImgDirection")) if gps.get("GPSImgDirection") is not None else None,
                "dir_ref": gps.get("GPSImgDirectionRef"), "hpe_m": rat(gps.get("GPSHPositioningError")) if gps.get("GPSHPositioningError") is not None else None,
                "gps_time": str(gps.get("GPSDateStamp")) + " " + ":".join(str(int(rat(x))) for x in gps["GPSTimeStamp"]) if gps.get("GPSTimeStamp") and gps.get("GPSDateStamp") else None,
                "camera": " ".join(str(x) for x in (base.get("Make"), base.get("Model")) if x), "w": im.width, "h": im.height}
def ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe: return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()
def read_clip(path):
    """QuickTime metadata of a phone clip, from ffmpeg's report (no ffprobe needed)."""
    r = subprocess.run([ffmpeg(), "-hide_banner", "-i", path], capture_output=True, text=True).stderr
    key = lambda k: (re.search(rf"{re.escape(k)}\s*:\s*([^\n]*\S)", r) or [None, None])[1]   # the whole value: "iPhone 16"
    t = key("com.apple.quicktime.creationdate")                # 2025-09-28T12:04:06+0900
    loc = re.match(r"([+-]\d+\.\d+)([+-]\d+\.\d+)([+-]\d+\.\d+)?", key("com.apple.quicktime.location.ISO6709") or "")
    dur = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r)
    wh = re.search(r"Video: .*?, (\d{3,5})x(\d{3,5})", r)
    rot = re.search(r"displaymatrix: rotation of (-?\d+(?:\.\d+)?) degrees", r)
    w, h = (int(wh.group(1)), int(wh.group(2))) if wh else (None, None)
    if rot and abs(abs(float(rot.group(1))) - 90) < 1: w, h = h, w
    acc = key("com.apple.quicktime.location.accuracy.horizontal")
    return {"time": t[:19].replace("-", ":").replace("T", " ") if t else None, "offset": (t[19:22] + ":" + t[22:24]) if t and len(t) >= 24 else None,
            "lat": float(loc.group(1)) if loc else None, "lon": float(loc.group(2)) if loc else None,
            "alt": float(loc.group(3)) if loc and loc.group(3) else None, "dir": None, "dir_ref": None,
            "pos_dp": min(len(loc.group(1).split(".")[1]), len(loc.group(2).split(".")[1])) if loc else None,
            "hpe_m": float(acc) if acc else None, "gps_time": None,
            "camera": " ".join(x for x in (key("com.apple.quicktime.make"), key("com.apple.quicktime.model")) if x),
            "w": w, "h": h, "video": True, "duration_s": round(int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3)), 2) if dur else None}
man = []
for fn in sorted(os.listdir(SRC)):
    p = os.path.join(SRC, fn); ext = fn.lower().rsplit(".", 1)[-1]
    if ext in ("jpg", "jpeg", "heic", "heif", "png", "webp", "dng"):
        try:
            im, m = read(p)
        except Exception as e:
            print("unreadable", fn, e); continue
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((1600, 1600), Image.LANCZOS)
        stem = os.path.splitext(fn)[0]
        out = os.path.join(OUT, stem + ".jpg")
        im.save(out, "JPEG", quality=82, optimize=True, progressive=True)   # no exif= → no metadata written
        m.update({"file": fn, "web": out, "web_w": im.width, "web_h": im.height})
        man.append(m)
    elif ext in ("mov", "mp4", "m4v"):
        m = read_clip(p); stem = os.path.splitext(fn)[0]; out = os.path.join(OUT, stem + ".jpg")
        subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-ss", "0.5", "-i", p, "-frames:v", "1",
                        "-vf", "scale='if(gt(iw,ih),1600,-2)':'if(gt(iw,ih),-2,1600)'", "-map_metadata", "-1", "-q:v", "3", out], check=True)
        im = Image.open(out); m.update({"file": fn, "web": out, "web_w": im.width, "web_h": im.height})
        man.append(m)
    elif ext in ("gpx", "fit", "kml", "tcx", "geojson"):
        man.append({"file": fn, "track": True})
json.dump(man, open("manifest.json", "w"), ensure_ascii=False, indent=1, default=str)
print(len(man), "items;", sum(1 for m in man if m.get("lat")), "with GPS")
