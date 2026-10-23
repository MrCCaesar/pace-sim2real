# Issue #1 兼容性测试计划

## 来源、范围与已确认决策

- 需求来源：`.scratch/issue_01/REQUIREMENTS.md`。
- 覆盖范围：`REQ-I01` 至 `REQ-I08`；本 Issue 不新增安装文档、教程或截图测试。
- 验收后端：Isaac Sim + PhysX。Newton 和 OV PhysX 不属于本计划验收前提。
- 数值边界：不比较旧 Isaac Lab 版本的动力学输出，不设置 CMA-ES score、策略 reward、收敛精度或性能时长阈值。
- 警告边界：deprecation warning 不构成失败；非零退出、未捕获异常、断言失败或功能缺失构成失败。
- 已确认的 I05 Oracle：保留当前 `PaceDCMotor` 的编码器坐标语义，即基础 DC motor 接收 `joint_pos - encoder_bias`，速度为原始 `joint_vel`。
- 已确认的 I07 注入方式：测试包装器在调用当前 `scripts/pace/fit.py` 前 monkeypatch `parse_env_cfg`，将 `env_cfg.sim2real.cmaes.max_iteration` 设置为 `1`；不修改脚本业务代码。
- 测试超时：不设置任何“运行时长”验收阈值。CI 的外部看门狗只用于防止进程永久挂起；触发时报告基础设施错误，不作为性能或收敛失败。

## 通用测试设施

### 隔离环境

- 安装测试使用全新的临时 Uv 环境：

  ```bash
  PACE_UV_ENV="$(mktemp -d)/venv"
  UV_PROJECT_ENVIRONMENT="$PACE_UV_ENV" uv sync --locked
  ```

  不删除、不覆盖项目已有的 `.venv`。
- GPU 验收命令统一在能够访问 NVIDIA 驱动的主机终端执行。当前 Codex 进程看不到 GPU 时，I04–I08 必须报告为“未执行”，不能报告为通过或跳过成功。
- PACE 数据采集和 fit 测试设置 `PACE_ROOT` 到临时目录，避免写入仓库中的既有 `data/` 和 `logs/`。
- 绘图脚本的根目录由脚本自身位置决定。测试将 `scripts/pace/plot_trajectory.py` 原样复制到临时根的对应目录后执行，使其读取同一临时根下的日志。
- RSL-RL 测试以空临时目录作为工作目录，使相对路径 `logs/rsl_rl/...` 完全落在临时根内。
- 所有绘图测试设置 `MPLBACKEND=Agg`，不修改脚本自身的 `plt.show()` 逻辑。

### 产物清理

- 每个测试在启动前记录目标输出根的目录树和文件指纹，结束后只删除本次新增路径。
- 临时根目录由 `mktemp -d` 创建，清理时必须先断言其绝对路径位于测试临时根下，再删除该临时根。
- 不执行宽泛的 `rm -rf data logs`，不删除运行前已存在的文件。
- I06 的 `chirp_data.pt` 在同一 smoke 流程中保留到 I07 完成后，再随临时根清理。

### 结果判定

- 单元测试标记为 `unit` 和 `kitless`，不得启动 Kit 或依赖 GPU。
- 环境和脚本测试标记为 `integration` 或 `smoke`，并在独立子进程中启动 Isaac Sim。
- 每个测试的 Oracle 必须由需求值、公开 API、包元数据、文件格式或明确的数学关系产生，不能用被测实现的同一输出反向作为期望值。
- Negative control 应在相同的断言路径上被识别为失败；不能只验证一个无关的异常。

## 测试覆盖矩阵

| Requirement | Test IDs | 覆盖重点 | 执行层 |
| --- | --- | --- | --- |
| REQ-I01 | I01-T01, I01-T02 | Uv 环境、Isaac Lab 本地 editable source、Python/GPU/平台 | 安装 + 环境 |
| REQ-I02 | I02-T01, I02-T02 | lock、包元数据、依赖、模块导入位置 | 安装 + 单元 |
| REQ-I03 | I03-T01, I03-T02, I03-T03 | 公共 API、registry、entry point、模板语义 | 单元 + integration |
| REQ-I04 | I04-T01, I04-T02, I04-T03 | ANYmal 配置、61 参数、reset/step、有限值 | 单元 + GPU integration |
| REQ-I05 | I05-T01 至 I05-T07 | 配置、延迟模式、零/非零延迟、bias、摩擦比例 | kitless unit |
| REQ-I06 | I06-T01, I06-T02 | 数据采集命令、文件、shape、有限值 | GPU smoke |
| REQ-I07 | I07-T01 至 I07-T03 | CMA-ES fit、checkpoint、绘图读取 | GPU smoke |
| REQ-I08 | I08-T01 至 I08-T03 | PPO 配置、训练、checkpoint、1 步回放 | 单元 + GPU smoke |

## 测试用例

### I01-T01：全新 Uv 环境解析到当前 Isaac Lab checkout

**对应 Requirement ID**：`REQ-I01`

**初始条件**：

- 操作系统为 Ubuntu 24.04。
- 项目 Python 版本满足 `>=3.12,<3.13`。
- `../IsaacLab` 存在，并以 `../IsaacLab/source/isaaclab` 作为 editable source。
- 使用全新的临时 `UV_PROJECT_ENVIRONMENT`。

