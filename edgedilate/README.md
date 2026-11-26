# edgedilate

## 题面（可直接粘贴）

边缘图膨胀与描边。约束：膨胀半径可配且与距离变换一致（≤1e-9）；结果包含原边缘（单调）；外描边与内描边分别可调；与暴力半径搜索对照 ≤1 像素；100 万像素不超过 700 ms；非法半径报错。 工作目录为仓库内的 edgedilate/。 验收：cd edgedilate && python -m pytest tests -q。 实现只允许使用 Python 标准库。

## 运行方式

```bash
cd edgedilate && python -m pytest tests -q
```

初始 15 failed（实现前）。仅使用 Python 标准库。

## 字段

- 所属领域：游戏、图形与多媒体
- 子方向：图像处理
- 任务类型：Bugfix
- 语言/框架：Python 3, pytest
- 环境可复现等级：无外部依赖
