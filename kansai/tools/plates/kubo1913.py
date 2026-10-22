"""Plates of the Kubo photo studio's 『熊野百景写真帖』 (1913; NDL info:ndljp/pid/906106, public domain) for the Kansai page.

    python3 kansai/tools/plates/kubo1913.py <work dir> <kansai/img dir>

Fetches the album spreads from NDL's IIIF service once (into <work dir>) and writes greyscale JPEGs (q80):
  kubo1913_page56.jpg … kubo1913_page64.jpg  the album pages holding plates 56–65, printed titles included (contact sheet)
  kubo1913_plate56.jpg                      plate 56 新宮町全景 alone
  kubo1913_plate62.jpg                      plate 62 新宮貯木塲 alone, cut inside its border below the corner that plate 63
                                            covers on the page (a band of sky and the chimney's top are left out)
  kubo1913_plate82.jpg                      plate 82 鵜殿貯木塲, the oval alone, the page outside it white
Positions are pixels of the full IIIF frames (3756 × 1494), measured on the printed border lines; the oval of plate 82 is a
least-squares ellipse fitted to its border where nothing else touches it (median residual under 1 px)."""
import os, sys, json, urllib.request
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

WORK, OUT = sys.argv[1], sys.argv[2]
os.makedirs(WORK, exist_ok=True)
IIIF = "https://dl.ndl.go.jp/api/iiif/906106/R{:07d}/full/full/0/default.jpg"


def frame(n):
    p = os.path.join(WORK, f"f{n}.jpg")
    if not os.path.exists(p):
        urllib.request.urlretrieve(IIIF.format(n), p)
    im = Image.open(p).convert("L")
    assert im.size == (3756, 1494), (n, im.size)
    return im


def save(im, name, long_side):
    im = im.copy(); im.thumbnail((long_side, long_side), Image.LANCZOS)
    im.save(os.path.join(OUT, name), quality=80, optimize=True, progressive=True)
    return {"file": "img/" + name, "w": im.width, "h": im.height}


# album pages, in the album's order (a right-bound book: right page, then left), with the plates each holds
PAGES = [  # (frame, side, plates)
    (28, "L", "56"), (29, "R", "57"), (29, "L", "58–59"), (30, "R", "60–61"), (30, "L", "62–63"), (31, "R", "64"), (31, "L", "65")]


def page_box(im, side):
    """The printed content of one page of a spread, padded: its plates (large dark components) and the printed titles near
    them (small components within 260 px), ignoring the binding strip, the paper's edges and the scan's border."""
    a = np.asarray(im, float); h, w = a.shape
    mid = a[:, w // 2 - 250: w // 2 + 250].mean(0); gut = w // 2 - 250 + int(np.argmin(mid))
    x0, x1 = (100, gut - 110) if side == "L" else (gut + 110, w - 100)
    sub = ndi.uniform_filter(a[100:h - 100, x0:x1], 5) < 150
    lab, n = ndi.label(sub); objs = ndi.find_objects(lab); area = ndi.sum(sub, lab, range(1, n + 1))
    boxes = [(o[1].start, o[0].start, o[1].stop, o[0].stop) for o in objs]
    big = [b for b, ar in zip(boxes, area) if ar > 20000 and b[2] - b[0] > 150 and b[3] - b[1] > 150]   # plates, not edge lines
    X0, Y0 = min(b[0] for b in big), min(b[1] for b in big); X1, Y1 = max(b[2] for b in big), max(b[3] for b in big)
    P0, Q0, P1, Q1 = X0, Y0, X1, Y1         # the plates alone: titles are looked for relative to them, not to each other
    for b, ar in zip(boxes, area):          # printed titles beside or below the plates
        dims = (b[2] - b[0], b[3] - b[1])     # printed characters: blobs of 12–120 px; edge lines and the binding are not
        if 30 < ar <= 20000 and min(dims) >= 12 and max(dims) <= 120 and b[0] > P0 - 260 and b[2] < P1 + 260 and b[1] > Q0 - 10 and b[3] < Q1 + 120:
            X0, Y0, X1, Y1 = min(X0, b[0]), min(Y0, b[1]), max(X1, b[2]), max(Y1, b[3])
    pad = 45
    return tuple(int(v) for v in (x0 + X0 - pad, 100 + Y0 - pad, x0 + X1 + pad, 100 + Y1 + pad))


out = []
for f, side, plates in PAGES:
    im = frame(f); box = page_box(im, side)
    r = save(im.crop(box), f"kubo1913_page{plates.split('–')[0]}.jpg", 900)
    r.update(frame=f, side=side, plates=plates, box=box); out.append(r)

# plate 56: the rectangle (border lines x 438–1692, y 543–989)
r = save(frame(28).crop((436, 541, 1695, 992)), "kubo1913_plate56.jpg", 1000); r.update(frame=28, box=(436, 541, 1695, 992)); out.append(r)

# plate 62: rectangle x 602–1717, y 730–1182; plate 63 lies over its upper-left corner up to x 1254, y 786
box = (606, 790, 1714, 1179)
r = save(frame(30).crop(box), "kubo1913_plate62.jpg", 1000); r.update(frame=30, box=box); out.append(r)

# plate 82: tilted ellipse centre (1396.3, 554.2), semi-axes 342.9 × 227.1, −4.27°; the border line kept (+3 px)
E = dict(cx=1396.3, cy=554.2, A=342.9 + 3, B=227.1 + 3, th=np.radians(-4.27))
im = frame(37); box = (int(E["cx"] - 360), int(E["cy"] - 260), int(E["cx"] + 360), int(E["cy"] + 260))
c = np.array(im.crop(box)).astype(np.uint8)
yy, xx = np.mgrid[box[1]:box[3], box[0]:box[2]]
cs, sn = np.cos(E["th"]), np.sin(E["th"])
X = (xx - E["cx"]) * cs + (yy - E["cy"]) * sn; Y = -(xx - E["cx"]) * sn + (yy - E["cy"]) * cs
c[(X / E["A"]) ** 2 + (Y / E["B"]) ** 2 > 1] = 255
r = save(Image.fromarray(c), "kubo1913_plate82.jpg", 1000); r.update(frame=37, box=box, ellipse={k: float(np.degrees(v) if k == "th" else v) for k, v in E.items()}); out.append(r)

json.dump(out, open(os.path.join(WORK, "kubo1913.json"), "w"), ensure_ascii=False, indent=1)
for r in out:
    print(r["file"], r["w"], "×", r["h"], "frame", r["frame"], r.get("plates", ""), r["box"])
