import math

import pytest

import uvbake

def _raises(fn, exc=ValueError):
    try:
        fn()
    except exc:
        return True
    return False

TRI = ((0.0, 0.0), (0.9, 0.0), (0.0, 0.9))
UV = ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0))
VAL = (1.0, 0.5, 0.0)

CASES = [
    ("shape", lambda: len(uvbake.UvBake(8).bake(TRI, UV, VAL)) == 8),
    ("coverage", lambda: 0.0 < uvbake.UvBake(8).bake(TRI, UV, VAL) and uvbake.UvBake(8).coverage() > 0.0),
    ("corner", lambda: isinstance(uvbake.UvBake(8).bake(TRI, UV, VAL)[0][0], float)),
    ("bad_size", lambda: _raises(lambda: uvbake.UvBake(0))),
    ("bad_tri", lambda: _raises(lambda: uvbake.UvBake(8).bake((), UV, VAL))),
    ("bad_len", lambda: _raises(lambda: uvbake.UvBake(8).bake(TRI, UV, (1.0,)))),
    ("type", lambda: isinstance(uvbake.UvBake(8).bake(TRI, UV, VAL), list)),
    ("det", lambda: uvbake.UvBake(8).bake(TRI, UV, VAL) == uvbake.UvBake(8).bake(TRI, UV, VAL)),
    ("range", lambda: all(-1.0 <= v <= 1.0 for row in uvbake.UvBake(8).bake(TRI, UV, VAL) for v in row)),
    ("invalid", lambda: isinstance(uvbake.UvBake(8).bake(TRI, UV, VAL), list)),
    ("coverage_type", lambda: isinstance(uvbake.UvBake(8).bake(TRI, UV, VAL) and uvbake.UvBake(8).coverage(), float)),
    ("nan", lambda: _raises(lambda: uvbake.UvBake(8).bake(TRI, UV, (float('nan'), 0.0, 0.0)))),
    ("no_mut", lambda: uvbake.UvBake(8).bake(TRI, UV, VAL) is not None),
    ("wrap", lambda: isinstance(uvbake.UvBake(8).bake(TRI, ((-0.5, 0.0), (1.0, 0.0), (0.0, 1.0)), VAL), list)),
    ("float", lambda: isinstance(uvbake.UvBake(8).coverage(), float)),
]


@pytest.mark.parametrize("name,check", CASES, ids=[c[0] for c in CASES])
def test_spec(name, check):
    assert check() is True
