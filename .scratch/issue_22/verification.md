# Issue #22 · A1–A8 正式复验

**复验通过，8 项全部满足。** 本轮按用户授权回到 Implement 修复，再按[验收条件](spec.md)逐项复核。[首轮验收](verification-initial.md)保留 A7、A8 两个漏检的原始记录。[本轮逐例输出](reverification-cases.json)可与[首轮输出](verification-cases.json)直接比较。

## 目录与版本依据

用户确认 PACE 和消费项目统一采用 Isaac Lab 正式标签 `v3.0.0`，对应提交 `e3f7d9ff1f5d7f8280de3ece9000b7117f66bcf4`。生成器在 `src/<project>/tasks/` 下直接创建任务家族，变体放在 `config/<robot>/`。本仓库的家族为 `pace/`。验证中分别调用正式标签的生成器生成 manager-based、direct 单智能体和 direct 多智能体任务，所得家族为 `walk/`、`walk_direct/` 和 `walk_marl_direct/`。[官方生成器](https://github.com/isaac-sim/IsaacLab/blob/v3.0.0/tools/template/generator.py#L125) · [PACE 家族](../../src/pace_sim2real/tasks/pace/)

## 逐项结果

| 编号 | 判定 | 观测结果 |
| --- | --- | --- |
| A1 任务与变体 | 通过 | 正式模板三个工作流通过。两种 Direct 环境移入旧工作流目录或缺少正式版后缀时触发 ORG001。X5 保留 config 目录和注册文件，仅把注册目标移入旧路径，同样报 ORG001 并指出文件。 |
| A2 Manager 与地形 | 通过 | 间接继承的 Manager 在合法目录通过，错放时报 ORG003。官方平面与自定义地形生成函数可以共存。将函数移入任务后从原模块重导出，ORG002 定位其实际定义。 |
| A3 MDP 归属 | 通过 | 仅含自定义有状态奖励并复用官方事件的项目通过。把奖励移入 env_cfg，经字符串及两层导出绑定后，ORG004 同时给出绑定和实际定义位置。别名、存根和星号导出专项测试通过。 |
| A4 不可解析的奖励 | 通过 | 运行时工厂报 ORG005，退出 1，给出 env_cfg.py 第 6 行第 17 列及原因。删除被引用奖励的消费项目也失败。 |
| A5 跨项目 pre-commit | 通过 | 异名消费项目在隔离的 Git 修订上运行真实 hook。合法任务退出 0，错放奖励退出 1 并报 ORG004，只暂存删除被引用的文件时退出 1 并报 ORG005。 |
| A6 全库与兼容 | 通过 | Ruff、结构检查和适用 hooks 通过。正式版框架源码下全套回归 238 通过、9 跳过。独立 wheel 加载四个 Gym 配置与模板 agent，公开导出、机器人资源和参数检查通过。工作树的完整配置快照与迁移前逐字节一致。 |
| A7 组件链及共享 | 通过 | X5 和 X3mini 共享执行器的正例通过。将真实 X5 资产替换中的 actuators 字典值改为缺失工厂后，检查沿 cast、replace 和字典定位到叶节点，退出 1。链式替换、可解析的关键字映射、直接式单/多智能体生命周期及框架扩展的专项测试通过。 |
| A8 缺规则与未解析 | 通过 | 缺失工厂在 X5 临时副本的 env_cfg.py:109:30 报 ORG005，计数 unresolved=1。替换为可解析的 UnclassifiedDrive 后在 env_cfg.py:112:30 报 ORG008，给出类定义行及 missing_rules=1。两例均有且仅有对应类别的诊断，退出 1。缺失注册入口、资源和动态展开也触发 ORG005。 |

## 运行与复现

资源预检时可用内存约 20 GiB，可用显存 23214 MiB。正式版源码解包在临时目录，沿用本机已安装的 Python 运行依赖；这次验证覆盖任务发现、配置加载和现有回归。1 个用例因本地缺少 CSV 跳过，8 个显式启用的回放集成用例跳过。

| 命令 | 退出码与证据 |
| --- | --- |
| `.venv/bin/python scripts/generate_isaaclab_lint_catalog.py ../IsaacLab` | 0。从正式版 Git 对象重建的 JSON 与直接从同一标签源码生成的索引完全相同。 |
| `.venv/bin/python .scratch/issue_22/verify_cases.py` | 0。8 个独立正反例逐项匹配预期。正式 CLI 的[完整输出](reverification-cases.json)包括各负例的退出码、行列及原因。 |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_task_organization.py` | 0，22 通过。包含两项独立的 X5 真实源码回归。 |
| `.venv/bin/isaaclab-task-lint` | 0。4 个注册、5 个环境或配置定义、36 个组件，violations=0、unresolved=0、missing_rules=0。 |
| `.venv/bin/isaaclab-task-lint --root "$sample"` | 0。正式生成器的 Cartpole、Stubbed 内容与三种工作流均通过。含 AMP 的两组分别发现 3/6/25、3/6/20 个注册、环境及组件。 |
| `.venv/bin/ruff check .`、`uv lock --check --offline`、`git diff --check` | 均为 0。 |
| `.venv/bin/pre-commit run --all-files` | 0。临时 Git 索引纳入全部新增、迁移和既有文件。22 项通过，1 项因没有适用的符号链接跳过。 |
| `PYTHONPATH="$releasepath" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OMP_NUM_THREADS=2 .venv/bin/python -m pytest -q` | 0，238 通过、9 跳过、39 项警告。releasepath 由正式标签的 source/isaaclab* 各包根目录组成。 |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OMP_NUM_THREADS=2 .venv/bin/python -m pytest -q` | 0，在仓库现有开发环境再次执行，238 通过、9 跳过、39 项警告。 |
| `uv build --offline --wheel --out-dir "$v/final-dist"`、`uv pip install --offline --reinstall --no-deps --python "$v/wheel-env/bin/python" "$v"/final-dist/*.whl` | 0。wheel 安装到独立虚拟环境，使用正式版框架源码和已有运行依赖，核实三个项目包均从 wheel 加载。 |
| `PYTHONPATH="$releasepath" OMP_NUM_THREADS=2 .venv/bin/python /tmp/pace22-snapshot.py` | 0。对输出的末行执行 cmp，与 [config-baseline.json](config-baseline.json) 相同。四个任务的 dt、decimation、边界、关节分组、采样方式及执行器增益保持一致。 |

本轮临时目录为 `/tmp/pace22-reverify.MqXoVz`。正式版首次全量运行暴露了 7 个离线报告输出测试和 1 个运行参数测试的兼容问题。将上游配置加载提示转发到 stderr，并为正式版注册已有的 visualizer 启动选项后，相关 50 个测试通过，再复跑全套。以上结果使用正式标签的源码与仓库既有第三方依赖，未执行全规模仿真训练。
