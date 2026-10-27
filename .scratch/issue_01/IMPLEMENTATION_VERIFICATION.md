# Issue 01 implementation verification

2026-10-23；仅验证当前工作区，不援引其他分支的 PASS。

- 实现范围：9 个原有 Python 文件中的兼容性迁移，新增 CPU 回归测试；.gitignore 仅放行此测试文件。
- 公共 policy 观测仍为 joint_pos/joint_vel/actions 字典，各项 (1,12)；GPU 对 ANYmal 和调用方提供配置的模板均验证 reset/step、finite 观测。
- dt=.0025、decimation=1、12 关节、61 参数；robot 构造/copy/replace 隔离保留。
- `MPLCONFIGDIR=/tmp/pace-mpl .venv/bin/python -m pytest -q`：9 passed；测试包含两种延迟模式、lag 0/3、逐环境不同 lag、三通道和 encoder bias、非法模式、摩擦数学关系/非法 bounds、配置隔离及训练/回放输入。
- `.venv/bin/ruff check tests/test_isaaclab_compatibility.py`：通过。
- `git diff --check`：通过。
- 全新临时环境 `uv sync --locked --offline`、`uv sync --check --locked --offline`：退出 0。版本 0.2.0、本项目导入路径、本地 Isaac Lab 导入路径、CUDA 可用均断言通过。临时环境已清理。
- 现有 .venv 包含 GPU extras，裸 `uv sync --check --locked --offline` 提示将删除 extras，退出 1；未对现有环境执行该同步，改用上述全新基础环境完成需求验收。
- GPU RTX 4060 Laptop：两个任务环境、num_envs=1/duration=.1 采集、num_envs=2/max_iteration=1 fit、plot、num_envs=1/max_iterations=1 train、checkpoint play --video --video_length=1，均退出 0。
- 对新增数据、config、best_trajectory、mean、TensorBoard、checkpoint、JIT、ONNX 和可解码单帧 MP4 作断言；均通过。产物放在新 TemporaryDirectory，结束后自动清理，不删除运行前已有数据。
- 完整 pre-commit 在隔离源码副本运行，初始化 Black hook 时因无法解析 github.com 退出 3；没有修改工作区，也未将完整 hooks 声称为通过。
- 不宣称完整 TEST_PLAN 所有负向控制已覆盖；未做旧版数值等价、收敛或长期实时性能验收。

复跑 GPU smoke（需已有 Isaac Sim/PhysX/RSL-RL extras 和可见 GPU）：

```bash
.venv/bin/python .scratch/issue_01/implementation_evidence/run_smoke.py
```

harness 在临时目录复制当前脚本并明确使用当前 src，使用 Agg 绘图，仅短时参数覆盖；断言失败返回非零。原始日志保存在 implementation_evidence/*.log（仓库默认忽略日志）。CPU 回归位于 tests/test_isaaclab_compatibility.py。
