"""texturecrop 核心 API（仅标准库）。

纹理以等宽二维列表表示，元素为浮点（也接受整型）。
``crop`` 按 ``(x, y, w, h)`` 矩形裁剪，支持三种越界寻址模式：

- ``wrap``：周期重复（GL_REPEAT），``i -> i % n``；
- ``clamp``：钳制到边界（GL_CLAMP_TO_EDGE），越界取最边缘像素；
- ``mirror``：镜像重复（GL_MIRRORED_REPEAT），每越过一次边界方向翻转。
"""

_VALID_MODES = ('wrap', 'clamp', 'mirror')


class TexCrop:
    def __init__(self, tex):
        """构造：校验并持有纹理。

        ``tex`` 必须是非空、等宽的二维数值列表，且不得包含 NaN。
        """
        if not isinstance(tex, list) or not tex:
            raise ValueError('tex 必须为非空二维列表')
        width = len(tex[0])
        if not isinstance(tex[0], list) or width == 0:
            raise ValueError('tex 必须为非空二维列表')
        for row in tex:
            if not isinstance(row, list) or len(row) != width:
                raise ValueError('tex 的每一行必须是等宽列表')
            for v in row:
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    raise ValueError('tex 元素必须为数值')
                if v != v:  # NaN：NaN 是唯一不等于自身的浮点数
                    raise ValueError('tex 不允许包含 NaN')
        self._tex = tex
        self._h = len(tex)
        self._w = width

    def crop(self, rect, mode='wrap'):
        """按 ``rect=(x, y, w, h)`` 裁剪，``x/y`` 可为负。

        返回与请求尺寸一致的新二维列表；越界坐标按 ``mode`` 填充。
        """
        if mode not in _VALID_MODES:
            raise ValueError(
                "非法寻址模式 %r，仅支持 'wrap' / 'clamp' / 'mirror'" % (mode,)
            )
        if not isinstance(rect, (tuple, list)) or len(rect) != 4:
            raise ValueError('rect 必须是 (x, y, w, h) 四元组')
        if not all(type(v) is int for v in rect):
            raise ValueError('rect 的四个分量必须为整数')
        x0, y0, cw, ch = rect
        if cw <= 0 or ch <= 0:
            raise ValueError('裁剪宽高必须为正整数')

        h, w = self._h, self._w
        col_idx = self._axis_indices(x0, cw, w, mode)
        row_idx = self._axis_indices(y0, ch, h, mode)

        tex = self._tex
        out = []
        for r in row_idx:
            src = tex[r]
            out.append([src[c] for c in col_idx])
        return out

    @staticmethod
    def _axis_indices(start, count, n, mode):
        """预计算输出轴上每个位置对应的源纹理下标。"""
        idx = [0] * count
        if mode == 'wrap':
            for k in range(count):
                idx[k] = (start + k) % n
        elif mode == 'clamp':
            last = n - 1
            for k in range(count):
                i = start + k
                if i < 0:
                    idx[k] = 0
                elif i > last:
                    idx[k] = last
                else:
                    idx[k] = i
        else:  # mirror：周期为 2n，后半周期反向
            period = n * 2
            last = n - 1
            for k in range(count):
                t = (start + k) % period
                idx[k] = t if t < n else period - 1 - t
        return idx
