import shapely, numpy as np
from pyproj import Transformer
AEA = "+proj=aea +lat_1=33.6 +lat_2=34.25 +lat_0=33.9 +lon_0=135.83 +ellps=GRS80 +units=m +no_defs"
_fwd = Transformer.from_crs("EPSG:4326", AEA, always_xy=True)
_inv = Transformer.from_crs(AEA, "EPSG:4326", always_xy=True)
def to_m(geom):
    return shapely.transform(geom, lambda c: np.column_stack(_fwd.transform(c[:, 0], c[:, 1])))
def to_ll(geom):
    return shapely.transform(geom, lambda c: np.column_stack(_inv.transform(c[:, 0], c[:, 1])))
def area_km2(geom):
    return shapely.area(to_m(geom)) / 1e6
def round_coords(geom, nd=5):
    return shapely.set_precision(geom, 10**-nd) if False else shapely.transform(geom, lambda c: np.round(c, nd))
