# 无 GPU 依赖兼容性修复

2026-10-29；状态：修复完成，静态检查通过，运行时未验证。

授权：用户要求“不加载 GPU 的依赖兼容性检查，解决已知启动错误，再讨论受限重试”。本次只修复该范围的依赖，未进入 Specify 或实现悬吊环境。

## 原因与修改

IsaacLab HEAD `346c74fe722ad371a6c663e3b384b3d172966d11` 的 replicate.py 调用 `ModelBuilder.add_usd(allow_unsafe_torch_checkpoints=True)`。项目 override、锁文件和原已安装 Newton 均固定为 `71eeba16a717d4dcf0b9dd7056a7b6f863054dc3`，源码函数没有该参数。IsaacLab 自身 pyproject 和 lock 固定为 `42f7def118c2c4299ce493457bafd4e8a22a696e`，对应源码包含该参数。两个提交版本字符串同为 1.8.0.dev0，版本字符串不足以判断兼容性。

已将项目 pyproject.toml 的 Newton 提交对齐 IsaacLab。没有删除调用参数、修改上游源码或加运行时 monkey patch。

元数据检查另发现已安装 NumPy 2.5.4 不满足 numba 0.64.0 的 `<2.5` 和 Python 3.12 下 cmeel-boost 1.89.0 的 `>=2.3,<2.4`。检查当前已安装包的 NumPy requirements 后，将项目 override 收紧到 `>=2.3,<2.4`，解析为 2.3.5。

更新 uv.lock 并同步项目 `.venv`。与本轮开始备份进行 TOML 结构比较，仅 newton、numpy 两个 package 条目改变；项目 editable 包因元数据变更重新安装。原有 AGENTS.md 和 uv.lock 的其他工作区修改保留。修复前备份：uv.lock.before_compatibility_fix、pyproject.toml.before_compatibility_fix。

## 执行与证据

- 使用标准库 importlib.metadata、ast、tomllib 读取元数据和源码；不 import 仿真包。最初元数据读取直接使用项目 `.venv/bin/python`，后续验证按用户习惯使用 uv run。
- `uv lock --offline`：初次因缓存权限失败；获批沙箱外重试后因缺 registry 缓存失败。随后 `uv lock` 在线解析成功。
- 每次同步前运行 `uv sync --locked --dry-run` 检查变更范围，再运行 `uv sync --locked`；均退出 0。先仅替换 Newton，后仅替换 NumPy，两次均刷新项目 editable 包。
- `uv run --no-sync python .scratch/issue_2/check_dependency_contract.py`：最终退出 0。项目 pin、IsaacLab pin、锁文件及安装 commit 一致；7 处 add_usd 调用的显式关键字均在目标签名内。`runtime_modules_loaded=[]`；JSON 证据为 dependency_contract_results.json。此检查不覆盖参数类型、调用语义、动态代码或 GPU 能力。
- `uv pip check --python .venv/bin/python`：修复前退出 1，两个 NumPy 冲突；修复后退出 0，`Checked 220 packages`、`All installed packages are compatible`。只验证声明关系，不保证二进制 ABI 或完整运行时行为。
- `git diff --check`：退出 0。标准库 TOML 比较输出 `Changed locked packages: ['newton', 'numpy']`，断言通过。
- 解析器另提示已有 grpcio / hf-xet 锁定版本被撤回，构建时提示 uv-build 版本范围与当前 uv 不同；这些非本次引入，未扩展本次修复范围。依赖检查通过不等于供应链或漏洞审计通过。

## 受限重试提案（未批准、未执行）

首次仅做一个环境的无界面资产加载、环境构造、reset 和退出，不进行激励或 60 s 动态试验。使用项目 `.venv`、修复后的锁定依赖；单一子进程组，无并行测试。

建议最大墙钟时间 90 s、系统内存 MemoryMax=8 GiB、MemorySwapMax=0、CPUQuota=200%，由独立进程组/cgroup 监护退出；若所需限制无法生效，停止而不退回无约束执行。内存限制只针对系统 RAM，不能限制独显 VRAM，也不能保证驱动不会失效。记录加载阶段和失败信息，超时或任何错误即退出，不自动重复。

在用户明确批准后才准备和执行该运行器；本轮不启动 GPU、不调用 nvidia-smi、不修改系统驱动或电源管理。该重试只验证依赖修复后的启动路径，不证明黑屏已解决。首次结果审阅后再决定是否批准更短的动力学步进实验。
