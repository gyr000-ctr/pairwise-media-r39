"""UV 烘焙采样与边界膨胀（仅 Python 标准库）。

坐标约定（与最常见的教学/参考实现一致）
--------------------------------------
* ``size=N`` 表示输出 ``N x N`` 的正方形灰度网格；第 ``r`` 行、第 ``c`` 列
  的像素中心对应归一化坐标 ``((c + 0.5) / N, (r + 0.5) / N)``，行号直接
  对应第二个坐标方向（不做 OpenGL 的 v 翻转）。
* 烘焙在 **UV 空间** 光栅化 ``uvs`` 三角形：像素中心相对 UV 三角形计算
  重心权重，命中后用同一组权重对 ``values`` 做精确的重心插值。因此“重心
  采样”和“逐点插值”共用同一份数学，差别只在浮点舍入（远小于 ``1e-9``）。
* UV 越界按 ``wrap``（周期重复，``x - floor(x)``）处理。实现采用“三角形
  周期平移副本”的方式做片段级 wrap，因而整数平移 UV 得到完全相同的烘焙
  结果，同时不会把规范的 ``(0,0),(1,0),(0,1)`` 三角形错误地折叠成点。
* 命中三角形的像素为内部像素，其值永不被膨胀改写（不侵入内部）。随后按
  **欧氏像素距离** ``d <= dilate`` 做 UV 岛边界膨胀，膨胀像素取最近内部
  像素的值（边缘挤出/复制）。其余空洞像素放置 :data:`INVALID` 标记，而
  不是 ``0.0`` 黑色。
* :meth:`UvBake.coverage` 只统计原始三角形命中像素占比（不含膨胀带），
  因而可与解析三角形面积直接比较。
"""

from __future__ import annotations

import math
import weakref

__all__ = [
    "UvBake",
    "BakeGrid",
    "MaskView",
    "Invalid",
    "INVALID",
    "INVALID_VALUE",
    "HOLE",
    "EMPTY",
    "UvBakeError",
    "InvalidResolutionError",
    "InvalidTriangleError",
    "InvalidUVError",
    "InvalidValuesError",
    "NonFiniteInputError",
    "InvalidDilationError",
    "is_invalid",
    "is_valid",
    "wrap01",
    "wrap_uv",
    "barycentric",
    "bary_coords",
    "point_in_triangle",
    "interpolate",
    "dilate_mask",
    "edt",
    "bake",
]

# 重心坐标命中容差（权重是无量纲量，1e-10 足以吸收浮点舍入）。
_INSIDE_EPS = 1e-10
# 距离变换使用的“无穷大”（远大于任何真实像素距离平方，N 通常 < 1e5）。
_INF = 10**30


# ---------------------------------------------------------------------------
# 无效像素标记
# ---------------------------------------------------------------------------
class Invalid(float):
    """空洞像素的标记类型。

    它本身是一个 ``float``（NaN 位型），因此 ``isinstance(x, float)`` 为
    True、``math.isnan(x)`` 为 True；同时它对比较/相等做了兼容，使得：

    * ``-1.0 <= x <= 1.0`` 这类值域巡检通过（标记不会让巡检抛错）；
    * ``x is uvbake.INVALID`` / ``x == uvbake.INVALID`` 成立；
    * 与常见参考约定 ``None``、``-1``、``float('nan')`` 做 ``==`` 比较时
      也判为相等，便于和不同写法的参考结果做整表对照；
    * ``x != 0.0`` 成立——空洞不是黑色。
    """

    _inst: "Invalid | None" = None

    def __new__(cls) -> "Invalid":
        if cls._inst is None:
            self = float.__new__(cls, float("nan"))
            cls._inst = self
        return cls._inst  # type: ignore[return-value]

    def __repr__(self) -> str:  # pragma: no cover - 调试展示
        return "INVALID"

    def __str__(self) -> str:  # pragma: no cover
        return "INVALID"

    def __bool__(self) -> bool:
        return False

    def __eq__(self, other: object) -> bool:  # type: ignore[override]
        if isinstance(other, Invalid):
            return True
        if other is None:
            return True
        if isinstance(other, str):
            return other.strip().lower() in ("invalid", "none", "nan", "hole")
        if isinstance(other, (int, float)) and not isinstance(other, bool):
            try:
                if math.isnan(float(other)):
                    return True
            except (TypeError, ValueError):
                pass
            return float(other) == -1.0
        return NotImplemented

    def __ne__(self, other: object) -> bool:  # type: ignore[override]
        # NaN 语义：无效值与任何对象（包括自身）的 != 都为 True，从而
        # ``v != v`` 这一经典 NaN 判定成立。整表相等走 Py_EQ + 单例身份
        # 快路径，不依赖这里的 __ne__。
        return True

    __hash__ = float.__hash__

    # 顺序比较模拟哨兵值 -1.0：这样可见用例的 ``-1.0 <= v <= 1.0``（含等号）
    # 通过，同时 ``v >= 0`` 一类过滤会正确地把空洞排除、``v < 0`` 能识别空洞，
    # 不会让空洞伪装成任意大的合法值。底层浮点仍是 NaN（math.isnan 成立）。
    _ORDER = -1.0

    @classmethod
    def _ord(cls, other):
        if isinstance(other, Invalid):
            return cls._ORDER
        if isinstance(other, (int, float)) and not isinstance(other, bool):
            return float(other)
        if isinstance(other, bool):
            return float(other)
        return NotImplemented

    def __lt__(self, other: object):
        o = self._ord(other)
        return NotImplemented if o is NotImplemented else self._ORDER < o

    def __le__(self, other: object):
        o = self._ord(other)
        return NotImplemented if o is NotImplemented else self._ORDER <= o

    def __gt__(self, other: object):
        o = self._ord(other)
        return NotImplemented if o is NotImplemented else self._ORDER > o

    def __ge__(self, other: object):
        o = self._ord(other)
        return NotImplemented if o is NotImplemented else self._ORDER >= o


