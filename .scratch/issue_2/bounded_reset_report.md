# 单次受限加载/reset 结果

日期：2026-10-29；状态：本次加载/reset 通过，动力学及系统黑屏问题未验证。

授权：用户对单环境、无界面、仅加载/reset 后退出、90 秒上限、RAM 8 GiB、CPU 两核额度的提案回复 yes。本次授权不包括后续动力学步进。

## 执行

实验文件：bounded_reset_probe.py。仅在 Issue 工作目录添加实验文件，未改生产环境接口。

执行命令（一次；没有自动重试）：

```bash
systemd-run --user --unit=pace-issue2-reset-20261029 --wait --pipe --property=MemoryMax=8G --property=MemorySwapMax=0 --property=CPUQuota=200% --property=RuntimeMaxSec=85s --property=TimeoutStopSec=5s --property=KillMode=control-group --property=OOMPolicy=kill --property=Restart=no --working-directory=/home/sevnce-mr/pace-sim2real --setenv=PYTHONUNBUFFERED=1 --setenv=OMP_NUM_THREADS=2 --setenv=OPENBLAS_NUM_THREADS=2 /home/sevnce-mr/.local/bin/uv run --no-sync python .scratch/issue_2/bounded_reset_probe.py > .scratch/issue_2/bounded_reset.log 2>&1
```

沙箱不能访问用户 systemd 总线，获准在沙箱外运行。进程在导入运行时之前读取其自身 cgroup 文件并断言：memory.max=8589934592、memory.swap.max=0、cpu.max=`200000 100000`。85 秒运行上限加最多 5 秒终止等待对应 90 秒预算；本次未触发超时，不声称测试过超时杀进程行为。

## 结果与证据

- systemd-run 退出 0，服务结果 success，主进程 status=0；服务 runtime=26.892 s，CPU time=13.790 s。
- 单个 ManagerBasedRLEnv，Newton/MuJoCo Warp 后端，浮动 ANYmal D，PaceDCMotor 驱动器。
- 环境构造完成、reset 完成、env.close 完成、运行时退出；每个阶段均实时记录到 bounded_reset_result.json。
- 脚本显式 env.step 调用数为 0；未施加激励或悬吊外力。框架构造/reset 的内部初始化不等同于已验证物理时间步。
- 之前的 add_usd 参数 TypeError 未再出现，已从静态检查推进到实际加载路径验证。
- systemd-run 汇总 Memory peak=1.2M，与大型运行时的预期占用不相称，不将其作为准确 RAM 峰值证据；未测显存峰值。内存额度证据来自进程内 cgroup 文件，不以该峰值推断资源风险。
- 结束后读取 systemctl show 时瞬态单元已 inactive，显示默认 infinity；不将已被回收单元的默认值当作运行期间配置。实际 cgroup 设置已在运行时导入前读取保存。

## 限制及下一步

本次通过不能证明唤醒黑屏已修复、动态绳索模型正确或长期 GPU 稳定。没有恢复 60 s 动态实验。建议下一次单独批准同样资源限制下最多 20 个物理步（dt=0.0025 s，共 0.05 s）的合成悬吊耦合探针，检查受力接口、有限状态、主链几何及挂钩平衡残差；失败立即退出，不自动重试。此次不执行该建议。
