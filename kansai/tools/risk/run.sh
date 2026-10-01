#!/usr/bin/env bash
# The risk analysis behind the page's evacuation, exposure, plan and network figures. Run in an empty work directory after the
# main build (KANSAI_GEO), tools/tsunami2026 (TSUNAMI_WORK) and tools/bike/fetch_tiles.py (OSM_ROADS); see cfg.py.
#   bash /path/to/kansai/tools/risk/run.sh /path/to/kansai
set -euo pipefail
T=$(cd "$(dirname "$0")" && pwd); KANSAI=${1:?kansai directory}
python3 $T/fetch.py        # census, evacuation sites, KSJ hospitals, IPSS, OSM land use → downloads/
python3 $T/census.py       # 2020 census: small areas and 250 m cells, suppressed figures merged as e-Stat does
python3 $T/fetch_bld.py    # GSI building outlines and road centre lines over every inhabited cell → obv16/
python3 $T/citylist.py     # Shingū's 津波一時避難施設・場所 (2017) → shingu_tsunami_ichiji_2017.csv
python3 $T/pop_bld.py      # residents per building (dasymetric, fitted to cells and small areas) → bld.npz
python3 $T/sites.py        # designated tsunami sites with floor heights and 2026 depths → sites.json
python3 $T/walknet.py      # walking network (GSI roads + OSM ways, ground heights) → walknet.npz
python3 $T/evac.py         # evacuation margins per building and scenario → evac.npz, evac_summary.json
python3 $T/expo.py         # residents by hazard tier, both banks → expo.npz, expo_summary.json
python3 $T/cve.py          # the plan's zones against the tiers → cve_summary.json
python3 $T/crit.py         # road network under hazard scenarios → crit_summary.json
python3 $T/shrink.py       # the margins with the 2050 population → shrink_summary.json
python3 $T/export.py "$KANSAI"   # → $KANSAI/data/risk.js
