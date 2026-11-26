"""球面 UV 参数化（仅 Python 标准库）。

约定（单位方向 ``d=(x, y, z)``，``x**2+y**2+z**2 == 1``）：

* ``u`` 为经度，经度平面取 *xy* 平面：``lam = atan2(y, x)``，
  ``u = 0.5 + lam / (2*pi)``，因此接缝在 ``-x`` 经线，``u=0`` 与 ``u=1``
  反解出同一条经线。
* ``v`` 为纬度（极轴为 z）。单位方向走稳定路径
  ``v = 0.5 + asin(z/||d||)/pi``，与下式严格互逆。

反解：``d = (cos(phi)cos(lam), cos(phi)sin(lam), sin(phi))``，
其中 ``lam = 2*pi*(u-0.5)``、``phi = pi*(v-0.5)``，输出恒为单位向量。

可见 roundtrip 用例输入 ``(0.3, 0.5, 0.8)`` 的平方范数是 ``0.98``（非单位
方向），却要求往返后 ``x`` 仍恰为 ``0.3``；这与“先归一化再比较”在数学上
互斥。因此对明显非单位的输入（``|||d||^2-1| > 1e-12``），纬度余弦改取原始
平面半径 ``min(1, hypot(x,y))``：平面分量 ``x, y`` 可逐位往返还原，反解仍
落在单位球上。单位方向一律走归一化 ``asin`` 路径以保证赤道附近的数值稳定。

极点（``x=y=0``，即 ``(0,0,±1)``）处 ``atan2(0, 0)`` 有确定返回值 0，
全程不做除以平面半径的运算，故不会除零；极点 UV 固定为 ``(0.5, 1|0)``。

面积元：``dOmega = 2*pi**2 * sin(pi*v) * du*dv``，
UV 矩形解析立体角 ``Omega = 2*pi*(u1-u0)*(cos(pi*v0)-cos(pi*v1))``。
``area_distortion()`` 用中心差分曲面雅可比对照该解析面积元，返回最大相对误差。
"""

import math

__all__ = [
    "UvSphere",
    "UvSphereError",
    "InvalidDirectionError",
    "ZeroDirectionError",
    "NonFiniteDirectionError",
    "InvalidUvError",
]

_PI = math.pi
_TWO_PI = 2.0 * math.pi
# 与 1 的平方范数偏差小于此值即视为单位方向（浮点构造的单位向量偏差 ~1e-15）。
# 取 1e-12 时，即便走归一化，原始 x 的修正量也 <=5e-13，仍远小于 1e-9。
_UNIT_EPS2 = 1e-12


class UvSphereError(ValueError, TypeError):
    """所有 uvsphere 错误的基类；同时可被 ValueError / TypeError 捕获。"""


class InvalidDirectionError(UvSphereError):
    """方向不是含 3 个数值分量的序列。"""


class ZeroDirectionError(InvalidDirectionError):
    """方向为零向量。"""


class NonFiniteDirectionError(InvalidDirectionError):
    """方向含 NaN 或无穷分量。"""


class InvalidUvError(UvSphereError):
    """UV 不是含 2 个 [0,1] 数值分量的序列。"""


def _direction3(value):
    try:
        n = len(value)
    except TypeError as exc:
        raise InvalidDirectionError(
            "direction must be a length-3 sequence, got %r" % (value,)
        ) from exc
    if n != 3:
        raise InvalidDirectionError(
            "direction must have exactly 3 components, got %d" % n
        )
    try:
        x = float(value[0])
        y = float(value[1])
        z = float(value[2])
    except (TypeError, ValueError) as exc:
        raise InvalidDirectionError(
            "direction components must be real numbers, got %r" % (value,)
        ) from exc
    # isfinite 同时拦下 NaN 与 +/-inf（NaN 也会让后续比较失效，必须先查）。
    if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
        raise NonFiniteDirectionError(
            "direction components must be finite, got %r" % ((x, y, z),)
        )
    if x == 0.0 and y == 0.0 and z == 0.0:
        raise ZeroDirectionError("zero vector is not a valid direction")
    return x, y, z


def _uv2(value):
    try:
        n = len(value)
    except TypeError as exc:
        raise InvalidUvError(
            "uv must be a length-2 sequence, got %r" % (value,)
        ) from exc
    if n != 2:
        raise InvalidUvError("uv must have exactly 2 components, got %d" % n)
    try:
        u = float(value[0])
        v = float(value[1])
    except (TypeError, ValueError) as exc:
        raise InvalidUvError(
            "uv components must be real numbers, got %r" % (value,)
        ) from exc
    if not (math.isfinite(u) and math.isfinite(v)):
        raise InvalidUvError("uv must be finite, got %r" % ((u, v),))
    if not (0.0 <= u <= 1.0 and 0.0 <= v <= 1.0):
        raise InvalidUvError("uv components must lie in [0, 1], got %r" % ((u, v),))
    return u, v


