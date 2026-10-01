import json, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
d = json.load(open("routes_out.json"))
roads = json.load(open("roads.json"))
fig, ax = plt.subplots(1, 1, figsize=(12, 11))
for e in roads["elements"]:
    t = e.get("tags", {})
    if t.get("highway") in ("trunk", "primary", "secondary", "tertiary", "motorway"):
        xs = [p["lon"] for p in e["geometry"]]; ys = [p["lat"] for p in e["geometry"]]
        ax.plot(xs, ys, color="#bbb" if t["highway"] != "motorway" else "#f99", lw=0.6)
cols = ["#d62728", "#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b", "#e377c2"]
for k, (pair, rs) in enumerate(d["pairs"].items()):
    for i, r in enumerate(rs):
        xs = [c[0] for c in r["coords"]]; ys = [c[1] for c in r["coords"]]
        ax.plot(xs, ys, color=cols[i % 7], lw=2.2 - 0.25 * i, alpha=0.8, label=f"{pair} #{i} {r['len_m']/1000:.1f} km")
        ax.text(xs[len(xs)//2], ys[len(ys)//2], f"{pair[:2]}{i}", fontsize=8)
for k, v in d["snap"].items(): ax.plot(*v, "k*", ms=12); ax.text(v[0], v[1], k)
ax.legend(fontsize=7, loc="lower right"); ax.set_aspect(1 / 0.832)
plt.savefig("routes_map.png", dpi=80, bbox_inches="tight")
fig, axs = plt.subplots(3, 1, figsize=(12, 10))
for ax, (pair, rs) in zip(axs, d["pairs"].items()):
    for i, r in enumerate(rs):
        ax.plot([c / 1000 for c in r["cum"]], r["h"], color=cols[i % 7], lw=1, label=f"#{i} up {r['up_m']:.0f}")
    ax.set_title(pair); ax.legend(fontsize=7)
plt.tight_layout(); plt.savefig("routes_prof.png", dpi=70)
