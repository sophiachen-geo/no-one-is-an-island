"""Shingū City's 津波一時避難施設・場所 (https://www.city.shingu.lg.jp/info/762, updated 2017-02-03) → shingu_tsunami_ichiji_2017.csv:
district, facility, address, designated place, height above sea level of that place, as printed (NFKC-normalised)."""
import csv, re, sys, unicodedata
from html.parser import HTMLParser
import cfg
class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows = []; self.district = None; self.in_h2 = False; self.cell = None; self.row = None
    def handle_starttag(self, t, a):
        if t == "h2": self.in_h2 = True; self.buf = ""
        elif t in ("td", "th"): self.cell = ""
        elif t == "tr": self.row = []
    def handle_endtag(self, t):
        if t == "h2": self.in_h2 = False; self.district = self.buf.strip()
        elif t in ("td", "th") and self.cell is not None and self.row is not None: self.row.append(self.cell.strip()); self.cell = None
        elif t == "tr" and self.row is not None:
            if self.district and len(self.row) == 4 and self.row[0] != "施設名": self.rows.append([self.district] + self.row)
            self.row = None
    def handle_data(self, d):
        if self.in_h2: self.buf += d
        if self.cell is not None: self.cell += d
p = P(); p.feed(open(cfg.dl("sites", "shingu_info_762.html"), encoding="utf-8", errors="replace").read())
norm = lambda s: re.sub(r"\s+", "", unicodedata.normalize("NFKC", s))
with open("shingu_tsunami_ichiji_2017.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["地区", "施設名", "所在地", "指定場所", "海抜"])
    for r in p.rows: w.writerow([norm(x) for x in r])
print(len(p.rows), "sites", file=sys.stderr)
