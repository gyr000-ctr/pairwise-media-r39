# texturecrop

## 题面（可直接粘贴）

纹理裁剪与环绕。约束：裁剪区域支持 wrap/clamp/mirror 三种模式且与逐像素参考一致（≤1e-12）；越界部分按模式填充；裁剪尺寸与请求一致；负偏移可用；100 万像素不超过 500 ms；非法模式报错。 工作目录为仓库内的 texturecrop/。 验收：cd texturecrop && python -m pytest tests -q。 实现只允许使用 Python 标准库。

## 运行方式

```bash
cd texturecrop && python -m pytest tests -q
```

初始 15 failed（实现前）。仅使用 Python 标准库。

## 字段

- 所属领域：游戏、图形与多媒体
- 子方向：图像处理
- 任务类型：Bugfix
- 语言/框架：Python 3, pytest
- 环境可复现等级：无外部依赖