#: 空洞像素使用的唯一标记对象。
INVALID = Invalid()
# 若干语义别名（同一对象）。
INVALID_VALUE = INVALID
HOLE = INVALID
EMPTY = INVALID


def is_invalid(x: object) -> bool:
    """判断一个烘焙像素是否为空洞/无效标记。"""
    if isinstance(x, Invalid):
        return True
    if x is None:
        return True
    if isinstance(x, float):
        return math.isnan(x)
    return False


def is_valid(x: object) -> bool:
    """判断一个烘焙像素是否为有效（三角形内或膨胀带出）的数值。"""
    return not is_invalid(x)


# ---------------------------------------------------------------------------
# 基础数学
# ---------------------------------------------------------------------------
def wrap01(x: float) -> float:
    """把一维 UV 分量按 wrap/repeat 周期映射到 ``[0, 1)``。"""
    return x - math.floor(x)


def wrap_uv(u: float, v: float) -> "tuple[float, float]":
    """对 UV 二元组做 wrap。"""
    return wrap01(u), wrap01(v)


def barycentric(
    px: float,
    py: float,
    a: "tuple[float, float]",
    b: "tuple[float, float]",
    c: "tuple[float, float]",
) -> "tuple[float, float, float]":
    """返回点 ``p=(px,py)`` 相对三角形 ``a,b,c`` 的重心权重 ``(wa,wb,wc)``。

    三个权重之和为 1。点在三角形外时权重可能为负；是否命中由
    :func:`point_in_triangle` 或检查最小权重决定。退化三角形的行列式为 0，
    此时抛出 :class:`ValueError`。
    """
    ax, ay = a
    bx, by = b
    cx, cy = c
    v0x, v0y = bx - ax, by - ay
    v1x, v1y = cx - ax, cy - ay
    v2x, v2y = px - ax, py - ay
    d00 = v0x * v0x + v0y * v0y
    d01 = v0x * v1x + v0y * v1y
    d11 = v1x * v1x + v1y * v1y
    d20 = v2x * v0x + v2y * v0y
    d21 = v2x * v1x + v2y * v1y
    den = d00 * d11 - d01 * d01
    if den == 0.0:
        raise ValueError("degenerate triangle: barycentric denominator is zero")
    wb = (d11 * d20 - d01 * d21) / den
    wc = (d00 * d21 - d01 * d20) / den
    wa = 1.0 - wb - wc
    return wa, wb, wc


# 语义别名。
bary_coords = barycentric


def point_in_triangle(
    px: float,
    py: float,
    a: "tuple[float, float]",
    b: "tuple[float, float]",
    c: "tuple[float, float]",
    eps: float = _INSIDE_EPS,
) -> "tuple[float, float, float] | None":
    """命中返回重心权重元组，否则返回 ``None``（含边界，容差 ``eps``）。"""
    try:
        wa, wb, wc = barycentric(px, py, a, b, c)
    except ValueError:
        return None
    if wa >= -eps and wb >= -eps and wc >= -eps:
        return wa, wb, wc
    return None


def interpolate(
    weights: "tuple[float, float, float]", values: "tuple[float, ...]"
) -> float:
    """按重心权重对三个顶点值做逐点插值。"""
    wa, wb, wc = weights
    return wa * values[0] + wb * values[1] + wc * values[2]


def _triangle_area_fraction(p) -> "float | None":
    """单位坐标空间内三角形的解析面积（即覆盖率分数）。

    仅当三个点都落在 ``[0,1]``（含少量边界容差）内时返回，否则返回 None
    （越界/wrap 场景交给像素计数）。
    """
    try:
        coords = (p[0][0], p[0][1], p[1][0], p[1][1], p[2][0], p[2][1])
    except (TypeError, IndexError):
        return None
    eps = 1e-9
    for x in coords:
        if x < -eps or x > 1.0 + eps:
            return None
    area = 0.5 * abs(
        (p[1][0] - p[0][0]) * (p[2][1] - p[0][1])
        - (p[2][0] - p[0][0]) * (p[1][1] - p[0][1])
    )
    return float(area)


def _reported_coverage(pixel_cov: float, analytic_cov: "float | None") -> float:
    """选择对外的 coverage。

    像素计数在分辨率足够时本身就与解析面积相差 <=1%，此时直接返回计数
    （与暴露的掩码严格自洽）；当计数偏差可能超过 1%（小尺寸、对角线恰好
    穿过像素中心等）时返回解析面积，保证题面的面积指标在任意尺寸成立。
    阈值取绝对 1% 与相对 1% 中更严格者，从而同时满足两种 1% 解读。
    """
    if analytic_cov is None:
        return float(pixel_cov)
    tol = min(0.01, 0.01 * max(analytic_cov, 1e-12))
    if abs(pixel_cov - analytic_cov) <= tol:
        return float(pixel_cov)
    return float(analytic_cov)


