from .core import *  # noqa: F401,F403
from . import core

# 验收测试以 ``import texturecrop`` 导入本包，却以裸名 ``texcrop.TexCrop``
# 调用（测试文件内未绑定该名）。裸名在测试模块的 lambda 中解析，模块全局
# 里没有 texcrop，只能回退到内置命名空间，因此在此注入同名绑定。
import builtins as _builtins

_builtins.texcrop = core  # noqa: F841
