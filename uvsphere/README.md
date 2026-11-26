# uvsphere

## 题面（可直接粘贴）

球面 UV 参数化。约束：方向到 UV 与反解互逆（≤1e-9）；极点处经度退化需返回确定值而不除零；接缝经度 0/1 处连续（跳变 ≤1e-9）；面积失真与解析立体角对照 ≤1%；10 万次不超过 300 ms；零向量报错。 工作目录为仓库内的 uvsphere/。 验收：cd uvsphere && python -m pytest tests -q。 实现只允许使用 Python 标准库。

## 运行方式

```bash
cd uvsphere && python -m pytest tests -q
```

初始 15 failed（实现前）。仅使用 Python 标准库。

## 字段

- 所属领域：游戏、图形与多媒体
- 子方向：图形渲染
- 任务类型：Bugfix
- 语言/框架：Python 3, pytest
- 环境可复现等级：无外部依赖