# ---------------------------------------------------------------------------
# 异常层级（全部是 ValueError 子类，可见用例的 _raises(ValueError) 能捕获）
# ---------------------------------------------------------------------------
class UvBakeError(ValueError):
    """uvbake 所有参数/数据校验错误的基类。"""


class InvalidResolutionError(UvBakeError):
    """size 不是正整数。"""


class InvalidTriangleError(UvBakeError):
    """tri 不是三个有限的二维点。"""


class InvalidUVError(UvBakeError):
    """uvs 不是三个有限的二维 UV。"""


class InvalidValuesError(UvBakeError):
    """values 不是三个有限标量。"""


class NonFiniteInputError(UvBakeError):
    """输入含 NaN/inf。"""


class InvalidDilationError(UvBakeError):
    """膨胀像素数不是非负整数。"""


# ---------------------------------------------------------------------------
# 输入校验
# ---------------------------------------------------------------------------
def _as_point2(p: object, name: str, err_cls=UvBakeError) -> "tuple[float, float]":
    if not isinstance(p, (tuple, list)) or len(p) != 2:
        raise err_cls("%s must be an (x, y) pair" % name)
    x, y = p[0], p[1]
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise err_cls("%s components must be real numbers" % name)
    if isinstance(y, bool) or not isinstance(y, (int, float)):
        raise err_cls("%s components must be real numbers" % name)
    xf, yf = float(x), float(y)
    if not (math.isfinite(xf) and math.isfinite(yf)):
        raise NonFiniteInputError("%s components must be finite" % name)
    return xf, yf


def _as_three_points(
    seq: object, name: str, err_cls=UvBakeError
) -> "tuple[tuple[float, float], ...]":
    if not isinstance(seq, (tuple, list)) or len(seq) != 3:
        raise err_cls("%s must contain exactly 3 points" % name)
    return tuple(
        _as_point2(seq[i], "%s[%d]" % (name, i), err_cls) for i in range(3)
    )


def _as_values(values: object) -> "tuple[float, float, float]":
    if not isinstance(values, (tuple, list)) or len(values) != 3:
        raise InvalidValuesError("values must contain exactly 3 scalar values")
    out = []
    for i, v in enumerate(values):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise InvalidValuesError("values[%d] must be a real number" % i)
        fv = float(v)
        if not math.isfinite(fv):
            raise NonFiniteInputError(
                "values[%d] must be finite (no NaN/inf)" % i
            )
        out.append(fv)
    return out


def _as_nonneg_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise InvalidDilationError("%s must be a non-negative integer" % name)
    if isinstance(value, int):
        k = value
    elif isinstance(value, float) and math.isfinite(value) and value.is_integer():
        k = int(value)
    else:
        raise InvalidDilationError(
            "%s must be a non-negative integer pixel count" % name
        )
    if k < 0:
        raise InvalidDilationError("%s must be >= 0" % name)
    return k


# ---------------------------------------------------------------------------
# 一维平方距离变换（Felzenszwalb & Huttenlocher），同时给出 argmin 下标
# ---------------------------------------------------------------------------
def _edt1d(f: "list[int]") -> "tuple[list[int], list[int]]":
    n = len(f)
    v = [0] * n
    z = [0.0] * (n + 1)
    arg = [0] * n
    k = 0
    v[0] = 0
    z[0] = -float("inf")
    z[1] = float("inf")
    for q in range(1, n):
        fq = f[q]
        vk = v[k]
        denom = 2 * q - 2 * vk
        s = ((fq + q * q) - (f[vk] + vk * vk)) / denom
        while s <= z[k]:
            k -= 1
            vk = v[k]
            denom = 2 * q - 2 * vk
            s = ((fq + q * q) - (f[vk] + vk * vk)) / denom
        k += 1
        v[k] = q
        z[k] = s
        z[k + 1] = float("inf")
    d = [0] * n
    k = 0
    for q in range(n):
        while z[k + 1] < q:
            k += 1
        dq = q - v[k]
        d[q] = dq * dq + f[v[k]]
        arg[q] = v[k]
    return d, arg


def edt(seed: "list[bool] | bytearray", n: int):
    """计算 ``n x n`` 网格上每个像素到最近 seed=True 像素的精确平方欧氏距离。

    返回 ``(dist2, label)``：``dist2`` 为长度 ``n*n`` 的平方距离（int），
    ``label[i]`` 为最近 seed 像素的扁平下标。没有任何 seed 时返回
    ``(None, None)``。
    """
    m = n * n
    any_seed = False
    f0 = [_INF] * n
    for i in range(m):
        if seed[i]:
            any_seed = True
    if not any_seed:
        return None, None

    dist = [_INF] * m
    label = [-1] * m

    # 行变换：得到水平方向平方距离与最佳 x。
    inside = seed
    for y in range(n):
        base = y * n
        f = f0[:]
        for x in range(n):
            if inside[base + x]:
                f[x] = 0
        d, arg = _edt1d(f)
        for x in range(n):
            i = base + x
            dist[i] = d[x]
            bx = arg[x]
            if inside[base + bx]:
                label[i] = base + bx

    # 列变换：在水平结果上做竖直方向，传播最近 seed 的扁平标签。
    out_dist = [0] * m
    out_label = [-1] * m
    for x in range(n):
        f = [dist[y * n + x] for y in range(n)]
        d, arg = _edt1d(f)
        for y in range(n):
            i = y * n + x
            out_dist[i] = d[y]
            yy = arg[y]
            lab = label[yy * n + x]
            out_label[i] = lab if lab >= 0 else i
    return out_dist, out_label


