# Issue #2 状态

## 2026-10-29：一次受限 20 步耦合实验通过

- 用户 yes 批准单次 20 步；同 cgroup 资源限制下完成 0.05 s，服务 58.721 s 正常退出，无自动重试。
- 浮动 ANYmal D + PaceDCMotor + 合成四绳力，均为有限状态；最大缩放挂钩平衡残差 2.69e-12，四绳始终张紧。基座/关节有响应，但未验证静止平衡初态、因果对照、收敛、松弛再张紧或 60 s 残余摆动。
- 详见 bounded20_report.md 及 robot_bounded20_* 证据。Research 继续，尚未进入 Specify。下一批零激励对照与半步长短实验只作提案，等待用户审批；没有继续 GPU 工作。

## 2026-10-29：已批准的一次受限加载/reset 通过

- 用户 yes 批准一次受限重试；已执行 bounded_reset_probe.py，单环境 headless，cgroup 内确认 RAM 8 GiB、swap=0、CPU 两核额度；systemd 设置 85 s 运行及 5 s 终止等待。服务 26.892 s 正常退出，未触发上限。
- 浮动 ANYmal D、PaceDCMotor 环境构造/reset/close 成功；显式 env.step 次数 0。参数兼容性修复通过本次实际加载路径验证。
- 详见 bounded_reset_report.md、bounded_reset.log、bounded_reset_result.json。没有进行动力学实验或证明黑屏问题修复。下一步最多 20 步受限耦合探针需用户另行批准，不自动执行。

## 2026-10-29：无 GPU 兼容性修复完成

- 用户明确授权无 GPU 检查并解决已知启动错误。本轮将项目 Newton 提交从 71eeba16 对齐到当前 IsaacLab 要求的 42f7def1，恢复 add_usd 参数契约；另将 NumPy 收紧为 >=2.3,<2.4 并安装 2.3.5，关闭 numba/cmeel-boost 声明冲突。
- 修改 pyproject.toml、uv.lock、项目 .venv，保留本轮前既有工作区变更和备份。AST 契约检查、220 包依赖检查、git diff --check 均通过；没有加载 GPU 或仿真运行时。
- 完整命令、证据和未执行的受限启动重试提案见 dependency_compatibility.md。GPU/仿真仍停止，等待用户批准受限重试；本修复不证明黑屏原因已解决，不代表进入 Specify。

## 2026-10-29：用户报告电脑崩溃，停止实验

- 时间已确认是 10-29 08:51–08:57 唤醒后。追加只读日志定位到 08:57:29 dbus-daemon general protection fault / SIGSEGV，随后桌面会话失效、GDM 重启及 login1 激活超时。无 D-Bus core 堆栈，根因未定；与先前测试的因果关系未证实。详见 black_screen_diagnosis.md 补充结论。未恢复实验。

- 用户补充症状为黑屏，并授权只读日志诊断。首轮结果见 black_screen_diagnosis.md：上一启动没有匹配 Xid/OOM kill；08:51 挂起恢复有 i915/NVIDIA 电源事件异常；08:57:29 系统 D-Bus SIGSEGV 与 GNOME 显示连接断开，随后 GDM 重启。根因及与测试的关联尚未确定，待确认黑屏时间。保持实验停止。

- 用户报告上一次 Codex 测试导致电脑崩溃。具体根因尚未确认，不能以 Python 异常代替系统故障诊断。
- 暂停后续仿真及 GPU 调用；在用户确认诊断/重试范围前，不恢复先前已授权的动态实验。
- 已执行轻量进程检查：`ps -eo pid,ppid,comm,args | rg '[r]obot_coupling_probe.py|[h]ook_equilibrium_probe.py|[n]ative_tendon_probe.py|[s]ingle_rope_reference.py'`，退出 1，无匹配实验进程。此检查不证明不存在其他派生进程或系统故障。
- 最近保留的 robot_smoke.log 显示场景构建阶段 `ModelBuilder.add_usd()` 不接受 `allow_unsafe_torch_checkpoints` 参数，进程退出 1；尚未完成动力学步进。此 API 不兼容不能解释或排除电脑崩溃原因。
- 先前动态实验没有明确设置资源上限和总运行时限；后续重试前需先诊断系统/驱动/OOM 证据，提出可审阅的受限运行方案，再请求用户确认。当前不执行该诊断或重试。
- 工作目录按最新用户指引使用 `.scratch/issue_2/`；下文早期阶段和实验记录保留为历史。