**输入/触发条件**：

- 在项目根目录执行 `uv sync --locked`。
- 在同一个 Uv 环境中执行 `uv pip show isaaclab`。
- 执行 `import isaaclab` 并读取其模块位置和 `direct_url.json` 中的 editable source。

**可观察行为**：

- Uv 在临时项目环境内完成同步。
- `isaaclab` 包是 editable 安装。
- 包位置和源码位置指向当前 `~/IsaacLab/source/isaaclab`，不是 PyPI wheel、站点包副本或其他 checkout。

**验收标准**：

- `uv sync --locked` 退出码为 0。
- Python 版本满足项目声明。
- `uv pip show isaaclab` 的 editable project location 为当前 checkout 的 `source/isaaclab`。
- `import isaaclab` 成功。

**Oracle**：

- `importlib.metadata.distribution("isaaclab").read_text("direct_url.json")` 的 editable 路径。
- `pyproject.toml` 中 `[tool.uv.sources]` 的本地 source 映射。
- 需求确认的 `../IsaacLab` 路径。

**Negative control**：

- 在未加载项目 Uv 环境的基础 Python 中执行同一来源断言，预期无法证明是项目内 editable 安装。
- 或在临时复制的 `pyproject.toml` 中删除 `isaaclab` 的本地 source 映射，预期来源断言失败。

### I01-T02：验收终端 GPU、Python 和平台声明

**对应 Requirement ID**：`REQ-I01`

**初始条件**：

- I01-T01 使用的 Uv 环境。
- 验收终端能够访问 NVIDIA 驱动。

**输入/触发条件**：

- 在项目环境中执行 `torch.cuda.is_available()`、`torch.cuda.device_count()` 并读取当前 Python 版本。
- 用 TOML 解析器读取 `pyproject.toml` 的 `[tool.uv].environments`。

**可观察行为**：

- PyTorch 能看到至少一个 CUDA 设备。
- Python 版本处于允许区间。
- Uv 平台声明仍完整保留三个已确认平台。

**验收标准**：

- `torch.cuda.is_available()` 为 `True`。
- `torch.cuda.device_count() > 0`。
- Python 版本满足 `>=3.12,<3.13`。
- 平台表达式与以下集合一致：
  - `sys_platform == 'linux' and platform_machine == 'x86_64'`
  - `sys_platform == 'linux' and platform_machine == 'aarch64'`
  - `sys_platform == 'win32' and platform_machine == 'AMD64'`

**Oracle**：

- PyTorch CUDA 运行时查询。
- `pyproject.toml` 的规范化 TOML 结构和需求中的平台集合。

**Negative control**：

- 子进程设置 `CUDA_VISIBLE_DEVICES=""` 后，现有 CUDA 断言必须失败。
- 在临时 TOML 副本中移除 aarch64 平台，平台集合比较必须失败。

### I02-T01：锁定安装、版本和必需依赖

**对应 Requirement ID**：`REQ-I02`

**初始条件**：

- 全新临时 Uv 环境。
- 项目根目录存在 `pyproject.toml` 和 `uv.lock`。
- `../IsaacLab` 路径存在。

**输入/触发条件**：

- 执行 `uv sync --locked` 和 `uv sync --check --locked`。
- 执行 `uv pip show pace-sim2real`。
- 从 `importlib.metadata` 读取发行包版本和 `Requires-Dist`。

**可观察行为**：

- 锁定同步成功，增量检查确认环境与锁文件一致。
- 安装版本为 `0.2.0`。
- 运行依赖包含 `isaaclab-dev`、`cmaes`、`psutil`。

**验收标准**：

- 两条 Uv 命令退出码均为 0。
- `uv pip show pace-sim2real` 显示版本 `0.2.0`，editable location 为项目根目录。
- `importlib.metadata.version("pace-sim2real")` 返回 `0.2.0`。
- 规范化后的直接运行依赖包含 `isaaclab-dev`、`cmaes`、`psutil`。

**Oracle**：

- `uv.lock` 与 `pyproject.toml` 的一致性检查。
- 已安装 distribution 的元数据。
- 需求确定的版本和依赖集合。

**Negative control**：

- 在临时 `pyproject.toml` 副本中把版本改为 `0.2.1`，不更新锁文件；`uv sync --check --locked` 必须失败。
- 在同一副本中增加一个未锁定运行依赖；锁一致性检查必须失败。
- 用期望版本 `0.2.1` 比较已安装的 `0.2.0`，版本断言必须失败。

### I02-T02：模块名、源码位置和 editable 安装位置

**对应 Requirement ID**：`REQ-I02`

**初始条件**：

- I02-T01 已通过。

**输入/触发条件**：

- 在项目 Uv 环境中执行 `import pace_sim2real`。
- 读取 `pace_sim2real.__file__`、`importlib.metadata.distribution("pace-sim2real")` 和 editable 元数据。

**可观察行为**：

- 导入模块名为 `pace_sim2real`。
- 模块源码来自项目的 `src/pace_sim2real`。
- 发行包为项目根目录的 editable 安装。

**验收标准**：

