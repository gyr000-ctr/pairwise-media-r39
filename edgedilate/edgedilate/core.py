"""edgedilate 核心 API（初始未实现，仅标准库）。"""


class EdgeDilate:
    def __init__(self, radius):
        """构造"""
        raise NotImplementedError

    def dilate(self, edges):
        """膨胀"""
        raise NotImplementedError

    def outline(self, edges, inner, outer):
        """描边"""
        raise NotImplementedError
