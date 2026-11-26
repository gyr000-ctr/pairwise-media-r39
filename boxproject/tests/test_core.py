import math

import pytest

import boxproject

def _raises(fn, exc=ValueError):
    try:
        fn()
    except exc:
        return True
    return False

P = (0.25, 0.5, 0.75)
N = (0.0, 0.0, 1.0)

CASES = [
    ("triple", lambda: len(boxproject.BoxProject().face_uv(P, N)) == 3),
    ("face_range", lambda: 0 <= boxproject.BoxProject().face_uv(P, N)[0] < 6),
    ("uv_range", lambda: all(0.0 <= c <= 1.0 for c in boxproject.BoxProject().face_uv(P, N)[1:])),
    ("zero_normal", lambda: _raises(lambda: boxproject.BoxProject().face_uv(P, (0.0, 0.0, 0.0)))),
    ("bad_pos", lambda: _raises(lambda: boxproject.BoxProject().face_uv((0.0, 0.0), N))),
    ("seam", lambda: boxproject.BoxProject().is_seam_continuous(1e-9) is True),
    ("type", lambda: isinstance(boxproject.BoxProject().face_uv(P, N), tuple)),
    ("det", lambda: boxproject.BoxProject().face_uv(P, N) == boxproject.BoxProject().face_uv(P, N)),
    ("axis_x", lambda: boxproject.BoxProject().face_uv(P, (1.0, 0.0, 0.0))[0] != boxproject.BoxProject().face_uv(P, N)[0]),
    ("bad_eps", lambda: _raises(lambda: boxproject.BoxProject().is_seam_continuous(0.0))),
    ("nan", lambda: _raises(lambda: boxproject.BoxProject().face_uv((float('nan'), 0.5, 0.5), N))),
    ("no_mut", lambda: boxproject.BoxProject().face_uv(P, N) is not None),
    ("float", lambda: isinstance(boxproject.BoxProject().face_uv(P, N)[1], float)),
    ("bool_seam", lambda: isinstance(boxproject.BoxProject().is_seam_continuous(1e-6), bool)),
    ("six_faces", lambda: len({boxproject.BoxProject().face_uv(P, n)[0] for n in [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]}) == 6),
]


@pytest.mark.parametrize("name,check", CASES, ids=[c[0] for c in CASES])
def test_spec(name, check):
    assert check() is True