- `import pace_sim2real` 成功。
- `Path(pace_sim2real.__file__).resolve()` 位于项目 `src/pace_sim2real` 下。
- `uv pip show pace-sim2real` 的 editable location 为项目根目录。
- 不存在从其他 checkout 或 wheel 安装路径导入的情况。

**Oracle**：

- `direct_url.json` 的 editable project path。
- 项目 `pyproject.toml` 的 `[tool.uv.build-backend].module-name`。
- 实际 `src/pace_sim2real` 目录结构。

**Negative control**：

- 在临时目录创建一个同名 `pace_sim2real` 模块并置于 Uv 环境之前，路径断言必须失败。
- 或使用期望路径 `src/pace_sim2real_v2` 比较，确认路径校验不是仅检查模块可导入。

### I03-T01：文档公共符号和 task entry point

**对应 Requirement ID**：`REQ-I03`

**初始条件**：

- I01 和 I02 已通过。
- Isaac Lab Python 包可导入。

**输入/触发条件**：

- 导入 `pace_sim2real` 和 `pace_sim2real.utils`。
- 从顶层模块读取六个公共符号。
- 从 `importlib.metadata` 查询 group `isaaclab.tasks` 中名称为 `pace_sim2real` 的 entry point。

**可观察行为**：

- 六个文档声明的公共符号均可导入。
- entry point 指向 `pace_sim2real.tasks`。

**验收标准**：

- 可导入：
  - `PaceSim2realEnvCfg`
  - `PaceSim2realSceneCfg`
  - `PaceCfg`
  - `CMAESOptimizer`
  - `PaceDCMotorCfg`
  - `PaceDCMotor`
- `isaaclab.tasks` 中 `pace_sim2real` 的 value 精确为 `pace_sim2real.tasks`。

**Oracle**：

- `docs/importing.md` 和 `pyproject.toml` 中声明的公开 API 与 entry point。
- `importlib.metadata.entry_points`。

**Negative control**：

- 执行 `from pace_sim2real import NonExistentPublicSymbol`，预期 `ImportError`。
- 在临时元数据副本中把 entry point 改为其他模块，entry point 断言必须失败。

### I03-T02：Gymnasium registry 和模板默认语义

**对应 Requirement ID**：`REQ-I03`

**初始条件**：

- I03-T01 已通过。
- 执行 `import pace_sim2real.tasks` 完成任务注册。

**输入/触发条件**：

- 查询 `gymnasium.registry` 中的 task ID。
- 检查模板任务注册参数和 `PaceSim2realSceneCfg().robot`。

**可观察行为**：

- 两个 PACE task ID 已注册。
- 模板任务仍要求调用方提供 robot 配置，没有新增内置默认 robot。

**验收标准**：

- registry 中存在 `Isaac-Pace-Anymal-D-v0` 和 `Template-Pace-Sim2real-v0`。
- 模板任务的 `env_cfg_entry_point` 指向 `PaceSim2realEnvCfg`。
- `PaceSim2realSceneCfg().robot is dataclasses.MISSING`。

**Oracle**：

- Gymnasium registry API。
- `PaceSim2realSceneCfg` 的模板配置契约。

**Negative control**：

- `gym.spec("Isaac-Pace-Does-Not-Exist-v0")` 必须抛出 `gymnasium.error.NameNotFound`。
- 若测试用默认场景被隐式替换为 ANYmal，`robot is MISSING` 断言必须失败。

### I03-T03：模板任务接受调用方 ANYmal 配置并 reset/step

**对应 Requirement ID**：`REQ-I03`

**初始条件**：

- I03-T01、I03-T02 已通过。
- 验收进程可启动 Isaac Sim。
- 调用方能够实例化 `AnymalDPaceEnvCfg`。

**输入/触发条件**：

- 使用 `AnymalDPaceEnvCfg` 作为 `cfg` 创建 `Template-Pace-Sim2real-v0`。
- 设置 `num_envs=1`、headless。
- 执行一次 `reset()`，然后使用 `env.action_space` 形状的全零动作执行一次 `step()`。

**可观察行为**：

- 模板任务使用调用方提供的 ANYmal 配置创建环境。
- reset 和 step 完成，没有配置或机器人缺失异常。

**验收标准**：

- 环境创建、reset、step 均无异常。
- reset 返回观测，观测空间与配置一致。
- step 返回 Gymnasium 五元组，动作形状与 `action_space` 一致。

**Oracle**：

- Gymnasium 环境调用契约。
- 调用方提供的 `AnymalDPaceEnvCfg`。
- 模板任务不注入 robot 的需求语义。

**Negative control**：

- 使用 `PaceSim2realSceneCfg` 的 `robot=MISSING` 模板场景创建环境，预期因缺少 robot 失败。
- 使用错误形状的动作执行 step，预期不能作为正常的一步运行。

### I04-T01：ANYmal PACE 配置结构和 61 个优化参数

**对应 Requirement ID**：`REQ-I04`

**初始条件**：

- I01、I02 已通过。
- Isaac Lab 配置 API 可导入。

**输入/触发条件**：

- 实例化 `AnymalDPaceEnvCfg()`。
- 读取 `joint_order`、`sim.dt`、`decimation`、`separate_dynamic_friction` 和 `bounds_params.shape`。

**可观察行为**：

