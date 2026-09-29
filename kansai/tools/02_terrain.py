"""Mosaic the four SRTM 1-arc-second tiles (33-35N, 135-137E) and derive a 3-arc-second grid for hydrology.

Writes dem1.npy (1", origin 35N 135E), dem3.npy and grid3.json."""
import numpy as np, json
T = {}
for la in (33, 34):
    for lo in (135, 136):
        a = np.fromfile(f"N{la}E{lo}.hgt", dtype=">i2").reshape(3601, 3601)
        T[(la, lo)] = a
# mosaic 33..35N, 135..137E at 1 arc-sec: rows from north (35N) to south (33N)
full = np.zeros((7201, 7201), dtype=np.int16)
full[0:3601, 0:3601] = T[(34, 135)]
full[0:3601, 3600:7201] = T[(34, 136)]
full[3600:7201, 0:3601] = T[(33, 135)]
full[3600:7201, 3600:7201] = T[(33, 136)]
full[full < -1000] = 0
np.save("dem1.npy", full)            # 1 arc-sec, origin 35N 135E, step 1/3600
# 3 arc-sec for hydrology
f = 3
d3 = full[: (7201 // f) * f, : (7201 // f) * f].reshape(7201 // f, f, 7201 // f, f).mean(axis=(1, 3)).astype(np.float32)
H, W = d3.shape
print("grid", d3.shape)
res = f / 3600.0
np.save("dem3.npy", d3)
json.dump({"H": H, "W": W, "res": res, "lat0": 35.0, "lon0": 135.0}, open("grid3.json", "w"))
print("dem1", full.shape, "dem3", d3.shape)
