"""Reassemble the map raster of a PDF page from its embedded image strips (pymupdf): every strip at least <min_w> px wide
(Wakayama's colour JPEG strips are 4,811 px; Mie's 3,691 px) is pasted at the position its placement rectangle gives,
at the strips' own resolution. Nothing is resampled.
usage: raster.py <pdf> <page (1-based)> <min_w> <out.png> [jpeg]   (jpeg: colour JPEG strips only; Wakayama's sheets also
carry 1-channel overlay images of the same width)"""
import io, sys, pymupdf
from PIL import Image
pdf, page, min_w, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
jpeg_only = len(sys.argv) > 5 and sys.argv[5] == "jpeg"
d = pymupdf.open(pdf); p = d[page - 1]
parts = []
for im in p.get_images(full=True):
    xref, w, h = im[0], im[2], im[3]
    if w < min_w: continue
    info = d.extract_image(xref)
    if jpeg_only and info["ext"] != "jpeg": continue
    r = p.get_image_rects(xref)[0]; parts.append((r.y0, r, info, w, h))
parts.sort(key=lambda t: t[0])
x0 = min(t[1].x0 for t in parts); y0 = min(t[1].y0 for t in parts); x1 = max(t[1].x1 for t in parts); y1 = max(t[1].y1 for t in parts)
W = max(t[3] for t in parts); ppt = W / (x1 - x0); H = int(round((y1 - y0) * ppt))
cv = Image.new("RGB", (W, H), "white")
for y, r, info, w, h in parts:
    cv.paste(Image.open(io.BytesIO(info["image"])).convert("RGB"), (int(round((r.x0 - x0) * ppt)), int(round((r.y0 - y0) * ppt))))
cv.save(out)
print(out, cv.size, "strips", len(parts), "px/pt", round(ppt, 3), "pt box", (round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)))
