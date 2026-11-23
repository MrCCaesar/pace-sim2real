# Issue #22 · 蒸馏 lint 规则

状态：Approved，用户于 2026-11-23 批准 Explore 草案并授权进入 Research。来源：[Issue #22](https://github.com/MrCCaesar/pace-sim2real/issues/22)，读取时无评论。用户已批准进入 Explore。

## 已确认的需求来源与仓库事实

- R1：从当前项目代码和文档中提炼适用于 Isaac Lab 3.0 机器人运动控制强化学习开发的约束，让 agent 编程时能通过自动检查发现违规。
- R2：根据项目语言构成选择合适的自动化 lint 工具，并将其纳入 agent 的开发依赖。
- R3：遵守 Issue 中的工程边界：模型、仿真配置、测试和文档合理解耦；重要功能有清晰的输入、输出和配置接口；重要架构决策先经用户确认；保持物理问题和功能范围；文档与实现一致。
- 已跟踪文件中有 51 个 Python 源文件、2 个 Python 类型存根和 51 个 Markdown 文件，另有 JSON、TOML、YAML 等。文档是规则来源之一，其是否也属于检查对象待确认。
- pyproject.toml 已声明 Ruff 和 pre-commit 开发依赖，并包含 Ruff 配置。.pre-commit-config.yaml 已配置 Black、Flake8、isort 等。这些是配置事实，实际执行时机与覆盖情况尚未验证。

## 用户确认的首版范围与验收

- R1 的领域范围聚焦 Isaac Lab 3.0 强化学习任务与环境配置。
- R4：交付时全库已有代码均须通过适用的 lint 检查，涵盖未在本次功能开发中修改的代码。
- 用户指定从 .scratch 的文档提取优先错误场景。

## 已撤回的提议（Superseded）

用户明确排除此前提议的初始状态覆盖、动作列错序和时步混用。三项均从首版需求及验收候选中撤回。

## 用户确认的组织规范

- R5：凡强化学习任务包含自定义地形、Manager 或 MDP 项，其文件组织和代码职责划分须与 Isaac Lab 3.0 官方同类组件一致。检查既要覆盖模块位置，也要覆盖实现实际定义的位置；只检查目录或文件存在无法满足此需求。
- R6：项目级自定义地形、Manager 和任务级 MDP 实现须能按职责定位。用户以地形目录及任务内的 mdp/rewards.py、mdp/events.py 为例。自定义奖励定义在环境配置文件中，即使已有 rewards.py，也属于应识别的场景。

- R7：外部项目容纳自定义地形、Manager 等框架扩展的包必须命名为 `<项目名>_isaaclabs`。本项目对应 `pace_sim2real_isaaclabs`，包内按官方同类组件组织，如 `terrains/` 和 `managers/`。
- R8：任务包 `src/pace_sim2real/` 承载各运动控制任务的环境配置与任务 MDP，任务目录层级遵循 Isaac Lab 3.0 官方外部项目模板，以 v3.0.0 正式标签为准，所有项目采用 `src/<项目>/tasks/<任务家族>/config/<robot>/`，本项目采用 `src/pace_sim2real/tasks/pace/config/`，任务自定义 MDP 位于同一任务的 `mdp/`。此次澄清取代此前对齐框架内置任务包根目录的表述。
- R9：任务的 MDP 模块按实际自定义项类别设立。仅定义自定义奖励、事件全部复用官方实现时，只有 `mdp/rewards.py` 即满足奖励和事件两类的组织要求。

- R10：独立结构检查应便于其他外部项目通过 pre-commit 配置和复用。由 agent 评估跨项目复用是否需要独立 GitHub 仓库；确有需要时，agent 须说明必要性，向用户提出建仓申请，获批后方可创建。

- R11（Specify 期间用户澄清，扩展 R5–R6）：所有与 Isaac Lab 自定义环境有关的组件、配置和实现均属于组织检查范围。地形、Manager、MDP 项是示例。目录与代码职责以外部项目模板及同版本官方同类组件为参照。
- R12（用户确认）：适用的绑定无法静态解析时，检查失败，报告绑定位置及具体原因。“全库通过”要求适用绑定的未解析数为零。

## 参考事实与延后决策

本地 Isaac Lab 的框架包下有同级 terrains/ 和 managers/；其 core/lift 任务在 mdp/ 下分别组织 rewards.py 和 events.py。本项目当前使用 src/pace_sim2real/ 包路径，PACE 任务已有 mdp/rewards.py。上述是源码示例，具体适用条件在 Research 核对。

- 建议在 Research 按组件查证官方组织方式与允许的变体，再提出具体 lint 规则。工具、规则实现和迁移方案均待后续阶段。