- 配置通过 Isaac Lab 3.0 API 实例化。
- ANYmal 配置包含 12 个按显式顺序定义的关节。
- 分离静态/动态摩擦后，参数 bounds 为 61 行。

**验收标准**：

- `joint_order` 精确为：

  ```text
  LF_HAA, LF_HFE, LF_KFE, RF_HAA, RF_HFE, RF_KFE,
  LH_HAA, LH_HFE, LH_KFE, RH_HAA, RH_HFE, RH_KFE
  ```

- `sim.dt == 0.0025`。
- `decimation == 1`。
- `separate_dynamic_friction is True`。
- `bounds_params.shape == (61, 2)`。

**Oracle**：

- `REQ-I04` 的显式参数值。
- `AnymalDPaceCfg` 中 12 个关节的顺序声明。
- `4 * 12 + 1 + 12 = 61` 的参数布局关系。

**Negative control**：

- 保持同一配置类但将 `separate_dynamic_friction` 设为 `False`，预期得到 49 行，因此不能通过 61 行断言。
- 从 `joint_order` 删除一个关节后，12 关节和 61 参数检查必须失败。

### I04-T02：ANYmal PhysX 环境创建和 reset

**对应 Requirement ID**：`REQ-I04`

**初始条件**：

- I04-T01 已通过。
- 终端可访问 GPU。
- Isaac Sim + PhysX 已随 `--extra isaacsim` 安装。

**输入/触发条件**：

- 以 headless、`num_envs=1` 创建 `Isaac-Pace-Anymal-D-v0`。
- 执行环境 reset。
- 检查场景中的 robot articulation 和 12 个目标关节的映射。

**可观察行为**：

- 环境完成 Kit、场景、机器人、关节、执行器和 PACE 配置初始化。
- reset 后机器人 articulation 和动作/观测空间可用。
- 没有属性、类型或 Isaac Lab API 不兼容异常。

**验收标准**：

- `gym.make(..., num_envs=1)` 和 `reset()` 均成功。
- 场景中存在可用的 robot articulation。
- `joint_order` 中每个名称都能映射到唯一 articulation joint。
- 动作和观测空间已创建，且关节维为 12。

**Oracle**：

- Gymnasium/Isaac Lab 环境构建 API。
- `AnymalDPaceEnvCfg.sim2real.joint_order`。
- 机器人 articulation 的公开 `joint_names`。

**Negative control**：

- 在配置副本中把一个 `joint_order` 名称改为不存在关节，映射检查必须失败。
- 在没有 Robot 配置的模板场景上复用相同创建断言，环境构建必须失败。

### I04-T03：reset 和单步输出有限

**对应 Requirement ID**：`REQ-I04`

**初始条件**：

- I04-T02 已通过。
- 使用固定随机种子和 headless、`num_envs=1`。

**输入/触发条件**：

- reset 环境。
- 使用与动作空间匹配的全零动作执行一次 step。

**可观察行为**：

- 动作和观测正常生成。
- step 不抛异常。
- 返回观测不包含意外 NaN 或 Inf。

**验收标准**：

- reset 观测中所有浮点张量满足 `torch.isfinite(...).all()`。
- step 返回完整的 Gymnasium 五元组。
- step 返回的 observation 和数值型 reward 均有限，terminated/truncated 信号的形状合法。
- 没有未捕获的 Isaac Lab API 异常。

**Oracle**：

- `torch.isfinite` 的数学定义。
- Gymnasium step 返回契约。
- 需求只要求有限值，不要求轨迹数值等价。

**Negative control**：

- 将一份观测副本的一个元素设为 `NaN`，同一个有限值检查器必须返回失败。
- 将动作副本的一个元素设为 `Inf`，输入校验路径必须拒绝或明确失败。

### I05-T01：PaceDCMotorCfg 可用性和默认参数

**对应 Requirement ID**：`REQ-I05`

**初始条件**：

- `PaceDCMotorCfg` 和 `PaceDCMotor` 可导入。
- 不启动 Kit。

**输入/触发条件**：

- 使用 ANYmal 执行器所需的饱和力矩、连续力矩、速度限制和关节表达式实例化 `PaceDCMotorCfg`。
- 读取默认字段和 `class_type`。

**可观察行为**：

- 配置对象可实例化。
- ANYmal 的 PACE 配置使用 `PaceDCMotor` 作为执行器类。
- PACE 默认参数保持当前 0.2.0 语义。

**验收标准**：

- `PaceDCMotorCfg(...)` 实例化成功。
- `ANYDRIVE_PACE_ACTUATOR_CFG.class_type is PaceDCMotor`。
- 默认值保持：
  - `encoder_bias == 0.0`
  - `max_delay == 0`
  - `delay_mode == "command"`

**Oracle**：

- `PaceDCMotorCfg` 的当前公开配置契约。
- `REQ-I05` 的“不改变默认参数”要求。

**Negative control**：

- 使用 `delay_mode="effort"` 作为默认值断言，预期失败。
- 在配置副本中将 `max_delay` 改为主观随机值，默认值断言必须失败。

### I05-T02：两种 delay_mode 构造和非法模式拒绝

**对应 Requirement ID**：`REQ-I05`

**初始条件**：

- 使用 kitless 单元测试替身绕过基础 `DCMotor` 的 Kit 绑定。
- 确定性输入形状为 `(1, 2)`。