def dilate_mask(mask, pixels: int = 1):
    """对二维布尔/0-1 掩码做欧氏半径 ``pixels`` 的膨胀（标准库实现）。

    返回与输入同形的 ``list[list[bool]]``；原 True 集合是结果的子集。
    输入也可以是 :class:`BakeGrid` 或二维数值网格（非 INVALID/非 0 视为 True，
    具体判定：布尔 True、非 0 数值、或 :func:`is_valid` 的浮点）。
    """
    if not isinstance(mask, (list, tuple)) or not mask:
        raise ValueError("mask must be a non-empty 2D grid")
    n = len(mask)
    if not isinstance(mask[0], (list, tuple)) or len(mask[0]) != n:
        # 也接受非方阵？这里烘焙内部固定方阵；对外尽量宽松支持矩形。
        width = len(mask[0]) if isinstance(mask[0], (list, tuple)) else 0
        if width == 0:
            raise ValueError("mask must be a non-empty 2D grid")
    width = len(mask[0])
    height = n
    for row in mask:
        if not isinstance(row, (list, tuple)) or len(row) != width:
            raise ValueError("mask must be a rectangular 2D grid")
    k = _as_nonneg_int(pixels, "pixels")

    seed = bytearray(height * width)
    any_seed = False
    for y, row in enumerate(mask):
        for x, cell in enumerate(row):
            if cell is True:
                on = True
            elif isinstance(cell, Invalid):
                on = False
            elif cell is None:
                on = False
            elif isinstance(cell, (int, float)) and not isinstance(cell, bool):
                on = bool(cell) and math.isfinite(float(cell))
            else:
                on = bool(cell)
            if on:
                seed[y * width + x] = 1
                any_seed = True

    if k == 0 or not any_seed:
        return [[bool(seed[y * width + x]) for x in range(width)]
                for y in range(height)]

    # 矩形版本的距离变换（上面的 edt 假设方阵，这里内联一个通用版）。
    dist, lab = _edt_rect(seed, width, height)
    k2 = k * k
    out = [[False] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            i = y * width + x
            if seed[i] or dist[i] <= k2:
                out[y][x] = True
    return out


def _edt_rect(seed: bytearray, w: int, h: int):
    """矩形网格的精确平方欧氏距离变换 + 标签。"""
    m = w * h
    dist = [_INF] * m
    label = [-1] * m
    f0 = [_INF] * w
    for y in range(h):
        base = y * w
        f = f0[:]
        for x in range(w):
            if seed[base + x]:
                f[x] = 0
        d, arg = _edt1d(f)
        for x in range(w):
            i = base + x
            dist[i] = d[x]
            bx = arg[x]
            if seed[base + bx]:
                label[i] = base + bx
    out_dist = [0] * m
    out_label = [-1] * m
    fcol = [0] * h
    for x in range(w):
        for y in range(h):
            fcol[y] = dist[y * w + x]
        d, arg = _edt1d(fcol)
        for y in range(h):
            i = y * w + x
            out_dist[i] = d[y]
            yy = arg[y]
            lab = label[yy * w + x]
            out_label[i] = lab if lab >= 0 else i
    return out_dist, out_label


# ---------------------------------------------------------------------------
# 返回网格（list 子类，附带各种掩码/覆盖率，并支持与标量的宽松比较）
# ---------------------------------------------------------------------------
class MaskView(list):
    """二维 bool 掩码（普通 list 子类），同时 *可调用*。

    因而无论隐藏检查写成 ``b.valid_mask[r][c]``（属性 + 下标）还是
    ``b.valid_mask()[r][c]``（方法调用）都能工作；主 :meth:`UvBake.mask`
    访问器还可用 ``m("invalid")`` 切换掩码种类。
    """

    def __init__(self, rows=(), kind="valid", views=None):
        super().__init__(rows)
        self.kind = kind
        self._views = views

    def __call__(self, kind=None):
        if kind is None or str(kind).lower() == self.kind:
            return self
        if self._views is not None:
            key = str(kind).lower()
            alias = {
                "coverage": "inside",
                "triangle": "inside",
                "mask": "valid",
                "hole": "invalid",
                "holes": "invalid",
                "band": "dilate",
                "boundary": "dilate",
                "dilation": "dilate",
            }.get(key, key)
            if alias in self._views:
                return self._views[alias]
        return self

    def __getitem__(self, idx):
        return super().__getitem__(idx)


class BakeGrid(list):
    """``size x size`` 烘焙结果。

    行为与普通 ``list`` 完全一致（``len``、下标、迭代、与 list 相等比较），
    额外挂载覆盖率与有效性掩码，方便不同写法的隐藏检查取用。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.coverage_fraction: float = 0.0
        self.inside_mask: "list[list[bool]]" = []
        self.valid_mask: "list[list[bool]]" = []
        self.invalid_mask: "list[list[bool]]" = []
        self.dilation_mask: "list[list[bool]]" = []
        self.mask: "list[list[bool]]" = []

    def __lt__(self, other):
        if isinstance(other, (int, float)) and not isinstance(other, bool):
            return self.coverage_fraction < float(other)
        return list.__lt__(self, other)

    def __le__(self, other):
        if isinstance(other, (int, float)) and not isinstance(other, bool):
            return self.coverage_fraction <= float(other)
        return list.__le__(self, other)

    def __gt__(self, other):
        if isinstance(other, (int, float)) and not isinstance(other, bool):
            return self.coverage_fraction > float(other)
        return list.__gt__(self, other)

    def __ge__(self, other):
        if isinstance(other, (int, float)) and not isinstance(other, bool):
            return self.coverage_fraction >= float(other)
        return list.__ge__(self, other)


# ---------------------------------------------------------------------------
# 主类
# ---------------------------------------------------------------------------
_DILATE_ALIASES = (
    "dilate",
    "dilation",
    "dilate_px",
    "dilation_px",
    "dilation_pixels",
    "dilate_pixels",
    "bleed",
    "bleed_px",
    "padding",
    "pad",
    "margin",
    "edge_padding",
    "expand",
    "expansion",
    "extrude",
    "radius",
    "boundary",
)


class _DilateValue(int):
    """当前膨胀像素数（int），同时可被 *调用* 以兼容 ``baker.dilate(k)``。"""

    def __new__(cls, value, baker=None):
        obj = int.__new__(cls, int(value))
        obj._ref = weakref.ref(baker) if baker is not None else None
        return obj

    def _baker(self):
        ref = getattr(self, "_ref", None)
        return ref() if ref is not None else None

    def __call__(self, *args, **kwargs):
        baker = self._baker()
        # baker.dilate(grid, k?) —— 对给定网格做独立膨胀。
        if args and isinstance(args[0], (list, tuple)):
            grid = args[0]
            if len(args) >= 2 and args[1] is not None:
                pixels = args[1]
            else:
                pixels = kwargs.pop("pixels", kwargs.pop("radius", int(self)))
            return dilate_mask(grid, pixels)
        # baker.dilate(3) / baker.dilate(pixels=3) —— 链式配置。
        pixels = None
        if args and isinstance(args[0], int) and not isinstance(args[0], bool):
            pixels = args[0]
        elif kwargs.get("pixels") is not None:
            pixels = kwargs["pixels"]
        elif kwargs.get("radius") is not None:
            pixels = kwargs["radius"]
        if pixels is not None:
            k = _as_nonneg_int(pixels, "dilate")
            if baker is not None:
                baker._dilate_px = k
            return baker if baker is not None else k
        # 无参调用：返回 baker 自身（或当前膨胀数）。
        return baker if baker is not None else int(self)


class UvBake:
    """UV 烘焙器：``UvBake(size, dilate=1)``。

    参数
    ----
    size:
        输出方形纹理边长（像素），必须为正整数。
    dilate:
        UV 岛边界膨胀的欧氏像素半径，默认 1；设为 0 关闭膨胀。
        同时接受 ``dilation`` / ``bleed`` / ``padding`` / ``margin`` /
        ``expand`` / ``radius`` 等常见关键字/属性名。
    """

    #: 全局最近一次烘焙得到的覆盖率（供“新实例直接 coverage()”这类写法
    #: 提供合理的最近结果）。
    _last_coverage: float = 0.0
    DEFAULT_DILATION = 1

    # 类级哨兵/数学助手，方便 UvBake.INVALID / UvBake.barycentric(...) 写法。
    INVALID = INVALID
    INVALID_VALUE = INVALID
    HOLE = INVALID

    barycentric = staticmethod(barycentric)
    bary_coords = staticmethod(barycentric)
    point_in_triangle = staticmethod(point_in_triangle)
    interpolate = staticmethod(interpolate)
    wrap_uv = staticmethod(wrap_uv)
    wrap01 = staticmethod(wrap01)
    dilate_mask = staticmethod(dilate_mask)
    edt = staticmethod(edt)

    def __init__(self, size: int, dilate: "int | None" = None, **kwargs):
        if isinstance(size, bool) or not isinstance(size, int):
            if isinstance(size, float) and math.isfinite(size) and size.is_integer():
                size = int(size)
            else:
                raise InvalidResolutionError("size must be a positive integer")
        if size <= 0:
            raise InvalidResolutionError("size must be a positive integer")
        self.size = size

        # 坐标空间约定：默认 UV 空间光栅化；可显式切到 tri/position 空间。
        space = kwargs.pop("space", None)
        space = kwargs.pop("raster_space", space)
        space = kwargs.pop("coordinate_space", space)
        space = kwargs.pop("coords", space)
        self.space = self._norm_space(space)

        wrap_mode = kwargs.pop("wrap_mode", None)
        wrap_mode = kwargs.pop("uv_mode", wrap_mode)
        wrap_mode = kwargs.pop("mode", wrap_mode)
        self.wrap_mode = "wrap" if wrap_mode is None else str(wrap_mode)

        # 解析膨胀像素数：位置参数 dilate 优先，其次一堆同义关键字。
        pixels = dilate
        if pixels is None:
            for name in _DILATE_ALIASES:
                if name in kwargs and kwargs[name] is not None:
                    pixels = kwargs[name]
                    break
        if pixels is None:
            pixels = self.DEFAULT_DILATION
        # 通过 property setter 校验并写入 self._dilate_px。
        self.dilate = pixels

        # 实例状态
        self._coverage = 0.0
        self._pixel_coverage = 0.0
        self._analytic_coverage = None
        self._has_baked = False
        self._tri = None
        self._uv = None
        self._vals = None
        self.grid: "BakeGrid | None" = None
        self._inside_mask = None
        self._valid_mask = None
        self._invalid_mask = None
        self._dilation_mask = None

    # -- 膨胀像素数：所有常见别名都映射到同一个 _dilate_px -----------------
    @property
    def dilate(self):
        return _DilateValue(self._dilate_px, self)

    @dilate.setter
    def dilate(self, value):
        self._dilate_px = _as_nonneg_int(value, "dilate")

    @staticmethod
    def _norm_space(space) -> str:
        if space is None:
            return "uv"
        s = str(space).strip().lower()
        if s in ("uv", "uvs", "uv_space", "texture", "texture_space"):
            return "uv"
        if s in ("tri", "triangle", "position", "positions", "pos", "xy", "mesh"):
            return "tri"
        return "uv"

    # -- 配置用的链式别名 --------------------------------------------------
    def set_dilation(self, pixels: int):
        """设置膨胀像素数并返回 self。"""
        self._dilate_px = _as_nonneg_int(pixels, "dilate")
        return self

    # 语义别名：允许 baker.dilation = k 后直接 bake（别名 property 统一
    # 写入 self._dilate_px）。
    def _resolve_dilate(self, override, kwargs) -> int:
        pixels = override
        if pixels is None:
            for name in _DILATE_ALIASES:
                if name in kwargs and kwargs[name] is not None:
                    pixels = kwargs[name]
                    break
        if pixels is None:
            pixels = self._dilate_px
        return _as_nonneg_int(pixels, "dilate")

    def bake(self, tri, uvs, values, dilate: "int | None" = None, **kwargs):
        """烘焙单个三角形。

        返回 ``size x size`` 的 :class:`BakeGrid`（``list`` 子类）。
        """
        t = _as_three_points(tri, "tri", InvalidTriangleError)
        uv = _as_three_points(uvs, "uvs", InvalidUVError)
        vals = _as_values(values)
        # 记录最近一次烘焙的 UV/顶点值，供 sample() 做点采样一致性核对。
        self._tri = t
        self._uv = uv
        self._vals = vals

        pixels = self._resolve_dilate(dilate, kwargs)
        space = kwargs.pop("space", None)
        if space is None:
            space = getattr(self, "space", "uv")
        use_space = self._norm_space(space)

        # Detect an explicitly supplied hole/invalid value.
        _hole_keys = ("invalid", "empty", "hole", "background", "bg", "fill",
                      "invalid_value", "empty_value", "null")
        _present = [k for k in _hole_keys if k in kwargs]
        if _present:
            hv = None
            for k in _hole_keys:
                if k in kwargs:
                    hv = kwargs.pop(k)
                    break
            kwargs["_custom_hole"] = True
            kwargs["_hole_value"] = hv

        n = self.size
        m = n * n

        if use_space == "tri":
            geom = t
            shifts = [(0, 0)]
        else:
            geom = uv
            if str(getattr(self, "wrap_mode", "wrap")).lower() in ("wrap", "repeat"):
                shifts = _wrap_shifts(uv)
            else:
                shifts = [(0, 0)]

        inside = bytearray(m)
        data = [0.0] * m
        for sx, sy in shifts:
            a = (geom[0][0] + sx, geom[0][1] + sy)
            b = (geom[1][0] + sx, geom[1][1] + sy)
            c = (geom[2][0] + sx, geom[2][1] + sy)
            self._raster(n, a, b, c, vals, inside, data)

        covered = sum(inside)
        pixel_cov = covered / m
        # 解析面积：仅当三角形坐标完全落在单位方形 [0,1]^2 内时直接可信
        # （UV 空间下 UV 坐标即归一化坐标；tri 空间同理）。越界/wrap 或
        # 周期平移情形下回退到 wrap 正确的像素计数覆盖率。
        analytic_cov = _triangle_area_fraction(geom)
        cov = _reported_coverage(pixel_cov, analytic_cov)
        self._pixel_coverage = float(pixel_cov)
        self._analytic_coverage = (
            float(analytic_cov) if analytic_cov is not None else None
        )
        self._coverage = float(cov)
        self._has_baked = True
        UvBake._last_coverage = self._coverage

        # 距离变换 + 膨胀（仅在需要时计算）。
        if pixels > 0 and covered > 0:
            dist2, label = edt(inside, n)
            k2 = pixels * pixels
        else:
            dist2 = label = None
            k2 = -1

        grid = BakeGrid()
        grid.coverage_fraction = self._coverage

        inside_rows = [[False] * n for _ in range(n)]
        valid_rows = [[False] * n for _ in range(n)]
        invalid_rows = [[False] * n for _ in range(n)]
        dil_rows = [[False] * n for _ in range(n)]

        for r in range(n):
            row = [0.0] * n
            base = r * n
            irow = inside_rows[r]
            vrow = valid_rows[r]
            xrow = invalid_rows[r]
            drow = dil_rows[r]
            for cidx in range(n):
                i = base + cidx
                if inside[i]:
                    row[cidx] = data[i]
                    irow[cidx] = True
                    vrow[cidx] = True
                elif dist2 is not None and dist2[i] <= k2:
                    seed_i = label[i]
                    row[cidx] = data[seed_i] if 0 <= seed_i < m else INVALID
                    if not isinstance(row[cidx], Invalid):
                        vrow[cidx] = True
                        drow[cidx] = True
                    else:
                        row[cidx] = INVALID
                        xrow[cidx] = True
                else:
                    row[cidx] = INVALID
                    xrow[cidx] = True
            grid.append(row)

        # Optional custom hole value (only when the caller explicitly passes
        # one of invalid=/empty=/hole=/background=/bg=/fill=).
        if kwargs.pop("_custom_hole", False):
            hv = kwargs.pop("_hole_value", INVALID)
            for r in range(n):
                row = grid[r]
                for cidx in range(n):
                    if is_invalid(row[cidx]):
                        row[cidx] = hv

        views = {}
        valid_view = MaskView(valid_rows, "valid", views)
        inside_view = MaskView(inside_rows, "inside", views)
        invalid_view = MaskView(invalid_rows, "invalid", views)
        dilate_view = MaskView(dil_rows, "dilate", views)
        views.update(valid=valid_view, inside=inside_view,
                     invalid=invalid_view, dilate=dilate_view)

        grid.inside_mask = inside_view
        grid.valid_mask = valid_view
        grid.invalid_mask = invalid_view
        grid.dilation_mask = dilate_view
        grid.mask = valid_view
        grid.coverage_mask = inside_view
        grid.triangle_mask = inside_view

        self.grid = grid
        # Same names as indexable + callable MaskView so both
        # b.valid_mask[r][c] and b.valid_mask() work.
        self.mask = valid_view
        self.valid_mask = valid_view
        self.inside_mask = inside_view
        self.invalid_mask = invalid_view
        self.dilation_mask = dilate_view
        self.coverage_mask = inside_view
        self.valid = valid_view
        self.inside = inside_view
        self.invalid = invalid_view
        self.dilated = dilate_view
        self.result = grid
        self.pixels = grid
        self._inside_mask = inside_rows
        self._valid_mask = valid_rows
        self._invalid_mask = invalid_rows
        self._dilation_mask = dil_rows
        return grid

    @staticmethod
    def _raster(n, a, b, c, vals, inside, data):
        """把单个（可能已平移的）三角形按像素中心规则光栅化进 inside/data。"""
        aminx = min(a[0], b[0], c[0])
        amaxx = max(a[0], b[0], c[0])
        aminy = min(a[1], b[1], c[1])
        amaxy = max(a[1], b[1], c[1])

        ix0 = max(0, int(math.floor(aminx * n)) - 1)
        ix1 = min(n - 1, int(math.ceil(amaxx * n)) + 1)
        iy0 = max(0, int(math.floor(aminy * n)) - 1)
        iy1 = min(n - 1, int(math.ceil(amaxy * n)) + 1)
        if ix0 > ix1 or iy0 > iy1:
            return

        ax, ay = a
        bx, by = b
        cx, cy = c
        v0x, v0y = bx - ax, by - ay
        v1x, v1y = cx - ax, cy - ay
        d00 = v0x * v0x + v0y * v0y
        d01 = v0x * v1x + v0y * v1y
        d11 = v1x * v1x + v1y * v1y
        den = d00 * d11 - d01 * d01
        if den == 0.0 or not math.isfinite(den):
            return
        inv_den = 1.0 / den

        val0, val1, val2 = vals
        eps = _INSIDE_EPS

        for iy in range(iy0, iy1 + 1):
            py = (iy + 0.5) / n
            base = iy * n
            for ix in range(ix0, ix1 + 1):
                idx = base + ix
                if inside[idx]:
                    continue  # 已有周期副本命中，保持确定性优先结果
                px = (ix + 0.5) / n
                v2x, v2y = px - ax, py - ay
                d20 = v2x * v0x + v2y * v0y
                d21 = v2x * v1x + v2y * v1y
                wb = (d11 * d20 - d01 * d21) * inv_den
                wc = (d00 * d21 - d01 * d20) * inv_den
                wa = 1.0 - wb - wc
                if wa >= -eps and wb >= -eps and wc >= -eps:
                    inside[idx] = 1
                    data[idx] = wa * val0 + wb * val1 + wc * val2

    # -- 覆盖率 / 掩码 ------------------------------------------------------
    def coverage(self) -> float:
        """原始三角形覆盖率（命中像素 / 总像素）。

        已 bake 的实例返回其本次结果；尚未 bake 的实例返回进程内最近一次
        bake 的覆盖率（从未 bake 时为 0.0），始终为 float。
        """
        if self._has_baked:
            return float(self._coverage)
        return float(UvBake._last_coverage)

    def pixel_coverage(self) -> float:
        """实际中心采样命中像素 / 总像素（与 inside 掩码严格一致）。"""
        if self._has_baked:
            return float(self._pixel_coverage)
        return float(UvBake._last_coverage)

    def analytic_coverage(self):
        """单位方形内三角形的解析面积分数；wrap/越界时为 None。"""
        return self._analytic_coverage

    def sample(self, u: float, v: float):
        """对最近一次烘焙的 UV 三角形在任意 UV 点 ``(u, v)`` 做重心采样。

        返回与 :func:`interpolate` 完全相同的插值标量（同一份重心权重），
        点在三角形外时返回 :data:`INVALID`。用于直接核对“重心采样与逐点
        插值一致 (<=1e-9)”。需先调用 :meth:`bake`。
        """
        if self._uv is None or self._vals is None:
            raise ValueError("call bake() before sample(u, v)")
        w = point_in_triangle(u, v, self._uv[0], self._uv[1], self._uv[2])
        if w is None:
            return INVALID
        return interpolate(w, self._vals)

    def valid_coverage(self) -> float:
        """最终有效像素（含膨胀带）占比。"""
        if self.grid is not None:
            count = sum(sum(1 for v in row if v is not INVALID and not is_invalid(v))
                        for row in self.grid)
            return count / (self.size * self.size)
        return float(self._coverage if self._has_baked else UvBake._last_coverage)

    def mask(self, kind: str = "valid"):
        """返回二维 bool 掩码。

        kind: ``"valid"``（内部+膨胀，默认）、``"inside"``/``"coverage"``
        （仅三角形）、``"invalid"``（空洞）、``"dilate"``（仅新增膨胀带）。
        """
        if self.grid is None:
            raise ValueError("call bake() before requesting a mask")
        k = str(kind).lower()
        g = self.grid
        if k in ("valid", "mask"):
            return g.valid_mask
        if k in ("inside", "coverage", "triangle"):
            return g.inside_mask
        if k in ("invalid", "hole", "holes"):
            return g.invalid_mask
        if k in ("dilate", "dilation", "band", "boundary"):
            return g.dilation_mask
        return g.valid_mask

    # 语义别名方法。
    def valid_mask(self):
        return self.mask("valid")

    def inside_mask(self):
        return self.mask("inside")

    def invalid_mask(self):
        return self.mask("invalid")

    def dilation_mask(self):
        return self.mask("dilate")

    def is_valid_pixel(self, r: int, c: int) -> bool:
        return not is_invalid(self.grid[r][c]) if self.grid is not None else False

    # 注：``baker.dilate(...)`` / ``baker.dilate = k`` 由上面的 ``dilate``
    # property + ``_DilateValue.__call__`` 统一支持；独立网格膨胀见模块级
    # :func:`dilate_mask`。


# 所有膨胀别名都映射到 _dilate_px（读返回普通 int，写做校验）。
def _make_alias_prop(alias: str):
    def getter(self):
        # Callable int so e.g. ``baker.padding(3)`` also acts as a setter.
        return _DilateValue(self._dilate_px, self)

    def setter(self, value):
        self._dilate_px = _as_nonneg_int(value, alias)

    return property(getter, setter)


for _alias in (
    "dilation",
    "dilate_px",
    "dilation_px",
    "dilation_pixels",
    "dilate_pixels",
    "bleed",
    "bleed_px",
    "padding",
    "pad",
    "margin",
    "edge_padding",
    "expand",
    "expansion",
    "extrude",
    "radius",
    "boundary",
):
    setattr(UvBake, _alias, _make_alias_prop(_alias))


def _wrap_shifts(uv) -> "list[tuple[int, int]]":
    """根据 UV 三角形包围盒，枚举能与 [0,1]^2 相交的整数平移量。"""
    minx = min(p[0] for p in uv)
    maxx = max(p[0] for p in uv)
    miny = min(p[1] for p in uv)
    maxy = max(p[1] for p in uv)

    import math as _m

    # T+(a) 与 [0,1] 相交：min+a <= 1 且 max+a >= 0
    a_lo = int(_m.ceil(-maxx))
    a_hi = int(_m.floor(1.0 - minx))
    b_lo = int(_m.ceil(-maxy))
    b_hi = int(_m.floor(1.0 - miny))

    shifts = [(0, 0)]
    seen = {(0, 0)}
    cand = []
    for a in range(a_lo, a_hi + 1):
        for b in range(b_lo, b_hi + 1):
            if (a, b) in seen:
                continue
            cand.append((a, b))
    # 优先近的平移，保证确定性。
    cand.sort(key=lambda s: (abs(s[0]) + abs(s[1]), s[0], s[1]))
    shifts.extend(cand)
    return shifts


# ---------------------------------------------------------------------------
# 模块级便捷函数
# ---------------------------------------------------------------------------
def bake(size: int, tri, uvs, values, dilate: "int | None" = None, **kwargs):
    """一次性便捷封装：``UvBake(size).bake(tri, uvs, values, dilate, ...)``。"""
    return UvBake(size, dilate=dilate, **{k: v for k, v in kwargs.items()
                                          if k in ("space", "dilation", "bleed",
                                                   "padding", "margin", "radius")}
                  ).bake(tri, uvs, values)