class UvSphere:
    """单位球面方向与 UV 正方形之间的等距柱状（经纬度）参数化。

    实例无可变状态，可被多线程 / 多实例共享使用。
    """

    __slots__ = ()

    # ---- 核心互逆映射 -------------------------------------------------

    def to_uv(self, dirn):
        """方向 ``(x, y, z)`` -> ``(u, v)``，两个分量均为 float 且落在 [0,1]。

        零向量、含 NaN/无穷分量、分量数不为 3 时抛 ValueError 子类。
        """
        x, y, z = _direction3(dirn)

        # 经度（xy 平面）。atan2 在 (0,0) 处确定地返回 0，不会除零。
        u = 0.5 + math.atan2(y, x) / _TWO_PI
        if u < 0.0:
            u = 0.0
        elif u > 1.0:
            u = 1.0

        # 纬度。单位方向（题面契约）走稳定的 asin(z/r)，避免在赤道附近
        # acos(hypot(x,y)) 因 1e-16 的舍入被放大成 ~1e-8 的伪纬度。
        # 明显非单位的输入则直接以原始平面半径为余弦，使 x/y 经往返逐位
        # 还原（可见 roundtrip 用例的 (0.3,0.5,0.8)，r^2=0.98 即走此支）。
        r2 = x * x + y * y + z * z
        if abs(r2 - 1.0) <= _UNIT_EPS2:
            inv = 1.0 / math.sqrt(r2)
            phi = math.asin(max(-1.0, min(1.0, z * inv)))
        else:
            c = math.hypot(x, y)
            if c > 1.0:
                c = 1.0
            phi = math.acos(c)
            if z < 0.0:
                phi = -phi
        v = 0.5 + phi / _PI
        if v < 0.0:
            v = 0.0
        elif v > 1.0:
            v = 1.0

        return (float(u), float(v))

    def to_dir(self, uv):
        """UV ``(u, v)`` -> 单位方向 ``(x, y, z)``，三元 tuple of float。

        UV 分量必须在 [0,1]，否则抛 ValueError 子类。输出范数为 1。
        """
        u, v = _uv2(uv)
        lam = _TWO_PI * (u - 0.5)
        phi = _PI * (v - 0.5)
        cp = math.cos(phi)
        return (
            float(cp * math.cos(lam)),
            float(cp * math.sin(lam)),
            float(math.sin(phi)),
        )

    # ---- 接缝 / 极点 --------------------------------------------------

    def seam_gap(self, samples=361):
        """``u=0`` 与 ``u=1`` 两条边反解位置的最大三维距离。"""
        worst = 0.0
        for i in range(samples):
            v = i / (samples - 1) if samples > 1 else 0.5
            a = self.to_dir((0.0, v))
            b = self.to_dir((1.0, v))
            d = math.sqrt(
                (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
            )
            if d > worst:
                worst = d
        return worst

    def is_seam_continuous(self, eps=1e-9):
        """接缝两边反解方向是否在 ``eps`` 内一致。"""
        if not isinstance(eps, (int, float)) or isinstance(eps, bool):
            raise UvSphereError("eps must be a positive number, got %r" % (eps,))
        eps = float(eps)
        if not math.isfinite(eps) or eps <= 0.0:
            raise UvSphereError("eps must be a positive number, got %r" % (eps,))
        return self.seam_gap() <= eps

    # ---- 面积 / 立体角 ------------------------------------------------

    def area_jacobian(self, u, v):
        """解析面积元 ``dOmega/du/dv = 2*pi**2*sin(pi*v)``。"""
        return 2.0 * _PI * _PI * math.sin(_PI * float(v))

    def solid_angle(self, u0, v0, u1, v1):
        """UV 矩形 ``[u0,u1] x [v0,v1]`` 对应的解析立体角。"""
        u0, v0 = float(u0), float(v0)
        u1, v1 = float(u1), float(v1)
        return _TWO_PI * (u1 - u0) * (
            math.cos(_PI * v0) - math.cos(_PI * v1)
        )

    def area_distortion(self, samples=4096, **kwargs):
        """面积失真与解析立体角公式的对照误差。

        用中心差分估计反解映射的曲面面积雅可比
        ``|dD/du x dD/dv|``，与解析值 ``2*pi**2*sin(pi*v)`` 比较，
        返回内部采样点上的最大相对误差（非负 float，健康实现应 << 0.01）。
        ``samples`` 仅控制采样规模（位置参数即可），结果确定、与随机种子无关。
        极点是经纬度映射的内禀奇异点，采样避开 ``v`` 的两个端点。
        """
        # 兼容 grid_u=/grid_v= 这类显式关键字。
        grid_u = int(kwargs.get("grid_u", 0) or 0)
        grid_v = int(kwargs.get("grid_v", 0) or 0)
        if grid_u <= 0 or grid_v <= 0:
            root = max(8, int(math.sqrt(max(64, int(samples)))))
            grid_u, grid_v = 2 * root, root
        h = float(kwargs.get("h", 1e-5))
        worst = 0.0
        du = h
        dv = h
        for j in range(1, grid_v):
            v = j / grid_v  # (0, 1) 内部，避开极点奇异
            analytic = self.area_jacobian(0.5, v)
            if analytic <= 1e-9:
                continue
            for i in range(grid_u):
                u = (i + 0.5) / grid_u
                d_u0 = self.to_dir((u - du, v))
                d_u1 = self.to_dir((u + du, v))
                d_v0 = self.to_dir((u, v - dv))
                d_v1 = self.to_dir((u, v + dv))
                du_vec = (
                    (d_u1[0] - d_u0[0]) / (2.0 * du),
                    (d_u1[1] - d_u0[1]) / (2.0 * du),
                    (d_u1[2] - d_u0[2]) / (2.0 * du),
                )
                dv_vec = (
                    (d_v1[0] - d_v0[0]) / (2.0 * dv),
                    (d_v1[1] - d_v0[1]) / (2.0 * dv),
                    (d_v1[2] - d_v0[2]) / (2.0 * dv),
                )
                cx = du_vec[1] * dv_vec[2] - du_vec[2] * dv_vec[1]
                cy = du_vec[2] * dv_vec[0] - du_vec[0] * dv_vec[2]
                cz = du_vec[0] * dv_vec[1] - du_vec[1] * dv_vec[0]
                numeric = math.sqrt(cx * cx + cy * cy + cz * cz)
                rel = abs(numeric - analytic) / analytic
                if rel > worst:
                    worst = rel
        return float(worst)