**输入/触发条件**：

- 分别以 `delay_mode="command"` 和 `delay_mode="effort"` 构造 `PaceDCMotor`。
- 以 `delay_mode="invalid"` 构造同一执行器。

**可观察行为**：

- 两种合法模式均能完成 PACE 自身的初始化。
- 非法模式在初始化阶段被拒绝。

**验收标准**：

- `"command"` 创建 position、velocity、effort 三个延迟缓冲。
- `"effort"` 只创建 effort 延迟缓冲。
- 非法模式抛出 `ValueError`，错误信息包含合法模式集合。

**Oracle**：

- `PaceDCMotor` 文档声明的两种模式。
- `DelayBuffer` 通道语义。

**Negative control**：

- 若非法模式没有抛出异常，该测试必须失败。
- 用合法 `"command"` 配置检查 effort-only 缓冲集合，预期失败，确认模式分支真的被区分。

### I05-T03：零延迟与无延迟输入一致

**对应 Requirement ID**：`REQ-I05`

**初始条件**：

- kitless 单元测试替身。
- `max_delay=0`。
- 位置、速度、前馈力矩均为确定性序列。

**输入/触发条件**：

- 分别以 `"command"` 和 `"effort"` 模式构造执行器，并通过公开的 `compute()` 逐步输入 `ArticulationActions`。
- 测试替身基础 `DCMotor.compute()` 记录收到的命令，并返回可实现预期值的 effort。
- 每步输入不同的非零值。

**可观察行为**：

- 两种模式的输出都与当前输入逐元素相同。
- 缓冲不会引入额外一步延迟。

**验收标准**：

- 每个通道的每步输出与输入使用 `torch.equal` 比较为真。
- command 模式的位置、速度、力矩均恒等。
- effort 模式的计算力矩恒等。

**Oracle**：

- 零时间滞后的恒等映射定义。
- `DelayBuffer(history_length=1, lag=0)` 文档语义。

**Negative control**：

- 将 lag 改为 `1` 并输入阶跃序列，输出与当前输入比较必须不相等。

### I05-T04：command 模式延迟三个命令通道

**对应 Requirement ID**：`REQ-I05`

**初始条件**：

- kitless 单元测试替身。
- `delay_mode="command"`、`max_delay=3`、`time_lag=3`。
- 位置、速度和前馈力矩使用三组互不相同的确定性序列。

**输入/触发条件**：

- 通过公开的 `compute()` 逐步调用执行器。
- 测试替身基础 `DCMotor.compute()` 记录收到的位置、速度和前馈力矩。
- 至少输入 6 个时间步，以覆盖缓冲未填满阶段和稳态阶段。

**可观察行为**：

- 基础 DC motor 收到的位置、速度、前馈力矩分别按 3 步延迟。
- `compute()` 返回的基础计算力矩在 command 模式不额外延迟。
- 三个通道使用各自的历史，不发生通道串用。

**验收标准**：

- 对每个通道，第 `n` 步输出等于输入序列第 `max(0, n - 3)` 步。
- command 模式的位置、速度、effort 三个通道均满足该规则。
- `compute()` 返回的力矩与测试替身基础 DC motor 产生的力矩相同。

**Oracle**：

- 需求定义的三通道命令延迟。
- `DelayBuffer` 在未积累够历史时返回最旧可用样本的文档行为。

**Negative control**：

- 将执行器模式改为 `"effort"`，同一 command 通道期望序列必须不再成立。
- 将三个通道输入设为相同值会使通道串用无法被发现，因此测试必须使用不同序列。

### I05-T05：effort 模式只延迟计算力矩

**对应 Requirement ID**：`REQ-I05`

**初始条件**：

- kitless 单元测试替身。
- `delay_mode="effort"`、`max_delay=3`、`time_lag=3`。
- 计算力矩使用可区分的确定性序列。

**输入/触发条件**：

- 通过公开的 `compute()` 逐步调用执行器。
- 测试替身基础 `DCMotor.compute()` 为每步返回可区分的确定性力矩，并记录收到的命令。

**可观察行为**：

- 计算出的关节力矩按 3 步延迟。
- 位置、速度、前馈力矩命令不被 command 缓冲延迟。

**验收标准**：

- `compute()` 第 `n` 步返回的力矩等于基础 DC motor 输出的第 `max(0, n - 3)` 步力矩。
- 基础 DC motor 收到的位置、速度和前馈力矩在该步保持当前值。

**Oracle**：

- 需求定义的 effort 延迟语义。
- 两种 delay_mode 的互斥通道规则。

**Negative control**：

- 将模式改为 `"command"`，effort 延迟断言必须失败。
- 人工把 effort 序列反向，预期输出不再匹配延迟序列。

### I05-T06：encoder bias 作用于控制器使用的位置

**对应 Requirement ID**：`REQ-I05`

**初始条件**：

- 用测试替身替换基础 `DCMotor.compute`，记录收到的位置和速度。
- 使用零延迟 `PaceDCMotor`。
- 确定性输入为 `joint_pos=[[0.4, -0.2]]`、`joint_vel=[[1.0, -2.0]]`、`encoder_bias=[[0.1, -0.05]]`。

