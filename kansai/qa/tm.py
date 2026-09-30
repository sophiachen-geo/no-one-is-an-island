"""Pure-Python Gauss–Krüger projection for JGD2011 Plane Rectangular CS zone VI (EPSG:6674).

GSI's published Krüger-series formulas (n-series to 5th order). Accurate to well under 1 mm within
the zone, so the QA can re-project reference coordinates without pyproj/GDAL in CI.
"""
from math import atan, atanh, cos, cosh, radians, sin, sinh, sqrt

A_GRS80 = 6378137.0
F_GRS80 = 298.257222101
M0 = 0.9999
LAT0, LON0 = 36.0, 136.0          # origin of zone VI

_n = 1.0 / (2 * F_GRS80 - 1)
_A = [1 + _n**2 / 4 + _n**4 / 64,
      -3 / 2 * (_n - _n**3 / 8 - _n**5 / 64),
      15 / 16 * (_n**2 - _n**4 / 4),
      -35 / 48 * (_n**3 - 5 / 16 * _n**5),
      315 / 512 * _n**4,
      -693 / 1280 * _n**5]
_alpha = [0.0,
          _n / 2 - 2 / 3 * _n**2 + 5 / 16 * _n**3 + 41 / 180 * _n**4 - 127 / 288 * _n**5,
          13 / 48 * _n**2 - 3 / 5 * _n**3 + 557 / 1440 * _n**4 + 281 / 630 * _n**5,
          61 / 240 * _n**3 - 103 / 140 * _n**4 + 15061 / 26880 * _n**5,
          49561 / 161280 * _n**4 - 179 / 168 * _n**5,
          34729 / 80640 * _n**5]
_Abar = M0 * A_GRS80 / (1 + _n) * _A[0]
_phi0 = radians(LAT0)
_S0 = M0 * A_GRS80 / (1 + _n) * (_A[0] * _phi0 + sum(_A[j] * sin(2 * j * _phi0) for j in range(1, 6)))
_c = 2 * sqrt(_n) / (1 + _n)


def forward(lon, lat):
    """(lon, lat) in degrees (JGD2011 ≈ WGS84) -> (easting, northing) in metres, EPSG:6674 axis order x=E, y=N."""
    phi, dlam = radians(lat), radians(lon - LON0)
    t = sinh(atanh(sin(phi)) - _c * atanh(_c * sin(phi)))
    tb = sqrt(1 + t * t)
    xi, eta = atan(t / cos(dlam)), atanh(sin(dlam) / tb)
    north = _Abar * (xi + sum(_alpha[j] * sin(2 * j * xi) * cosh(2 * j * eta) for j in range(1, 6))) - _S0
    east = _Abar * (eta + sum(_alpha[j] * cos(2 * j * xi) * sinh(2 * j * eta) for j in range(1, 6)))
    return east, north


def to_svg(lon, lat, origin):
    """Page coordinates: 1 SVG unit = 100 m, x east from X0, y south from Y1 (origin = [X0, Y1])."""
    e, n = forward(lon, lat)
    return (e - origin[0]) / 100.0, (origin[1] - n) / 100.0
