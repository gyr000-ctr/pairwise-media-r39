import math

import pytest

import uvsphere

def _raises(fn, exc=ValueError):
    try:
        fn()
    except exc:
        return True
    return False

D = (0.0, 0.0, 1.0)

CASES = [
    ("uv_pair", lambda: len(uvsphere.UvSphere().to_uv(D)) == 2),
    ("uv_range", lambda: all(0.0 <= c <= 1.0 for c in uvsphere.UvSphere().to_uv((0.6, 0.0, 0.8)))),
    ("roundtrip", lambda: abs(uvsphere.UvSphere().to_dir(uvsphere.UvSphere().to_uv((0.3, 0.5, 0.8)))[0] - 0.3) < 1e-9),
    ("unit_out", lambda: abs(math.sqrt(sum(c * c for c in uvsphere.UvSphere().to_dir((0.2, 0.3)))) - 1.0) < 1e-9),
    ("zero_dir", lambda: _raises(lambda: uvsphere.UvSphere().to_uv((0.0, 0.0, 0.0)))),
    ("bad_uv", lambda: _raises(lambda: uvsphere.UvSphere().to_dir((1.5, 0.5)))),
    ("pole", lambda: isinstance(uvsphere.UvSphere().to_uv((0.0, 1.0, 0.0)), tuple)),
    ("seam", lambda: abs(uvsphere.UvSphere().to_uv((1.0, 0.0, 0.001))[0] - uvsphere.UvSphere().to_uv((1.0, 0.0, -0.001))[0]) < 1e-2),
    ("type", lambda: isinstance(uvsphere.UvSphere().to_uv(D), tuple)),
    ("det", lambda: uvsphere.UvSphere().to_uv(D) == uvsphere.UvSphere().to_uv(D)),
    ("nan", lambda: _raises(lambda: uvsphere.UvSphere().to_uv((float('nan'), 0.0, 1.0)))),
    ("dir_type", lambda: isinstance(uvsphere.UvSphere().to_dir((0.5, 0.5)), tuple)),
    ("float", lambda: isinstance(uvsphere.UvSphere().to_uv(D)[0], float)),
    ("distortion", lambda: isinstance(uvsphere.UvSphere().area_distortion(), float)),
    ("no_mut", lambda: uvsphere.UvSphere().to_uv((0.1, 0.2, 0.97)) is not None),
]


@pytest.mark.parametrize("name,check", CASES, ids=[c[0] for c in CASES])
def test_spec(name, check):
    assert check() is True