**输入/触发条件**：

- 调用 `PaceDCMotor.compute()`。
- 取得基础 `DCMotor.compute` 实际收到的位置和速度参数。

**可观察行为**：

- 基础控制器使用偏置后的编码器坐标。
- 当前实现语义为 `joint_pos - encoder_bias`。
- 速度测量不被 bias 修改。

**验收标准**：

- 基础 DC motor 收到位置 `[[0.3, -0.15]]`。
- 基础 DC motor 收到速度 `[[1.0, -2.0]]`。
- 输出路径不抛异常。

**Oracle**：

- 用户已确认的当前 0.2.0 编码器坐标语义。
- `PaceDCMotor.compute()` 的现有位置修正顺序。

**Negative control**：

- 将 bias 全部设为零，期望位置仍为 `[[0.4, -0.2]]`，与偏置场景不同。
- 把期望改为 `joint_pos + encoder_bias`，该反向符号断言必须失败。

### I05-T07：动态摩擦比例计算和约束

**对应 Requirement ID**：`REQ-I05`

**初始条件**：

- bounds 形状检查使用 12 个关节的通用 PACE 配置；动态摩擦数值计算使用 2 个关节的测试夹具。
- `separate_dynamic_friction=True`。
- 静态摩擦 `[[0.2, 0.4]]`，动态/静态比例 `[[0.25, 0.5]]`。

**输入/触发条件**：

- 调用配置的 `apply_friction_ratio()`。
- 在临时日志目录初始化 `CMAESOptimizer`，注入上述静态摩擦和比例。
- 调用 `optimizer.dynamic_friction()`。

**可观察行为**：

- 49 行基础 bounds 后追加 12 行比例 bounds，总数为 61。
- 比例 bounds 默认为 `(0.0, 1.0)`。
- 动态摩擦等于静态摩擦乘以比例。

**验收标准**：

- `bounds_params.shape == (61, 2)`。
- 最后 12 行比例 bounds 的上下界分别为 `0.0` 和 `1.0`。
- `dynamic_friction()` 返回 `[[0.05, 0.2]]`。
- 所有动态摩擦值满足 `0 <= dynamic <= static`。

**Oracle**：

- 需求给出的公式 `dynamic = ratio * static`。
- `friction_ratio_bounds=(0.0, 1.0)` 的配置契约。
- `CMAESOptimizer` 对比例 bounds 的合法性校验。

**Negative control**：

- 构造比例 `1.2`，预期违反 `dynamic <= static` 并被 bounds/不变量检查拒绝。
- 构造负比例，预期 bounds 校验失败。

### I06-T01：短时 chirp 数据采集完成并生成文件

**对应 Requirement ID**：`REQ-I06`

**初始条件**：

- I04 已通过。
- GPU 终端可运行 Isaac Sim + PhysX。
- `PACE_ROOT` 指向空的临时根。
- `MPLBACKEND=Agg`。

**输入/触发条件**：

- 执行：

  ```bash
  python scripts/pace/data_collection.py \
    --headless \
    --task Isaac-Pace-Anymal-D-v0 \
    --num_envs 1 \
    --duration 0.1 \
    --min_frequency 0.1 \
    --max_frequency 10 \
    --device cuda:0
  ```

**可观察行为**：

- 脚本启动 ANYmal PACE 环境。
- 执行完整 chirp 轨迹后关闭环境。
- 在 `PACE_ROOT/data/anymal_d_sim/chirp_data.pt` 生成文件。
- Agg 后端使原有 `plt.show()` 不阻塞。

**验收标准**：

- 进程退出码为 0。
- 目标文件存在且 `torch.load(..., map_location="cpu")` 成功。
- 文件由本次测试的新进程生成，不读取或复用旧产物。

**Oracle**：

- 脚本输入参数。
- `PACE_ROOT` 和 `AnymalDPaceCfg.robot_name` 确定的输出路径。
- 进程退出码和 `torch.load`。

**Negative control**：

- 使用不存在的 task ID 运行同一命令，预期非零退出且临时输出根中没有新 `chirp_data.pt`。
- 在空输出根上执行文件存在断言，预期失败，确认没有误用旧数据。

### I06-T02：chirp 数据键、shape 和有限值

**对应 Requirement ID**：`REQ-I06`

**初始条件**：

- I06-T01 生成的 `chirp_data.pt`。
- `sim.dt=0.0025`、`duration=0.1`。

**输入/触发条件**：

- 用 `torch.load(..., map_location="cpu")` 加载数据。
- 读取 `time`、`dof_pos`、`des_dof_pos`。

**可观察行为**：

- 三个序列存在且时间维一致。
- 关节维为 12。
- 数据没有意外 NaN 或 Inf。

**验收标准**：

- 键集合至少包含 `time`、`dof_pos`、`des_dof_pos`。
- 预期步数为 `N = int(0.1 / 0.0025)`，当前值为 `40`。
- `time.shape == (N,)`。
- `dof_pos.shape == (N, 12)`。
- `des_dof_pos.shape == (N, 12)`。
- 三个张量全部满足 `torch.isfinite(...).all()`。

**Oracle**：

- 数据脚本的采样率 `1 / sim.dt` 和时间序列构造。
- `joint_order` 的 12 个关节。
- `torch.isfinite`。

