# Issue #22 · Implement 实施自检

依据：[批准的计划](plan.md)、[规格](spec.md)、[接口](interfaces.md)。此处记录工作树实施结果，供后续正式 Verify 复核。

## T1 与 T6 · 存量基线及迁移

迁移前的项目提交为 `122e21716516b0475e0c2e54594936a9ac206b7f`，包含用户对机器人配置的工作树修改。先读取 Gym 注册和配置，记录控制时步、decimation、边界张量、记录分组、历史时间模式、资产路径、驱动增益与顶层公开导出。迁移后在同一工作树对比序列化快照，[基线内容](config-baseline.json)与迁移后快照的 SHA-256 均为 `f328a471348ed31e0258bb42c65c4476f0aabc61ef30d3f15f05158b17dbeefc`。

| Gym ID | 新任务配置位置（相对 tasks/pace/） | 物理时步 |
| --- | --- | --- |
| Isaac-Pace-Anymal-D-v0 | config/anymal_d/env_cfg.py | 0.0025 s |
| Isaac-Pace-Sevnce-X5-v0 | config/x5/env_cfg.py | 0.0025 s |
| Isaac-Pace-Sevnce-X3mini-v0 | config/x3mini/env_cfg.py | 0.002 s |
| Template-Pace-Sim2real-v0 | config/template/env_cfg.py | 0.0025 s |

X3mini 的轮阻尼 2.0、500 Hz、参考关节与历史时间设置，以及 X5 的有效阻尼上界 6.0，均随源文件迁移。执行器实现和配置迁入 pace_sim2real_isaaclabs/actuators。旧深层模块的仓内调用及用户文档已更新。公共包导出和任务 ID 继续可用。

## T2–T5 · 检查器和 hook

[源码索引](../../src/isaaclab_task_lint/index.py)、[组织规则](../../src/isaaclab_task_lint/check.py)、[资源解析](../../src/isaaclab_task_lint/resources.py)及[命令入口](../../src/isaaclab_task_lint/__main__.py)只使用标准库。框架符号索引由[生成脚本](../../scripts/generate_isaaclab_lint_catalog.py)从固定源码生成，消费项目无需安装框架。使用[外部 hook](../../.pre-commit-hooks.yaml)和[仓内配置](../../.pre-commit-config.yaml)接入。不同包名消费项目通过临时本地 Git 修订验证，覆盖正常调用、错放奖励，以及只有删除被引用文件的暂存提交。未创建远程仓库。

## T6–T7 · 修复与接入

- Ruff 承担 Python lint 与导入排序，取代重复的独立 isort hook；保留 Black、Flake8 和其他适用的已有检查。原许可证插入 hook 缺少模板，在基线运行中失败。改为检查已有 SPDX、许可证声明或仓库 LICENSE/NOTICE 引用，保留各文件原版权归属。为 codespell 排除三个内嵌图像数据的 SVG，修复全库 hook 发现的换行、行尾空白等问题。
- 从 wheel 加载模板训练配置时发现旧 RSL-RL 合并策略类已不在 Isaac Lab 3.0 导出中，已采用固定版本官方外部模板的 actor、critic 配置，保留原网络宽度、激活和 PPO 超参数。检查器能定位旧类的绑定位置。机器人资产模块中 M20 的数据目录引用也已改用实际声明的路径。
- 迁移前 Ruff 有 24 条诊断，原回归为 215 通过、9 跳过、1 失败。既有提交 `242e5a3` 已把 X5 示例扫频上限调为 4 Hz，本轮同步测试和 README。原生 MuJoCo 的隔离断言在新解释器中运行，以排除其他测试已加载 Isaac Lab 对该断言的干扰。
- [开发说明](../../docs/dev/contributing.md)包含开发依赖、全库命令及外部 hook 接入。远程消费需要用户今后发布含该 hook 的实际 Git 修订。

## 实施自检命令

| 命令或检查 | 结果 |
| --- | --- |
| `.venv/bin/isaaclab-task-lint` | 4 个注册、5 个环境/配置定义（含共享基类）、36 个组件；违规、未解析、缺少规则均为 0。 |
| `.venv/bin/ruff check .`、`uv lock --check --offline`、`git diff --check` | 均成功。 |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/test_task_organization.py` | 19 通过，包含全部规则类别、退出码和固定修订消费项目。 |
| `uv build --wheel --offline --out-dir /tmp/pace22-dists` | 构建成功。将 wheel 以 `uv pip install --offline --reinstall --no-deps --python /tmp/pace22-wheel-env/bin/python` 安装到独立环境，复用本机已有 Isaac Lab 运行依赖。确认三个项目包来自该 wheel，加载四个 Gym 配置、模板 agent、扩展包和机器人 USD，运行 wheel 提供的检查器，退出 0。 |
| `.venv/bin/pre-commit run --all-files` | 在临时 Git 索引中纳入新增和已迁移文件；工作区原索引未改动。22 项适用检查通过，符号链接检查因无适用文件跳过。 |

全套回归命令为 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q`，最终 235 通过、9 跳过、39 个依赖警告。跳过项为 1 个缺本地 CSV 的样例和 8 个显式启用的回放集成用例。一次复跑发现数值回归继承了用户默认的可视化设置，查看器退出超时；将测试用合成模型明确设为 headless 后复跑通过，查看器专项用例继续显式启用查看器。

静态分析仅对固定版本可从源码判定的结构给出归属。ORG005/ORG008 均阻断验收。运行证据限于已执行的测试、配置加载和本地消费项目。正式 Verify 需用户单独授权。

## Verify 反馈后的修订

用户授权补齐嵌套绑定、将 X5 的两个反例纳入回归，并再次执行 A1–A8。根据用户随后对版本的确认，PACE 及其他项目使用官方 v3.0.0 正式标签的家族布局。PACE 位于 `src/pace_sim2real/tasks/pace/`，变体位于 `config/<robot>/`。Direct 单智能体和多智能体按生成器的家族后缀检查。离线符号索引从本地 Git 中固定的正式版提交生成。

配置组合递归检查构造及 `replace()` 的组件参数，包括链式替换、映射展开、嵌套映射和 `typing.cast`。可静态判定的关键字映射逐项检查，动态展开报告 ORG005。新增了两项真实 X5 参数化回归及一项链式替换测试。正式标签回归另发现两个 CLI 兼容点，离线工具将配置加载器的提示写到标准错误，正式版启动参数显式接收 visualizer。结果见[复验记录](verification.md)。
