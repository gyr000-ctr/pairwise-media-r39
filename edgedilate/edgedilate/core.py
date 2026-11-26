"""edgedilate 核心 API：边缘图膨胀与描边（仅标准库）。

算法：精确欧氏距离变换的可分离分解。

    dist^2(x, y) = min over x' of (x - x')^2 + g(x', y)^2

其中 g(x', y) 是第 x' 列内到最近边缘像素的垂直距离，用两次线性扫描
（自顶向下 + 自底向上）求得；随后每一行独立求一维锥形包络

    covered(x) <=>  存在 x' 使得 |x - x'| <= reach(x')
             <=>  max_{x'<=x}(reach(x') + x') - x >= 0
               或 max_{x'>=x}(reach(x') - x') + x >= 0

两个 running max 用 itertools.accumulate 在 C 层完成。整体时间复杂度
O(H * W)，结果与逐像素暴力半径搜索完全一致（半径判定含 1e-9 容差）。
"""

import math
from itertools import accumulate

__all__ = ["EdgeDilate"]

# 行包络中“无贡献”位置的哨兵值（足够小，加减列号后仍为负）
_NEG = -10**18
# 半径 / 距离判定容差，与题面 1e-9 一致
_EPS = 1e-9


def _raise_nan():
    raise ValueError("edges must not contain NaN cells")


def _check_width(value, name, allow_zero):
    """校验半径 / 描边宽度，返回 float。非法值抛 ValueError。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("%s must be a real number, got %r" % (name, value))
    if not math.isfinite(value):
        raise ValueError("%s must be finite, got %r" % (name, value))
    if allow_zero:
        if value < 0:
            raise ValueError("%s must be >= 0, got %r" % (name, value))
    elif value <= 0:
        raise ValueError("%s must be > 0, got %r" % (name, value))
    return float(value)


def _validate_edges(edges):
    """校验并拷贝为 bool 二维列表；不修改输入。非法输入抛 ValueError。"""
    if not isinstance(edges, (list, tuple)) or len(edges) == 0:
        raise ValueError("edges must be a non-empty 2D sequence")
    grid = []
    width = None
    for row in edges:
        if not isinstance(row, (list, tuple)) or len(row) == 0:
            raise ValueError("each edges row must be a non-empty sequence")
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ValueError("edges rows must all have the same length")
        # v == v 仅对 NaN 为 False；其余按真值转为 bool
        grid.append([bool(v) if v == v else _raise_nan() for v in row])
    return grid, width


def _dilate(grid, height, width, r):
    """对 bool 网格按半径 r（>= 0）做精确欧氏膨胀，返回 bool 二维列表。"""
    sqrt = math.sqrt
    r2 = r * r
    # 最大可取整垂直距离（含 1e-9 容差）
    rmax = int(math.floor(r + _EPS))
    # reach[v]：垂直距离为整数 v 时，水平方向可覆盖的最大整数距离
    # floor(sqrt(r^2 - v^2) + eps)。查表避免逐像素开方。
    lut = []
    for v in range(rmax + 1):
        d2 = r2 - v * v
        # r2 浮点舍入可能使 d2 出现微小负值，此时真实 reach 为 0
        lut.append(int(sqrt(d2) + _EPS) if d2 > 0.0 else 0)

    # 哨兵：大于任何真实垂直距离，且加上行索引后仍 > rmax，
    # 保证“列内无边缘”的位置最终映射为 _NEG 而不是被误认为可达。
    inf = height + rmax + 1
    # 第一遍：自顶向下，g[y][x] = 列 x 中 (y 含) 上方最近边缘的垂直距离
    g = []
    prev = [inf] * width
    for row in grid:
        cur = [0 if e else p + 1 for e, p in zip(row, prev)]
        g.append(cur)
        prev = cur

    # 第二遍：自底向上合并下方距离，并立即完成该行的水平包络
    out = [None] * height
    below = [inf + 1] * width  # below[x] = 下一行最终垂直距离 + 1
    acc = accumulate
    neg = _NEG
    for y in range(height - 1, -1, -1):
        grow = g[y]
        final = [a if a <= b else b for a, b in zip(grow, below)]
        below = [v + 1 for v in final]
        if min(final) > rmax:
            # 整行都在半径之外
            out[y] = [False] * width
            continue
        reach = [lut[v] if v <= rmax else neg for v in final]
        fp = [f + x for x, f in enumerate(reach)]
        fm = [f - x for x, f in enumerate(reach)]
        fwd = list(acc(fp, max))  # fwd[x] = max_{x'<=x} reach(x') + x'
        bwd = list(acc(fm[::-1], max))  # 反向后 bwd[x] = max_{x'>=x} reach(x') - x'
        bwd.reverse()
        out[y] = [a >= x or b >= -x for x, (a, b) in enumerate(zip(fwd, bwd))]
    return out


class EdgeDilate:
    """二值边缘图的欧氏膨胀与描边。

    radius 必须为正实数（int 或 float，非 bool、非 NaN/inf），否则 ValueError。
    """

    def __init__(self, radius):
        """构造：校验并保存膨胀半径。"""
        self.radius = _check_width(radius, "radius", allow_zero=False)

    def dilate(self, edges):
        """膨胀：返回与 edges 同形的 bool 二维列表。

        结果像素为真当且仅当其到最近边缘像素的欧氏距离 <= radius
        （含 1e-9 容差），因此必然包含原边缘（单调）。输入不被修改。
        """
        grid, width = _validate_edges(edges)
        return _dilate(grid, len(grid), width, self.radius)

    def outline(self, edges, inner, outer):
        """描边：沿边缘生成总宽 inner + outer 的描边带。

        inner（内描边）与 outer（外描边）分别可调，均须为 >= 0 的实数，
        否则 ValueError。返回与 edges 同形的 bool 二维列表。
        """
        inner = _check_width(inner, "inner", allow_zero=True)
        outer = _check_width(outer, "outer", allow_zero=True)
        grid, width = _validate_edges(edges)
        return _dilate(grid, len(grid), width, inner + outer)
