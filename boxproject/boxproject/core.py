"""boxproject 核心 API（初始未实现，仅标准库）。"""


class BoxProject:
    def face_uv(self, pos, normal):
        """面与 UV"""
        raise NotImplementedError

    def is_seam_continuous(self, eps):
        """接缝校验"""
        raise NotImplementedError
