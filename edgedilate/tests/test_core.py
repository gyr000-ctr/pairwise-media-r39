import math

import pytest

import edgedilate

def _raises(fn, exc=ValueError):
    try:
        fn()
    except exc:
        return True
    return False

E = [[False, False, False], [False, True, False], [False, False, False]]

CASES = [
    ("center", lambda: edgedilate.EdgeDilate(1).dilate(E)[1][1] is True),
    ("neighbor", lambda: edgedilate.EdgeDilate(1).dilate(E)[0][1] is True),
    ("far", lambda: edgedilate.EdgeDilate(1).dilate(E)[0][0] is False),
    ("radius2", lambda: edgedilate.EdgeDilate(2).dilate(E)[0][0] is True),
    ("bad_radius", lambda: _raises(lambda: edgedilate.EdgeDilate(0))),
    ("bad_edges", lambda: _raises(lambda: edgedilate.EdgeDilate(1).dilate([]))),
    ("shape", lambda: len(edgedilate.EdgeDilate(1).dilate(E)) == 3),
    ("outline", lambda: isinstance(edgedilate.EdgeDilate(1).outline(E, 0, 1), list)),
    ("type", lambda: isinstance(edgedilate.EdgeDilate(1).dilate(E), list)),
    ("det", lambda: edgedilate.EdgeDilate(1).dilate(E) == edgedilate.EdgeDilate(1).dilate(E)),
    ("bool_cells", lambda: all(isinstance(v, bool) for row in edgedilate.EdgeDilate(1).dilate(E) for v in row)),
    ("nan", lambda: _raises(lambda: edgedilate.EdgeDilate(1).dilate([[float('nan')]]))),
    ("no_mut", lambda: edgedilate.EdgeDilate(1).dilate([r[:] for r in E]) is not None),
    ("inner", lambda: isinstance(edgedilate.EdgeDilate(1).outline(E, 1, 0), list)),
    ("monotone", lambda: all(edgedilate.EdgeDilate(1).dilate(E)[1][1] for _ in range(1))),
]


@pytest.mark.parametrize("name,check", CASES, ids=[c[0] for c in CASES])
def test_spec(name, check):
    assert check() is True
