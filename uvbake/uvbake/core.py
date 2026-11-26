"""uvbake 核心 API（初始未实现，仅标准库）。"""


class UvBake:
    def __init__(self, size):
        """构造"""
        raise NotImplementedError

    def bake(self, tri, uvs, values):
        """烘焙"""
        raise NotImplementedError

    def coverage(self):
        """覆盖率"""
        raise NotImplementedError
