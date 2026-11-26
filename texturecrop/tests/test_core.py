import math

import pytest

import texturecrop

def _raises(fn, exc=ValueError):
    try:
        fn()
    except exc:
        return True
    return False

T = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]]

CASES = [
    ("size", lambda: len(texcrop.TexCrop(T).crop((0, 0, 2, 2))) == 2),
    ("value", lambda: abs(texcrop.TexCrop(T).crop((0, 0, 1, 1))[0][0] - 0.1) < 1e-12),
    ("wrap", lambda: isinstance(texcrop.TexCrop(T).crop((-1, -1, 2, 2), 'wrap'), list)),
    ("clamp", lambda: isinstance(texcrop.TexCrop(T).crop((-1, -1, 2, 2), 'clamp'), list)),
    ("mirror", lambda: isinstance(texcrop.TexCrop(T).crop((-1, -1, 2, 2), 'mirror'), list)),
    ("bad_mode", lambda: _raises(lambda: texcrop.TexCrop(T).crop((0, 0, 1, 1), 'bogus'))),
    ("bad_rect", lambda: _raises(lambda: texcrop.TexCrop(T).crop((0, 0, 0, 1)))),
    ("bad_tex", lambda: _raises(lambda: texcrop.TexCrop([]))),
    ("type", lambda: isinstance(texcrop.TexCrop(T).crop((0, 0, 2, 2)), list)),
    ("det", lambda: texcrop.TexCrop(T).crop((0, 0, 2, 2)) == texcrop.TexCrop(T).crop((0, 0, 2, 2))),
    ("wrap_differs", lambda: texcrop.TexCrop(T).crop((-1, 0, 1, 1), 'wrap') != texcrop.TexCrop(T).crop((-1, 0, 1, 1), 'clamp')),
    ("nan", lambda: _raises(lambda: texcrop.TexCrop([[float('nan')]]).crop((0, 0, 1, 1)))),
    ("no_mut", lambda: texcrop.TexCrop([r[:] for r in T]).crop((1, 1, 2, 2)) is not None),
    ("float", lambda: isinstance(texcrop.TexCrop(T).crop((0, 0, 1, 1))[0][0], float)),
    ("offset", lambda: isinstance(texcrop.TexCrop(T).crop((5, 5, 2, 2)), list)),
]


@pytest.mark.parametrize("name,check", CASES, ids=[c[0] for c in CASES])
def test_spec(name, check):
    assert check() is True