**Negative control**：

- 在内存副本中删除 `des_dof_pos`，键断言必须失败。
- 在内存副本中把一个元素替换为 `NaN`，有限值断言必须失败。

### I07-T01：单迭代 CMA-ES fit 完成并生成产物

**对应 Requirement ID**：`REQ-I07`

**初始条件**：

- I06 已生成符合 I06-T02 的 `chirp_data.pt`。
- GPU 终端可运行 Isaac Sim + PhysX。
- `PACE_ROOT` 指向同时包含 I06 数据和 scripts 的临时根。
- `MPLBACKEND=Agg`。

**输入/触发条件**：

- 测试包装器 monkeypatch `isaaclab_tasks.utils.parse_env_cfg`：
  - 先调用原函数；
  - 将返回配置的 `sim2real.cmaes.max_iteration` 设为 `1`；
  - 返回修改后的配置。
- 包装器使用 `runpy.run_path(..., run_name="__main__")` 执行当前 `scripts/pace/fit.py`。
- 脚本参数为 `--headless --num_envs 2 --task Isaac-Pace-Anymal-D-v0 --device cuda:0`。

**可观察行为**：

- CMA-ES 完成一次参数采样、rollout、评分和迭代更新。
- 新运行目录创建在 `PACE_ROOT/logs/pace/anymal_d_sim`。
- 运行目录内写出优化配置、最佳轨迹、均值参数和 TensorBoard 事件。
- 进程正常退出。

**验收标准**：

- 脚本退出码为 0。
- 存在本次新增的运行目录。
- 运行目录中存在：
  - `config.pt`
  - `best_trajectory.pt`
  - 至少一个匹配 `mean_*.pt` 的文件
  - 至少一个 TensorBoard `events.out.tfevents*` 文件
- 所有 `.pt` 文件可用 `torch.load(..., map_location="cpu")` 重新加载。

**Oracle**：

- 需求指定的 `num_envs=2` 和 `max_iteration=1`。
- `CMAESOptimizer.save_checkpoint()` 的公开产物契约。
- TensorBoard writer 的标准事件文件前缀。

**Negative control**：

- 包装器将 `max_iteration` 设为 `0`，预期没有完成一次迭代且产物断言失败。
- 移除临时根中的 `chirp_data.pt`，预期 fit 在进入仿真流程前非零失败。

### I07-T02：fit 配置和轨迹产物的结构一致性

**对应 Requirement ID**：`REQ-I07`

**初始条件**：

- I07-T01 生成的运行目录和产物。
- I06 的输入数据和 `AnymalDPaceCfg`。

**输入/触发条件**：

- 加载 `config.pt`、`best_trajectory.pt` 和最新的 `mean_*.pt`。
- 对照输入 chirp 数据和配置检查 bounds、joint order、时间序列和摩擦模式。

**可观察行为**：

- 配置保存正确输入和参数布局。
- 最佳轨迹和均值参数 shape 与 61 参数配置一致。

**验收标准**：

- `config["joint_order"]` 为 I04-T01 的 12 个关节。
- `config["bounds"].shape == (61, 2)`。
- `config["time"]`、`config["dof_pos"]`、`config["des_dof_pos"]` 与输入 chirp 数据 shape 一致。
- `config["separate_dynamic_friction"] is True`。
- `best_trajectory.shape == (N, 12)`，其中 `N` 为输入时间步数。
- 最新 `mean_*.pt` 展平后的参数数量为 61。

**Oracle**：

- I06-T02 已独立验证的输入数据。
- `AnymalDPaceCfg` 的 12 关节和 61 参数布局。
- `CMAESOptimizer` 保存配置和轨迹的公开契约。

**Negative control**：

- 在内存副本中把 `joint_order` 改为 11 个关节，结构检查必须失败。
- 把 `best_trajectory` 改为 `(N, 11)`，关节维断言必须失败。

### I07-T03：绘图脚本读取最新参数并完成

**对应 Requirement ID**：`REQ-I07`

**初始条件**：

- I07-T01、I07-T02 已通过。
- 临时根中存在 `scripts/pace/plot_trajectory.py` 的原样副本。
- `MPLBACKEND=Agg`。

**输入/触发条件**：

- 在临时根中执行绘图脚本，并启用 `--plot_trajectory`。
- 不显式传入 `--folder_name`，验证脚本自动选择最新运行。
- 不显式传入 `--mean_name`，验证自动选择最高迭代号的 `mean_*.pt`。

**可观察行为**：

- 脚本找到最新运行目录和参数文件。
- 读取 `config.pt` 和 `best_trajectory.pt`。
- 完成轨迹读取和绘图逻辑，打印完成信息。
- 不要求持久化图片。

**验收标准**：

- 进程退出码为 0。
- 标准输出包含最新参数文件路径。
- 标准输出包含 `Plotting complete.`。
- 脚本选择的运行目录是本次新运行，不是既有运行。

**Oracle**：

- 绘图脚本的公开输出信息和参数选择规则。
- I07-T01 创建的新运行目录和参数文件。

**Negative control**：

- 在同一运行目录放置一个编号更高但损坏的 `mean_*.pt`。脚本应选择并尝试加载它，随后非零失败，且不打印 `Plotting complete.`。
- 在空日志目录运行，预期因找不到运行或参数文件失败。

