#!/usr/bin/env bash
# Digitise the 2026 tsunami maps of Shingū and Kihō and read arrival times from Wakayama's animations.
# Run in an empty work directory: bash /path/to/kansai/tools/tsunami2026/run.sh <dir with N03-20260101_30/24.geojson and prefs.geojson>
set -euo pipefail
T=$(cd "$(dirname "$0")" && pwd); K=${1:?N03/prefs directory}
export PREFS=$K/prefs.geojson
bash $T/fetch.sh
python3 $T/fetch_obv.py 135.94 33.655 136.035 33.75          # GSI building outlines for the fit
python3 $T/fetch_photo.py                                     # GSI photographs, to place the animation's panel
# rasters (strips reassembled, not resampled)
python3 $T/raster.py wk_r8_kyodaishinngu.pdf 1 4800 r8_k1.png jpeg;  python3 $T/raster.py wk_r8_kyodaishinngu.pdf 2 4800 r8_k2.png jpeg
python3 $T/raster.py wk_r8_3rendoushinngu.pdf 1 4800 r8_s1.png jpeg; python3 $T/raster.py wk_r8_3rendoushinngu.pdf 2 4800 r8_s2.png jpeg
python3 $T/raster.py mie_001249288.pdf 1 3000 mie22.png
# Wakayama: sheet 2 from four facility symbols, refined; sheet 1 at the same scale from two symbols, refined;
# the frequent-class sheets share the maximum-class sheets' base map (sheet 2 reuses sheet 2's fit)
python3 $T/init.py k2 aff_init_k2.npy && python3 $T/register.py r8_k2.png aff_init_k2.npy aff_k2_full.npy && python3 $T/poly.py r8_k2.png aff_k2_full.npy poly_k2_full.npz
python3 $T/init.py k1 aff_init_k1.npy
for sh in k1 s1; do python3 $T/register.py r8_$sh.png aff_init_k1.npy aff_${sh}_full.npy && python3 $T/poly.py r8_$sh.png aff_${sh}_full.npy poly_${sh}_full.npz; done
for sh in k1 k2 s1 s2; do p=$sh; [ $sh = s2 ] && p=k2; python3 $T/classify.py r8_$sh.png poly_${p}_full.npz aff_${p}_full.npy cls_$sh.npz; done
python3 $T/merge.py $K/N03-20260101_30.geojson
# Mie sheet 22: four annotated points, then the fit on buildings inside Mie only (the sheet draws only Mie's land)
python3 $T/init.py mie22 aff_init_mie22.npy
CLIP_PREF=三重県 python3 $T/register.py mie22.png aff_init_mie22.npy aff_mie22.npy
python3 $T/affpoly.py aff_mie22.npy poly_mie22.npz
LEGEND=mie python3 $T/classify.py mie22.png poly_mie22.npz aff_mie22.npy cls_mie22.npz
# polygons for the page build (07_build.py reads them from ./tsunami2026 of its work directory)
mkdir -p tsunami2026
python3 $T/vectorize.py r8_k_grid.npz $K/N03-20260101_30.geojson 新宮市 wakayama_R8_max "和歌山県 地震動予測及び津波浸水想定（令和8年公表）南海トラフ巨大地震 新宮市 2/2・1/2" tsunami2026/shingu_r8_max.geojson
python3 $T/vectorize.py r8_s_grid.npz $K/N03-20260101_30.geojson 新宮市 wakayama_R8_frequent "和歌山県 同 東海・東南海・南海3連動地震 新宮市" tsunami2026/shingu_r8_freq.geojson
python3 $T/vectorize.py cls_mie22.npz $K/N03-20260101_24.geojson 紀宝町 mie_2026_L2 "三重県 津波浸水想定（令和8年3月30日公表）図面番号22" tsunami2026/kiho_mie2026_max.geojson
# arrival: first wetting in the 2D animations; the panel placed on the photographs, then on the digitised map
python3 $T/vid_decode.py wk_r8_16_shinguu_nk_2D_k.mp4 kyodai.npz
python3 $T/vid_decode.py wk_r8_16_shinngu_3ren_2D_k.mp4 sanren.npz
python3 $T/vid_register.py kyodai.npz aff_kyodai.npy
python3 $T/vid_shift.py kyodai.npz aff_kyodai.npy r8_k_grid.npz aff_kyodai_adj.npy
