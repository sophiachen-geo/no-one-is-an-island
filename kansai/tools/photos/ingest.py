"""Read the user's originals (JPEG/HEIC/PNG; GPX/FIT tracks) → manifest.json + EXIF-free web copies.
EXIF read: DateTimeOriginal (+OffsetTimeOriginal), GPS lat/lon/alt/direction/positioning error, camera.
Web copies: orientation applied, long side <= 1600 px, JPEG q82, NO metadata (GPS stays out of the
published file; the page carries only the position we choose to show)."""
import os, sys, json, datetime
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
    elif ext in ("gpx", "fit", "kml", "tcx", "geojson"):
        man.append({"file": fn, "track": True})
json.dump(man, open("manifest.json", "w"), ensure_ascii=False, indent=1, default=str)
print(len(man), "items;", sum(1 for m in man if m.get("lat")), "with GPS")
