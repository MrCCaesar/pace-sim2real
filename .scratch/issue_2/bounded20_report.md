# 20 步合成机器人耦合实验

日期：2026-10-29；状态：本次短程集成检查通过，Research 未结束。

## 授权及执行

用户 yes 批准相同资源限制下单次 20 步（0.05 s）悬吊耦合检查。实际命令：

```bash
systemd-run --user --unit=pace-issue2-20steps-20261029 --wait --pipe --property=MemoryMax=8G --property=MemorySwapMax=0 --property=CPUQuota=200% --property=RuntimeMaxSec=85s --property=TimeoutStopSec=5s --property=KillMode=control-group --property=OOMPolicy=kill --property=Restart=no --working-directory=/home/sevnce-mr/pace-sim2real --setenv=PYTHONUNBUFFERED=1 --setenv=OMP_NUM_THREADS=2 --setenv=OPENBLAS_NUM_THREADS=2 /home/sevnce-mr/.local/bin/uv run --no-sync python .scratch/issue_2/robot_coupling_probe.py --settle 0 --excite 0.05 --observe 0 --max-steps 20 --tag bounded20 > .scratch/issue_2/robot_bounded20.log 2>&1
```

退出 0，systemd result=success，runtime=58.721 s、CPU time=56.132 s。无自动重试。实验脚本在导入 GPU 运行时前验证自身 cgroup RAM=8 GiB、swap=0、CPU quota=200%；最多 20 步由启动前断言限制。系统汇总 Memory peak=1.2M 不作为可信运行时 RAM/VRAM 峰值证据，理由同 bounded_reset_report.md。

## 方法与检查范围

- ManagerBasedRLEnv + Newton/MuJoCo Warp；单个浮动 ANYmal D，沿用 PACE 驱动器；没有地面/自碰撞。
- 四个合成挂点、主链 2 m，合成短绳刚度 10000 N/m、阻尼 100 Ns/m。只在伸长为正时计算截断为非负的张力；这只是研究用候选本构，不是经校准的尼龙模型。
- 每个 0.0025 s 物理步之前求解挂钩力平衡和定长约束，挂钩速度采用后向差分；用 instantaneous_wrench_composer 在四挂点施加世界系作用力，保留挂点力矩。
- 初始默认关节姿态，绳长按重力支撑合成，未进行静态收敛或执行器重力平衡。因此不能声称满足 R-15 的静止悬吊平衡初态。
- 仅 LF_HFE 有平滑位置目标扰动；峰值指令偏移约 0.01695 rad。此次窗口没有结束后观察步骤。
- 预设失败条件：全松弛、负主链反力、非有限求解或状态、缩放平衡残差 >1e-6、意外环境终止/reset。任一发生即失败，不调整阈值重跑。

## 结果

证据：robot_bounded20_summary.json、robot_bounded20_timeseries.npy、robot_bounded20_analysis.json、robot_bounded20.log。

- 完成 20 步、0.05 s；20×46 个步前记录均有限，另记录最终步后位置、速度和关节位置。NumPy CPU 分析断言通过，退出 0。
- 四短绳记录张力范围约 125.55–134.16 N；始终大于零，没有覆盖松弛或再张紧。该值仅为合成模型张力，不能报告为真实冲击峰值。
- 最大缩放平衡残差范数 2.6897e-12；其中力平衡按机器人重力缩放，长度残差以米进入，属于探针求解检查，不是整体仿真精度契约。
- 最大主链长度误差 2.6645e-15 m，仅代表代数节点约束，不代表真实链条或动态误差。
- 基座位移约 (4.70e-6, -4.61e-8, 7.55e-4) m；最大记录基座质心线速度 0.02055 m/s；最大最终关节变化 0.01980 rad。可见关节与基座发生响应，但缺少零激励对照，不能将全部基座运动归因于激励。
- 同期内核定向检索无新 Xid、OOM kill、GPU HANG、general protection fault 或 segfault 匹配；结束后未匹配到实验脚本进程。此结果不证明休眠唤醒问题已修复。
- `git diff --check` 退出 0。

## 结论与待批准下一步

候选 C 的“代数无质量节点 + 单侧候选材料力 + 官方外力接口”已有短程集成证据；尚不能选定生产方案。未验证零激励初态漂移、步长收敛、耗能正确性、活动绳切换、真实峰值或停止后 60 s。

建议下一批两个顺序执行、各自同资源/时间限制的短实验：①dt=0.0025 s、20 步、零激励，量化初态漂移；②dt=0.00125 s、40 步、同物理时长及同连续目标轨迹，观察步长敏感性。第二项必须保持驱动器物理延迟等时间语义一致或显式报告差异；不能仅改变 dt 后将差异全部归因于积分。任何一个失败即停止整批，不自动重试。该提案尚未批准，未执行。
