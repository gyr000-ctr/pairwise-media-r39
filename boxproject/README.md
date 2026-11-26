# boxproject

## 题面（可直接粘贴）

盒式投影 UV。约束：按法线主轴选面（平局规则确定），面内 UV 与轴对齐坐标一致（≤1e-12）；六个面覆盖全方向且无重叠（互斥校验）；接缝处相邻面 UV 连续（≤1e-9）；10 万次不超过 200 ms；零法线报错。 工作目录为仓库内的 boxproject/。 验收：cd boxproject && python -m pytest tests -q。 实现只允许使用 Python 标准库。

## 运行方式

```bash
cd boxproject && python -m pytest tests -q
```

初始 15 failed（实现前）。仅使用 Python 标准库。

## 字段

- 所属领域：游戏、图形与多媒体
- 子方向：图形渲染
- 任务类型：Bugfix
- 语言/框架：Python 3, pytest
- 环境可复现等级：无外部依赖