状态：**Research 最小实验已获批准，进行中 / Explore 已批准**。

更新日期：2026-10-28。

## 当前阶段与授权

- Issue：[激励轨迹安全性仿真](https://github.com/MrCCaesar/pace-sim2real/issues/2)。已读取标题、正文、评论；读取时无评论。
- 用户已批准 Explore 需求基线及 U-01 至 U-04 的移交边界，并授权进入 **Research**；审批原文及边界见 [requirements.md](requirements.md) 的 AP-01。
- 当前优先级：定量冲击峰值所需的数据和验证证据。
- 当前工作文档：[research.md](research.md)；需求基线为 Approved，技术建议为 Draft/Proposed。
- AP-02：用户回复“1. 是；2. 是”，批准推荐建模方向及 research.md 最小实验范围；ADR-001 已接受。环境安装仍需另行确认；未授权 Specify、Plan、Implement 或 Verify。
- AP-03：用户选择“先用合成几何做能力验证”，允许机器人耦合实验使用明确标记的合成几何，不作为实物参数或实物精度验证。
- 环境补充：`../IsaacLab/.venv` 元数据含 isaaclab 42.0.0、newton 1.8.0.dev0、ovphysx 0.6.4.72118723、isaacsim 6.2.0.0、torch 2.11.0+cu130、mujoco 3.15.0。无需据项目 .venv 缺包推断必须安装。
- GPU 检查：沙箱内 nvidia-smi 失败；获准在沙箱外执行同一只读查询后退出 0，返回 RTX 4060 Laptop GPU / 驱动 595.99.02。该结果仅为设备检查，不是仿真通过。

## 已完成

- 阅读仓库 `AGENTS.md`、已有结构、相关配置与脚本，以及 Issue #1 历史需求/验证记录；未发现已有 Issue #2 工作文档。
- 查阅 IsaacLab 官方 Manager 工作流与 RL 环境文档，仅核对需求上下文与官方惯例。
- 建立需求工作稿，区分 Issue 已明确项、用户澄清、暂定假设、待确认问题、延后决定和 Explore 验收建议。
- 用户已确认：主绳为钢链、工况内不松弛、可忽略伸缩；绳索不需考虑自身质量；四根尼龙短绳会松弛后重新张紧，测试无肉眼可见伸长。
- 用户已确认：挂钩能绕主绳旋转、无明显摩擦，可视为无质量理想刚体。尚未选择仿真器中的表达方式。
- 用户已确认：覆盖启动、激励、停止后残余摆动，不考虑初始摆动与地面/构件接触；需要输出张力等量，没有阈值。
- 用户已确认：第一版以仓库现有 ANYmal D 验收，轨迹为关节位置目标，使用机器人默认驱动器。核对时发现原始 LSTM 与 PACE 覆盖配置的歧义，已通过追加澄清解决，见下文。
- 用户已确认：从静止悬吊平衡状态、默认关节姿态启动；激励结束后关节指令恢复默认配置，观察停止后 60 s 内的残余摆动。
- 用户已确认：四短绳在挂钩处汇于同一点，各绳端自由转动、不传递弯矩；需四短绳各自张力时序及定量冲击峰值，主链张力无需输出。
- 默认驱动器歧义已解决：用户明确选择仓库现有 PACE ANYmal D 任务的 PaceDCMotor 配置。
- Explore 需求基线及验收边界已获用户确认，Research 开始时重新读取 Issue，仍无评论、原文未变；用户 AP-01 的阶段授权优先于 Issue 的初始 Explore 阶段描述。

## 当前未决项

- AP-02 后已完成 CPU 单绳解析参照和 MuJoCo 原生弹性 tendon 探针；命令及结果见 research.md 末节。零阻尼极限通过，但加入阻尼后松弛零力要求失败；无质量自由 body 编译失败。机器人耦合尚未执行，不宣称最小实验全部完成。
- AP-04 已批准：四短绳同时松弛作为适用域外并报告失效；requirements.md 已补 R-16，ADR-002 已接受。
- 已执行合成无质量汇交点静态探针：四/二/一根张紧均找到局部平衡，残差小于 1.1e-12；全松弛虽被数值求解器报告成功，但 Jacobian 奇异，按 R-16 判为失效。这不是动态唯一性证明。
- 运行环境已纠正：按用户指令使用 `/home/sevnce-mr/pace-sim2real/.venv`，通过 `uv run --no-sync python` 调用已有同步环境。当前 isaaclab=42.0.0、cmaes=0.13.1、mujoco=3.15.0、scipy=1.17.0、torch=2.11.0+cu130。此前缺包记录仅适用于当时检查的解释器/状态，已不构成阻塞；取消向相邻环境安装 cmaes 的请求。
- 项目环境配置预检已通过，CUDA 可用；汇交点探针在项目环境重跑通过。记录见 research.md 与 project_environment_probe_results.json。未安装依赖；机器人耦合/60 s 实验尚未运行。

- 首轮、第二轮及默认驱动器追加问题均已答复；完整记录见 requirements.md 的 C-01 至 C-07。
- U-01（关键）：短绳材料参数、定量冲击峰值的精度要求和验证依据尚缺。建议 Research 优先调查所需输入与可行性限制；未批准忽略短绳弹性/耗能或降低峰值输出要求。
- U-02：吊索长度、固定点与挂点位置的具体值待补齐；建议列为后续配置/算例前的资料依赖。
- U-03：本地 IsaacLab checkout 与 Issue #1 历史记录不同；当前项目 `.venv` 查询不到 `isaaclab` 包元数据。建议 Research 核对源码、依赖和后端基线；未安装依赖，也未进行运行时验证。
- U-04：具体数据格式、坐标/单位、峰值采样/报告语义与误差指标留待 Research 提供证据、Specify 制定契约。
- 上述移交已获用户确认；不把未知参数变成未经批准的物理假设。

## 检查与变更边界

- 只读检查：GitHub Issue、仓库文件与历史文档、官方文档、本地 IsaacLab 源码版本、Python 包元数据。
- 包元数据查询：`PackageNotFoundError`；不据此推断其他环境或系统安装状态。
- `git diff --check`：退出 0；该命令只覆盖已跟踪的工作区差异。
- 两个新增 Markdown 另执行以下检查，退出 0，输出 `2 Markdown files: final newline, trailing whitespace, and status target checks passed`：

  ```bash
  python3 -c 'from pathlib import Path; files = sorted(Path(".scartch/issue_2").glob("*.md")); assert len(files) == 2; assert all(p.read_text().endswith("\n") and all(line == line.rstrip() for line in p.read_text().splitlines()) for p in files); assert Path(".scartch/issue_2/requirements.md").is_file(); print("2 Markdown files: final newline, trailing whitespace, and status target checks passed")'
  ```

- 未运行仿真、实验或自动化测试；未修改实现代码，未提交/推送或编辑 GitHub Issue。
- 仓库 `AGENTS.md` 在本轮开始前已有工作区修改；保持原样。

## 下一步与阶段门禁

2026-10-28 续接：沙箱执行恢复。已补充 research.md 的方案比较、证据 E-01 至 E-06、材料与峰值验证依赖、实验提案及 D-01 至 D-04；新建 Proposed ADR-001。建议先批准建模方向及最小实验，再决定 Specify。未安装依赖、未运行实验、未进入 Specify。现有 AGENTS.md、uv.lock 工作区修改非本轮产生，保持原样。下列条目保留为研究开始时的计划，其中资料研究已完成首轮。

1. 开展已授权的资料与源码研究，优先调查定量冲击峰值所需物理输入、观测定义与验证依据，其次核对版本、后端及悬吊表达能力。
2. 在 research.md 中记录事实、证据、限制、候选方法与建议；重要技术/物理模型建议单独建立 Proposed ADR。
3. 需要最小实验时先提供可审阅方案并请求批准；Research 总结后等待下一阶段批准，不自行进入 Specify。
