"""Where the risk analysis finds its inputs. Outputs are written to the current directory (the analysis work directory).
  KANSAI_GEO     the main build's work directory (ksj/ with N03, A31b-25, A33, A55; gsi_dem5.npy/.json)   default ../geo
  TSUNAMI_WORK   tools/tsunami2026's work directory (r8_*_grid.npz, cls_mie22.npz, kyodai/sanren.npz,
                 aff_kyodai_adj.npy)                                                                     default ../tsunami2026
  RISK_DOWNLOADS fetch.py's downloads (census, evacuation sites, KSJ facilities, IPSS, OSM land use)   default ./downloads
  OSM_ROADS      OpenStreetMap highways of the region (tools/bike/fetch_tiles.py → roads.json)          default ../bike/roads.json"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
CWD = os.getcwd()
GEO = os.environ.get("KANSAI_GEO", os.path.join(CWD, "..", "geo"))
T26 = os.environ.get("TSUNAMI_WORK", os.path.join(CWD, "..", "tsunami2026"))
DL = os.environ.get("RISK_DOWNLOADS", os.path.join(CWD, "downloads"))
ROADS = os.environ.get("OSM_ROADS", os.path.join(CWD, "..", "bike", "roads.json"))
BIKE = os.path.join(HERE, "..", "bike")
def geo(*p): return os.path.join(GEO, *p)
def t26(*p): return os.path.join(T26, *p)
def dl(*p): return os.path.join(DL, *p)
