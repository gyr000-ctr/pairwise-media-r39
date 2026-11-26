"""uvsphere 核心 API（初始未实现，仅标准库）。"""


class UvSphere:
    def to_uv(self, dirn):
        """方向到 UV"""
        raise NotImplementedError

    def to_dir(self, uv):
        """UV 到方向"""
        raise NotImplementedError
