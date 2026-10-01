#!/usr/bin/env bash
# The 2026 tsunami inundation maps and animations this folder digitises (all fetched 2026-10-01).
#   Wakayama 令和8年「地震動予測及び津波浸水想定」: maps of Shingū, maximum class and frequent class (PDF, 2 sheets each);
#   2D inundation animations of Shingū, both classes (MP4). Terms: 和歌山県ホームページ公開情報利用規約 (CC BY 4.0-compatible).
#   Mie 2026 津波浸水想定 (Tsunami Act Art. 8): sheet 22 (御浜町・紀宝町), PDF. Terms: CC BY 4.0 (三重県オープンデータ利用規約).
# Wakayama's server answers 403 to non-browser user agents.
set -euo pipefail
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
get() { [ -s "$2" ] || curl -sS -f -A "$UA" -o "$2" "$1"; }
W=https://www.pref.wakayama.lg.jp/prefg/011400
get $W/d00221942_d/fil/kyodaishinngu.pdf          wk_r8_kyodaishinngu.pdf     # maximum class (南海トラフ巨大地震)
get $W/d00221941_d/fil/3rendoushinngu.pdf         wk_r8_3rendoushinngu.pdf    # frequent class (東海・東南海・南海3連動)
get $W/bousai/shinsui/trough/d00222025_d/fil/16_shinguu_nk_2D_k.mp4     wk_r8_16_shinguu_nk_2D_k.mp4
get $W/bousai/shinsui/trough/d00222029_d/fil/16_shinngu_3ren_2D_k.mp4   wk_r8_16_shinngu_3ren_2D_k.mp4
get https://www.pref.mie.lg.jp/common/content/001249288.pdf    mie_001249288.pdf  # 図面番号22
sha256sum wk_r8_*.pdf wk_r8_*.mp4 mie_001249288.pdf
