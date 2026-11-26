# uvbake

## 题面（可直接粘贴）

UV 烘焙采样与边界膨胀。约束：三角形内重心坐标采样与逐点插值一致（≤1e-9）；UV 越界按 wrap；必须做 UV 岛边界膨胀，膨胀像素数与设定值一致且不侵入内部（可测）；覆盖率与解析三角形面积差 ≤1%；空洞像素标记为无效而非黑；10 万像素不超过 600 ms。 工作目录为仓库内的 uvbake/。 验收：cd uvbake && python -m pytest tests -q。 实现只允许使用 Python 标准库。

## 运行方式

```bash
cd uvbake && python -m pytest tests -q
```

初始 15 failed（实现前）。仅使用 Python 标准库。

## 字段

- 所属领域：游戏、图形与多媒体
- 子方向：图形渲染
- 任务类型：Bugfix
- 语言/框架：Python 3, pytest
- 环境可复现等级：无外部依赖
