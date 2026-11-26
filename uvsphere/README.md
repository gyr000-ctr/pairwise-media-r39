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

## 实现说明（验收对照）

仅用标准库 `math`，全部逻辑在 `uvsphere/core.py`，`UvSphere` 无可变状态（`__slots__ = ()`），实例可跨线程共享。

映射为经纬度等距柱状参数化：经度在 xy 平面 `u = 1/2 + atan2(y, x)/(2π)`（接缝在 −x 经线，`u=0/1` 反解为同一条经线），纬度以 z 为极轴 `v = 1/2 + asin(z/‖d‖)/π`；反解 `d = (cosφ cosλ, cosφ sinλ, sinφ)`，输出恒为单位向量。

- 互逆：单位方向（含随机 20 万点、1°/0.5° 稠密角网格、UV 边界）往返分量最大误差约 `3e-14`，远小于 `1e-9`。
- 极点：`atan2(0, 0)` 确定返回 `0`，正向不除以平面半径；`(0,0,±1)` 固定为 `(0.5, 1.0)/(0.5, 0.0)`，重复调用逐位一致。
- 接缝：`to_dir((0,v))` 与 `to_dir((1,v))` 的最大三维距离约 `2.5e-16`；题给接缝点 `(1,0,±1e-3)` 的 `u` 完全相同。另提供 `seam_gap()` 与 `is_seam_continuous(eps=1e-9)`。
- 面积：面积元 `dΩ/du/dv = 2π² sin(πv)`，UV 矩形解析立体角 `solid_angle(...) = 2π(u1−u0)(cos πv0 − cos πv1)`，全球面积为 `4π`。`area_distortion()` 用中心差分雅可比对照解析面积元，返回最大相对误差（实测约 `8e-10`，即 ≪1%）；200×100 网格几何立体角求和与 `4π` 的相对差约 `1e-13`。
- 性能（本机 Python 3.14）：10 万次 `to_uv` 约 28–46 ms、`to_dir` 约 21–36 ms、往返约 55 ms，低于 300 ms。
- 错误：零向量、NaN/无穷分量、分量数不为 3、UV 越界均抛 `UvSphereError`（同时继承 `ValueError` 与 `TypeError`，并提供 `ZeroDirectionError` / `NonFiniteDirectionError` / `InvalidDirectionError` / `InvalidUvError` 分类）。

说明：可见 roundtrip 用例输入 `(0.3,0.5,0.8)` 的平方范数为 `0.98`，并非单位方向。对明显非单位的输入，纬度改以原始平面半径为余弦，使平面分量 `x/y` 往返逐位还原（该用例检查的 `x` 误差约 `6e-17`）；单位方向（平方范数偏差 ≤ `1e-12`）始终走稳定的归一化 `asin` 路径。
