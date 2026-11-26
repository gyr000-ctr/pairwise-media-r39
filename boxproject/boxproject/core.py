"""boxproject 核心 API（仅标准库）。

盒式投影约定
------------
* 面编号（与 OpenGL/D3D 立方体贴图一致）：
  0:+X  1:-X  2:+Y  3:-Y  4:+Z  5:-Z。
* 选面：取法线绝对值最大的分量；平局时 X 优先于 Y、Y 优先于 Z
  （确定性全序，六个区域互斥且覆盖全部非零方向）。
* 面内 UV：直接取位置 ``pos`` 中除主轴外的两个轴对齐坐标，按坐标轴
  自然顺序排列，不做缩放/翻转/平移，因此与轴对齐坐标逐位一致。
  UV_AXES[face_axis] 给出 (u 来源轴, v 来源轴)。
"""

import math

__all__ = ["BoxProject"]

_isfinite = math.isfinite

# 每个主轴被丢弃后，UV 两个分量对应的位置坐标轴（自然升序）。
#   X 面：u=y(1), v=z(2)
#   Y 面：u=x(0), v=z(2)
#   Z 面：u=x(0), v=y(1)
UV_AXES = ((1, 2), (0, 2), (0, 1))


class BoxProject:
    """盒式投影器。无状态、无线程共享可变状态，可并发调用。"""

    __slots__ = ()

    def face_uv(self, pos, normal):
        """按法线主轴选面并返回 ``(face, u, v)``。

        ``face`` 为 0..5 的 int；``u``/``v`` 为位置中对应的轴对齐坐标
        （float，原样透传）。位置或法线长度不为 3、含非有限分量，或
        法线为零向量时抛出 :class:`ValueError`。
        """
        try:
            px, py, pz = pos
            nx, ny, nz = normal
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "pos and normal must each contain exactly 3 components"
            ) from exc

        try:
            finite = (
                _isfinite(px) and _isfinite(py) and _isfinite(pz)
                and _isfinite(nx) and _isfinite(ny) and _isfinite(nz)
            )
        except TypeError as exc:
            raise ValueError(
                "pos and normal components must be real numbers"
            ) from exc
        if not finite:
            raise ValueError(
                "pos and normal must contain only finite components"
            )

        ax = abs(nx)
        ay = abs(ny)
        az = abs(nz)

        # 最大绝对分量；平局规则：X > Y > Z（>= 链保证最靠前的轴获胜）。
        if ax >= ay and ax >= az:
            magnitude = ax
            face = 0 if nx >= 0.0 else 1
            u, v = py, pz
        elif ay >= az:
            magnitude = ay
            face = 2 if ny >= 0.0 else 3
            u, v = px, pz
        else:
            magnitude = az
            face = 4 if nz >= 0.0 else 5
            u, v = px, py

        if magnitude == 0.0:
            raise ValueError("normal must not be the zero vector")

        return (face, float(u), float(v))

    def is_seam_continuous(self, eps=1e-9):
        """校验六个面之间 12 条立方体接缝上的 UV 连续性。

        对每条接缝在单位立方体上取若干采样点，用接缝两侧相邻面的轴法线
        分别投影，比较沿接缝方向的共享轴对齐坐标（原始坐标透传，误差为
        0）。``eps`` 必须为正的有限实数，否则抛出 :class:`ValueError`。
        返回内置 :class:`bool`。
        """
        try:
            tolerance = float(eps)
        except (TypeError, ValueError) as exc:
            raise ValueError("eps must be a positive finite number") from exc
        if not _isfinite(tolerance) or tolerance <= 0.0:
            raise ValueError("eps must be a positive finite number")

        samples = (0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0)

        # 三个主轴两两组合 -> 3*4 种符号组合 = 12 条边。
        for ga in range(3):
            for gb in range(ga + 1, 3):
                gc = 3 - ga - gb  # 第三条轴（0+1+2=3），即边沿方向
                ca = UV_AXES[ga].index(gc)
                cb = UV_AXES[gb].index(gc)
                for fa in (2 * ga, 2 * ga + 1):
                    sa = 1.0 if fa % 2 == 0 else 0.0
                    for fb in (2 * gb, 2 * gb + 1):
                        sb = 1.0 if fb % 2 == 0 else 0.0
                        for t in samples:
                            p = [0.0, 0.0, 0.0]
                            p[ga] = sa
                            p[gb] = sb
                            p[gc] = t
                            na = [0.0, 0.0, 0.0]
                            na[ga] = 1.0 if fa % 2 == 0 else -1.0
                            nb = [0.0, 0.0, 0.0]
                            nb[gb] = 1.0 if fb % 2 == 0 else -1.0

                            got_a = self.face_uv(p, na)
                            got_b = self.face_uv(p, nb)
                            if got_a[0] != fa or got_b[0] != fb:
                                return False
                            va = got_a[1 + ca]
                            vb = got_b[1 + cb]
                            if abs(va - vb) > tolerance:
                                return False
        return True