### I08-T01：PPORunnerCfg 导入和实例化

**对应 Requirement ID**：`REQ-I08`

**初始条件**：

- `rsl-rl-lib` 和 Isaac Lab 3.0 RSL-RL 集成可导入。
- 不启动 Kit。

**输入/触发条件**：

- 从 PACE 的 RSL-RL agent 配置模块导入 `PPORunnerCfg`。
- 实例化该配置并读取 policy、algorithm 和 runner 字段。

**可观察行为**：

- 配置类可导入和实例化。
- Isaac Lab 3.0 导出路径与当前 PACE 配置兼容。

**验收标准**：

- `from ...rsl_rl_ppo_cfg import PPORunnerCfg` 成功。
- `PPORunnerCfg()` 实例化成功。
- 配置包含可用的 policy、algorithm、`max_iterations`、`save_interval` 和 `experiment_name` 字段。

**Oracle**：

- 项目注册的 `rsl_rl_cfg_entry_point`。
- Isaac Lab 3.0 的公开 RSL-RL runner 配置契约。

**Negative control**：

- 导入不存在的配置符号，预期 `ImportError`。
- 向 `PPORunnerCfg` 注入不存在的构造参数，预期实例化失败。

### I08-T02：单迭代 RSL-RL 训练生成日志和 checkpoint

**对应 Requirement ID**：`REQ-I08`

**初始条件**：

- I03 和 I04 已通过。
- I08-T01 已通过。
- GPU 终端可运行 Isaac Sim + PhysX。
- 当前工作目录为空临时根。

**输入/触发条件**：

- 执行：

  ```bash
  python /absolute/path/to/scripts/rsl_rl/train.py \
    --headless \
    --task Isaac-Pace-Anymal-D-v0 \
    --agent rsl_rl_cfg_entry_point \
    --num_envs 1 \
    --max_iterations 1 \
    --device cuda:0
  ```

**可观察行为**：

- PACE 环境和 RSL-RL runner 创建成功。
- 完成一次学习迭代。
- 在临时工作目录写训练日志、配置和模型 checkpoint。
- 进程正常退出。

**验收标准**：

- 训练进程退出码为 0。
- `logs/rsl_rl/<experiment_name>/<timestamp>/` 下存在本次新增运行目录。
- 运行目录中存在 TensorBoard 事件、参数配置和至少一个匹配 `model_*.pt` 的 checkpoint。
- checkpoint 可由 RSL-RL 加载路径读取。
- 不检查 reward、策略性能或收敛指标。

**Oracle**：

- `train.py` 的日志根目录和 `OnPolicyRunner` checkpoint 命名规则。
- RSL-RL checkpoint 加载契约。

**Negative control**：

- 使用 `--max_iterations 0`，预期没有完成有效学习迭代，训练产物断言失败。
- 使用不存在的 agent entry point，预期 Hydra/config 解析非零失败。

### I08-T03：checkpoint 回放、策略导出和单步视频退出

**对应 Requirement ID**：`REQ-I08`

**初始条件**：

- I08-T02 生成的 checkpoint。
- GPU 终端可运行 Isaac Sim + PhysX 和视频录制。
- 与训练相同工作目录，或使用 checkpoint 的绝对路径。

**输入/触发条件**：

- 执行：

  ```bash
  python /absolute/path/to/scripts/rsl_rl/play.py \
    --headless \
    --task Isaac-Pace-Anymal-D-v0 \
    --agent rsl_rl_cfg_entry_point \
    --num_envs 1 \
    --checkpoint /absolute/path/to/model_N.pt \
    --video \
    --video_length 1 \
    --device cuda:0
  ```

**可观察行为**：

- 脚本找到并加载 checkpoint。
- 创建推理策略和环境包装器。
- 执行恰好 1 个环境 step。
- 导出策略并结束 RecordVideo，然后脚本正常退出。

**验收标准**：

- play 进程退出码为 0，且不是由外部看门狗杀死。
- 输出确认 checkpoint 已加载。
- 完成 1 个环境 step。
- `exported/policy.pt` 和 `exported/policy.onnx` 存在且非空。
- 播放视频文件已生成并完成封装。
- 不要求 reward、动作幅值或视频内容达到特定数值。

**Oracle**：

- `play.py` 的录像循环在 `timestep == video_length` 时退出。
- RSL-RL policy export 路径。
- checkpoint 和视频文件的公开写入契约。

**Negative control**：

- 使用不存在的 checkpoint 路径，预期 play 非零失败且不生成 `exported/policy.*`。
- 将 `--video_length 2` 用于一个只断言“恰好 1 步”的镜像测试，预期该断言失败；不把 `2` 步结果作为 I08 验收。

## 完成判定

本 Issue 的兼容性测试只有在以下条件同时满足时可判定通过：

- I01-T01 至 I08-T03 全部在目标平台和可访问 GPU 的终端得到通过结果。
- 因环境不可用而跳过的 GPU 测试记为“未执行”，不能计入通过。
- 所有必要的临时数据和日志已按本计划清理，运行前已有文件保持不变。
- 测试证据包含退出码、关键 shape/元数据、产物存在性和失败路径的 Negative control 结果。
