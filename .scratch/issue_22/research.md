# Issue #22 · Isaac Lab 任务组织 lint 可行性研究

**Specify 范围补充。** 固定版本的环境配置还引用 scene、sim、录像、UI、设备与其他组件，直接式环境还声明动作/观察空间与噪声模型。框架同时提供 DirectMARLEnv。仓库中的 PaceDCMotor 和 PaceDCMotorCfg 分别继承官方执行器和配置类，现位于 utils/，为原先三个示例之外的真实迁移案例。参见 [环境配置](https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab/isaaclab/envs/manager_based_env_cfg.py)、[直接式配置](https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab/isaaclab/envs/direct_rl_env_cfg.py)、[执行器实现](https://github.com/MrCCaesar/pace-sim2real/blob/122e21716516b0475e0c2e54594936a9ac206b7f/src/pace_sim2real/utils/pace_actuator.py)和[配置](https://github.com/MrCCaesar/pace-sim2real/blob/122e21716516b0475e0c2e54594936a9ac206b7f/src/pace_sim2real/utils/pace_actuator_cfg.py)。

状态：Draft（Research）。本文记录证据和候选思路，规则接口、覆盖策略和迁移方案待 Specify 决定。

## 已确认事实：上游源码

核对基线为本机 `../IsaacLab`，版本文件为 3.0.0，Git 提交为 `ae63302486bb92fc865f1fd8449b91a53728184c`。下列链接均固定至该提交。R7 的扩展包命名来自用户确认。[VERSION][version]

| 研究对象 | 上游实际行为 | 对 R5–R9 的意义 |
| --- | --- | --- |
| 任务家族 | `isaaclab_tasks` 有 `core/`、`contrib/`、`benchmark/` 等目录。运动控制样例 `core/velocity/` 将共享配置置于 `velocity_env_cfg.py`，任务 MDP 在 `mdp/`，机器人变体在 `config/<robot>/`。[任务根][tasks]、[velocity 家族][velocity] | 可将同类任务的共享配置、机器人变体和 MDP 职责对应到本项目。用户已选外部模板作为本项目的目录层级基准。 |
| 任务内按需设立模块 | velocity 配置声明了多个事件，并经 `mdp` 使用框架事件。该任务的 MDP 有 `rewards.py`、`curriculums.py`、`terminations.py` 等，但无 `events.py`。lift 有自己的事件，独立设有 `events.py`。handover 使用 `mdp/commands.py` 和 `commands_cfg.py`，lift 用 `mdp/commands/` 子包。[velocity 配置][velcfg]、[velocity MDP][velmdp]、[lift MDP][liftmdp]、[handover MDP][handover] | 按本地实际定义触发相应职责检查。仅声明事件配置无需增设事件模块。命令模块至少存在两种上游布局。 |
| 绑定与实际定义 | lift 将 `RewardTermCfg` 重命名为 `RewTerm`。其 `func=mdp.object_ee_distance` 最终在任务的奖励文件找到函数定义，同文件还定义有状态奖励类 `success_reward(ManagerTermBase)` 及间接派生的奖励类。事件也可用字面量 `module:symbol` 指定。velocity 的 `mdp/__init__.pyi` 同时显式导出本地定义并从 `isaaclab.envs.mdp` 星号导入。上游 `lazy_export()` 读取存根确定导出。[lift 配置][liftcfg]、[奖励实现][liftrew]、[velocity 导出][velstub]、[lazy_export 源码][lazy] | `mdp.foo` 的前缀不足以判定归属。检查须追到原始定义，区分配置引用、项目实现和官方复用；仅有空的合规文件或在其中重新导出错放的定义，都不足以满足 R5。 |
| Manager 与 Manager term | `ManagerBase` 和 `ManagerTermBase` 是两个独立基类。`RewardManager` 继承前者，管理并调用奖励项。`CommandTerm` 继承后者，lift 在任务 MDP 中实现其子类。奖励、观察、事件、终止和课程等配置使用 `func`；动作、命令、记录项配置使用 `class_type`。lift 命令配置还有字面量 `{DIR}.pose_commands:ObjectUniformPoseCommand`。[基类][base]、[奖励管理器][rewardmgr]、[命令管理器和项][commandmgr]、[配置类型][termcfg]、[任务命令配置][cmdcfg] | 项目级自定义 Manager 的识别依据可从 Manager 继承链取得。任务 MDP 项的分类可结合配置绑定。只搜索名称含 Manager 的类或只读 `func` 会混淆职责或漏检。 |
| 地形 | 框架的 `terrains/` 下有生成器、导入器及各自配置，另含 `height_field/`、`trimesh/` 和 `config/`。子地形配置的 `function` 绑定生成函数，网格地形用 `{DIR}.mesh_terrains:flat_terrain` 等字面量；`config/rough.py` 组合已有子地形。velocity 在场景中实例化官方 `TerrainImporterCfg`。[地形目录][terrains]、[子地形契约][subcfg]、[网格地形配置][meshcfg]、[预设][rough]、[velocity 配置][velcfg] | 能分别定位生成实现、类型定义和已有类型的场景使用。单独出现 Terrain 配置调用不能证明项目定义了新地形。组合预设是否属于项目级扩展，应在 Specify 界定。 |
| 外部项目模板 | 官方生成器构造 `src/<name>/tasks/<family>/config/<robot>/`，外部环境配置默认文件名为 `env_cfg`，还建立 `src/<name>/assets/`。直接式任务模板在环境类中提供 `_get_rewards`。[外部生成器][generator]、[模板][template] | 同版本同时提供上游任务包与外部脚手架两种组织参考。R7 要求的 `pace_sim2real_isaaclabs` 是本项目约束。直接式环境方法与 manager-based 奖励项使用不同入口，检查前须界定适用对象。 |

## 假设、风险和建议：上游证据可支持的静态判定

- 可行性假设：在源码可读时，显式导入、模块别名、配置类型、普通继承以及可解析的字符串引用可形成“配置项 → 导出 → 定义”的证据链。仅依靠文件名的规则无法检测环境配置中定义奖励、随后由合规模块导出的情形。尚未用实验验证覆盖率。
- 误报边界：奖励函数调用的普通数学辅助函数未必也是奖励项。官方奖励文件存在私有辅助函数；单靠参数签名、类名后缀或调用栈扩展不足以判定。建议验收样例成对覆盖同名引用来自框架与来自本项目的情况。
- 未决问题：动态工厂、运行时替换、第三方插件或由多个类别共用的实现应如何处理；各类 MDP 项支持哪些上游布局；直接式环境是否纳入同一套组织检查。需区分“已证实错放”与“无法静态定位”，避免把覆盖缺口计为通过。
- 核对方式：阅读固定提交下的源码、存根、生成器与模板；未运行模板、导入 Isaac Lab、启动仿真或执行 lint 实验。

[version]: https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/VERSION
[tasks]: https://github.com/isaac-sim/IsaacLab/tree/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab_tasks/isaaclab_tasks
[velocity]: https://github.com/isaac-sim/IsaacLab/tree/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab_tasks/isaaclab_tasks/core/velocity
[velcfg]: https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab_tasks/isaaclab_tasks/core/velocity/velocity_env_cfg.py
[velmdp]: https://github.com/isaac-sim/IsaacLab/tree/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab_tasks/isaaclab_tasks/core/velocity/mdp
[liftmdp]: https://github.com/isaac-sim/IsaacLab/tree/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab_tasks/isaaclab_tasks/core/lift/mdp
[handover]: https://github.com/isaac-sim/IsaacLab/tree/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab_tasks/isaaclab_tasks/core/handover/mdp
[liftcfg]: https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab_tasks/isaaclab_tasks/core/lift/lift_env_cfg.py
[liftrew]: https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab_tasks/isaaclab_tasks/core/lift/mdp/rewards.py
[velstub]: https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab_tasks/isaaclab_tasks/core/velocity/mdp/__init__.pyi
[lazy]: https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab/isaaclab/utils/module.py#L84-L110
[base]: https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab/isaaclab/managers/manager_base.py
[rewardmgr]: https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab/isaaclab/managers/reward_manager.py
[commandmgr]: https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab/isaaclab/managers/command_manager.py
[termcfg]: https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab/isaaclab/managers/manager_term_cfg.py
[cmdcfg]: https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab_tasks/isaaclab_tasks/core/lift/mdp/commands/pose_commands_cfg.py
[terrains]: https://github.com/isaac-sim/IsaacLab/tree/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab/isaaclab/terrains
[subcfg]: https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab/isaaclab/terrains/sub_terrain_cfg.py
[meshcfg]: https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab/isaaclab/terrains/trimesh/mesh_terrains_cfg.py
[rough]: https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/source/isaaclab/isaaclab/terrains/config/rough.py
[generator]: https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/tools/template/generator.py
[template]: https://github.com/isaac-sim/IsaacLab/blob/ae63302486bb92fc865f1fd8449b91a53728184c/tools/template/templates/tasks/cartpole.jinja

## 仓库现状与迁移影响（Confirmed）

| 对象 | 核查结果与影响 |
| --- | --- |
| 任务发现和公共接口 | 当前入口是 `pace_sim2real.tasks`；包发现会跳过 `.mdp`。三个机器人任务用相对模块名注册，模板任务另有环境及 agent 配置入口。顶层包还直接导出环境配置类。目录迁移会影响这些导入路径；后续验收应覆盖已注册 Gym ID、各配置入口和原公共导入的兼容要求。[打包与发现入口](../../pyproject.toml#L27) · [机器人注册](https://github.com/MrCCaesar/pace-sim2real/blob/122e21716516b0475e0c2e54594936a9ac206b7f/src/pace_sim2real/tasks/manager_based/__init__.py) · [模板任务](https://github.com/MrCCaesar/pace-sim2real/blob/122e21716516b0475e0c2e54594936a9ac206b7f/src/pace_sim2real/tasks/manager_based/pace/__init__.py) · [公共接口](../../src/pace_sim2real/__init__.py) |
| 现有 MDP | PACE 已有自定义奖励函数；`mdp/__init__.py` 同时重导出官方函数和本地奖励。环境配置以 `RewTerm` 等别名引用其中的函数。应分别识别定义、引用和重导出；引用了 `mdp.X` 并不能证明 X 是当前任务自定义的。[奖励定义](https://github.com/MrCCaesar/pace-sim2real/blob/122e21716516b0475e0c2e54594936a9ac206b7f/src/pace_sim2real/tasks/manager_based/pace/mdp/rewards.py) · [重导出](https://github.com/MrCCaesar/pace-sim2real/blob/122e21716516b0475e0c2e54594936a9ac206b7f/src/pace_sim2real/tasks/manager_based/pace/mdp/__init__.py) · [配置](https://github.com/MrCCaesar/pace-sim2real/blob/122e21716516b0475e0c2e54594936a9ac206b7f/src/pace_sim2real/tasks/manager_based/pace/pace_sim2real_env_cfg.py#L130) |
| 地形与 Manager | `ground = TerrainImporterCfg(terrain_type="plane", …)` 是官方类型的配置实例。类似地，环境配置里组合 `RewardsCfg` 和 `ObservationsCfg` 并不能证明项目定义了新的 Manager。这些是规则应放行的真实样本。[场景和配置组](https://github.com/MrCCaesar/pace-sim2real/blob/122e21716516b0475e0c2e54594936a9ac206b7f/src/pace_sim2real/tasks/manager_based/pace/pace_sim2real_env_cfg.py#L81) |
| 扩展包发行 | 当前 uv_build 的 `module-name` 只列出 `pace_sim2real`。若以另一个顶层导入包交付扩展，需核实构建产物包含它，并能从已安装环境导入。工作树中存在目录不能证明已打包。[构建配置](../../pyproject.toml#L110) |
| 全库适用检查 | 本次 `git ls-files` 统计有 51 个 .py、2 个 .pyi、10 个 JSON、4 个 TOML、4 个 YAML，以及文档站的 JS/CSS。领域规则作用于 Python 组件及其任务配置；已有 YAML/TOML 解析、拼写等检查按配置适用。是否引入额外的 JS、CSS、文档风格规则需另有需求依据。[开发工具配置](../../pyproject.toml#L55) · [现有 hooks](../../.pre-commit-config.yaml) |

## 工具可行性与取舍（Proposed）

| 方案 | 能力、代价与判断 |
| --- | --- |
| Ruff 加独立 Python 静态检查 | 仓库已配置 Ruff，锁定版本 0.17.2；pre-commit 锁定 4.7.0。Ruff 可继续负责通用 Python 规则，项目检查可用 Python 3.12 标准库解析源码并结合包路径、导入和任务配置判断实现归属。适合跨文件检查，无需为领域检查导入仿真环境。代价是项目要维护有限的名称解析逻辑和反例。推荐作为 Specify 的候选方向。[依赖锁](../../uv.lock) · [Ruff 插件边界](https://docs.astral.sh/ruff/faq/#can-i-write-my-own-linter-plugins-for-ruff) · [Python AST](https://docs.python.org/3.12/library/ast.html) |
| Flake8 自定义插件 | 官方接口可提供文件名和 AST，适合诊断单文件内确定的违规；跨模块的定义、注册和重导出仍需额外索引。现有 Flake8 由 pre-commit 独立环境提供；将插件交付给 agent 需维护插件发现及两套环境的一致性。[Flake8 插件输入](https://flake8.pycqa.org/en/latest/plugin-development/plugin-parameters.html) · [现有 hook](../../.pre-commit-config.yaml#L12) |
| 仅用目录或文本匹配 | 可发现固定路径和拼写，但同一 `mdp` 命名空间同时包含本地与上游定义；仅用文件名无法抓到“已有 rewards.py，奖励实现却写在环境配置里”。可用于简单路径规则，单独使用无法满足 R5、R6。[本地重导出](https://github.com/MrCCaesar/pace-sim2real/blob/122e21716516b0475e0c2e54594936a9ac206b7f/src/pace_sim2real/tasks/manager_based/pace/mdp/__init__.py) |
| pre-commit 作为执行入口 | 支持本地 hook 和全库模式。即使某次只更改组件定义、删除模块或修改重导出，也可能使其他任务违规。跨文件规则需要看完整的相关源码，最终验收需从全库运行所有适用检查。[pre-commit 文档](https://pre-commit.com/#pre-commit-run) |

**现有工具的协调成本。** pre-commit 中有 Black、isort、Flake8、pyupgrade；Ruff 同时配置了导入排序等规则。应在 Specify 明确各工具负责哪些检查，再衡量存量清理量。.flake8 忽略 E501，Ruff 开启 E 系列，两者对行长度的检查已有差异。许可证 hook 引用当前仓库缺少的模板，历史验证曾跳过；codespell 对 HAA 的历史误报已有仓库级配置。全库验收前需核实有效配置及缺失文件，无依据扩大排除范围会掩盖问题。[Flake8 配置](../../.flake8) · [Ruff 和拼写配置](../../pyproject.toml#L113) · [许可证 hook](../../.pre-commit-config.yaml#L62) · [历史记录](../issue_4/verification.md#L179)

## 可靠性边界与建议验收样例（Proposed）

| 场景 | 后续应验证的行为 |
| --- | --- |
| 已有 rewards.py，另在环境配置中定义函数，并将其显式绑定为奖励 | 定位到错误的定义；通过别名或本地重导出引用同一函数时结论一致。 |
| 任务只自定义奖励，事件来自上游；配置文件内声明奖励权重、事件参数或 `__post_init__` | 允许配置，按 R9 无需补空的 events.py。 |
| 自定义 Manager 子类放在任务配置中；另一个任务只使用官方 Manager 或定义有状态的奖励项 | 对确认是 Manager 实现的类验证扩展包及 managers/ 归属。按所属 MDP 类别判断奖励项，避免用类名含 Manager 判定。 |
| 自定义地形生成函数由可追踪的地形配置指向；环境仅实例化官方平面地形 | 前者检查扩展包和 terrains/，后者允许放在场景配置。单凭函数名或数组返回值无法可靠区分普通几何辅助函数。 |
| 工厂动态返回 callable、运行时修改绑定、同一符号经多次不透明转发 | 仅靠语法树不足以证明最终对象。建议把“无法判定”单列并指出位置，待 Specify 确定是否阻断及处理方式；不能把未解析项统计成已验证。 |

以上为读源码得出的可行性判断，尚未通过原型测量误报率或覆盖率。[项目配置样本](https://github.com/MrCCaesar/pace-sim2real/blob/122e21716516b0475e0c2e54594936a9ac206b7f/src/pace_sim2real/tasks/manager_based/pace/pace_sim2real_env_cfg.py) · [Python AST 表达范围](https://docs.python.org/3.12/library/ast.html)

## 研究边界与审批

本轮以 `git -C ../IsaacLab rev-parse HEAD`、`cat ../IsaacLab/VERSION`、`git ls-files`、`rg` 和源码/官方文档查阅为证据。未运行原型、全库 lint、单元测试或仿真，当前违规总数与打包可用性未经验证。工具组合已批准；具体规则和迁移方案待 Specify；既有配置工作区改动未触碰。

**研究决定（Approved）**　用户确认采用外部模板层级 `src/pace_sim2real/tasks/<任务>/config/`。早先的 `core/pace/` 提案已撤回。用户批准 Ruff 与独立 Python 静态检查的职责分工，并要求便于新项目通过 pre-commit 接入。后续由 agent 评估复用需求。若有依据表明需要独立 GitHub 仓库，agent 应提出理由并申请用户批准后再建仓。[ADR 0020](../../adr/0020-task-organization-lint.md)

**版本复核（Approved）。** 正式标签 v3.0.0 解引用为 `e3f7d9ff1f5d7f8280de3ece9000b7117f66bcf4`。该版和之前核对的开发提交均将家族直接放在 tasks/ 下，beta2 的工作流目录仅作历史对照。用户确认 PACE 和消费项目的目录及检查统一以正式标签为准。[正式版生成器](https://github.com/isaac-sim/IsaacLab/blob/v3.0.0/tools/template/generator.py) · [beta2 生成器](https://github.com/isaac-sim/IsaacLab/blob/v3.0.0-beta2/tools/template/generator.py)
