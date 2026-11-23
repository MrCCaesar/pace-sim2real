# Issue #22 · 正式验收结果

**结论：未通过。** 2026-11-23 按用户授权进入 Verify，对照[已批准的 A1–A8](spec.md)复核。A1–A6 通过，A7、A8 失败。X5 机器人配置中的 `replace(actuators=…)` 存在一条遗漏的引用路径。两个独立反例都应退出 1，实际均退出 0。

**受验版本。** PACE 工作树基于 `122e21716516b0475e0c2e54594936a9ac206b7f`，包含 Implement 尚未提交的改动；Isaac Lab 为 `ae63302486bb92fc865f1fd8449b91a53728184c`。反例在临时项目或当前 PACE 源码的临时副本中运行。验收只增加核查材料和阶段记录，生产代码保持实施交付状态。

## 逐项判定

| 条件 | 判定 | 本轮观测 |
| --- | --- | --- |
| A1 任务及变体布局 | 通过 | 当前四个任务通过。直接式单/多智能体环境移回旧层级均报 ORG001。另将注册的 X5 定义移回旧路径，保留 config 目录及注册文件，ORG001 指出实际旧文件与期望目录。 |
| A2 Manager 与地形 | 通过 | Manager 间接子类在扩展包合法，移入任务外的错误模块报 ORG003。地形函数、官方平面和有状态奖励共存时退出 0；把地形函数移入任务并从原模块重导出，报 ORG002，诊断指向原始定义。 |
| A3 MDP 按需分文件及溯源 | 通过 | 自定义有状态奖励和官方事件共存，项目没有 events.py，退出 0。通过字符串和两层导出引用移入环境配置的奖励时，ORG004 指出绑定及定义两处位置。另有别名、存根和星号导出用例通过。 |
| A4 奖励绑定不可解析 | 通过 | 奖励改为 `resolve_at_runtime()` 后退出 1，ORG005 报 env_cfg.py 第 6 行第 17 列，并指明运行时工厂。消费项目仅删除被引用的奖励模块后 hook 也失败。 |
| A5 跨项目 pre-commit | 通过 | 专项测试用不同包名的消费项目从临时 Git 提供方固定 SHA 调用真实 hook，依次观测到正确布局退出 0、错放奖励报 ORG004、仅暂存删除目标文件报 ORG005。提供方 fixture 只包含 hook 和标准库检查器，未安装 PACE 到消费项目。 |
| A6 全库与迁移兼容 | 通过 | Ruff、适用 hooks 和现有回归均通过。独立 wheel 环境加载四个 Gym 任务、注册的模板 agent、公共包和本地机器人 USD；工作区的完整记录与迁移前 JSON 快照逐字节一致。 |
| A7 全环境组件链及共享 | **失败** | 合法的 X5、X3mini 共享执行器以及直接式单/多智能体正例通过；将真实 X5 配置的嵌套执行器绑定换成缺失工厂后仍退出 0。该结果表明对资产配置替换中的执行器引用追踪不完整。 |
| A8 未解析和无规则均失败 | **失败** | 简单场景字段的新组件能报 ORG008，缺失注册目标和资源能报 ORG005。X5 的嵌套执行器位置分别注入不可解析工厂与已定义但无归属规则的类，两者均报告三项计数为零。 |

## 可复现的失败

执行 `.venv/bin/python .scratch/issue_22/verify_cases.py`。脚本逐例调用正式 CLI，核对退出码及诊断文本。8 个独立情形中 6 个符合预期，2 个不符合，脚本退出 1。[核查脚本](verify_cases.py) · [逐例输入预期、实际退出码与完整诊断](verification-cases.json)

在 X5 的 `robot = cast(Any, SEVNCE_X5_CFG).replace(...)` 中只改变 `actuators["joints"]` 的值。

| 注入的值 | 预期 | 实际 |
| --- | --- | --- |
| `missing_drive_factory()` | 退出 1，ORG005，定位 X5 的绑定并给出原因 | 退出 0，未产生诊断 |
| `UnclassifiedDrive()`，类在同一模块中明确定义 | 退出 1，ORG008，定位新类及其绑定 | 退出 0，未产生诊断 |

正例和两个反例均输出 `registrations=4 environments=5 components=36 violations=0 unresolved=0 missing_rules=0`。源码中，`composition()` 处理 `.replace()` 时检查接收对象后立即返回；通用调用检查只对可识别的框架 callee 遍历组件关键字。本例的接收对象经 `cast(...)` 包装，关键字里的驱动未获检查。[实际绑定](../../src/pace_sim2real/tasks/pace/config/x5/env_cfg.py#L106) · [组合处理](../../src/isaaclab_task_lint/check.py#L249) · [调用处理](../../src/isaaclab_task_lint/check.py#L474)

## 正式运行记录

本轮临时输出目录为 `/tmp/pace22-verify.G7Eand`（下表记作 `$v`）。在启动回归前检查了内存和显存，当时可用内存约 21 GiB、可用显存 23304 MiB。配置加载没有创建 Isaac Lab 仿真实例。

| 命令 | 退出码与结果 |
| --- | --- |
| `.venv/bin/isaaclab-task-lint`；`.venv/bin/ruff check .`；`git diff --check` | 均为 0。生产工作树的结构计数见上文。 |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_task_organization.py --junitxml=$v/structure.xml` | 0，19 通过，含真实固定修订 hook 测试。 |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OMP_NUM_THREADS=2 .venv/bin/python -m pytest -q` | 0，235 通过，9 跳过，39 个依赖警告。跳过项为 1 个缺少本地 CSV 的样例及 8 个显式启用的回放集成用例。 |
| `.venv/bin/pre-commit run --all-files` | 0，22 项通过；符号链接检查无适用文件。用临时索引和临时对象目录执行 `git read-tree HEAD`、`git add -A`，包含新增、移动及已有文件；保留原 Git 暂存区。 |
| `uv build --offline --wheel --out-dir "$v/dist"`；`uv venv --python .venv/bin/python "$v/wheel-env"`；`uv pip install --offline --no-deps --python "$v/wheel-env/bin/python" "$v"/dist/*.whl` | 均为 0。向独立环境添加项目现有 Isaac Lab 运行依赖所在 site-packages，并断言 PACE、扩展包和检查器均从 wheel 环境加载。 |
| `VIRTUAL_ENV="$v/wheel-env" OMP_NUM_THREADS=2 "$v/wheel-env/bin/python" "$v/wheel-check.py" "$PWD"` | 0。成功发现任务入口，加载四个环境配置与模板 agent；核对公开导出、dt、decimation、边界和资产；wheel 中的检查器也成功运行。 |
| `OMP_NUM_THREADS=2 .venv/bin/python /tmp/pace22-snapshot.py > "$v/snapshot.log"`；`tail -1 "$v/snapshot.log" \| cmp - .scratch/issue_22/config-baseline.json` | 均为 0。公开导出、任务项、时步、驱动增益、拟合边界、分组、时间模式及资产路径均与[迁移前基线](config-baseline.json)一致。 |

**后续处理。** 建议回到 Implement，补齐资产配置替换操作中组件参数的递归检查，并将两个真实 X5 反例纳入持久回归。复验时应先看到两个反例分别报 ORG005、ORG008，再检查合法共享资产、其他 A 项和全库结果。本次验收结论保留为未通过。
