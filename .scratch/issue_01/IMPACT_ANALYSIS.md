# Issue 01 impact analysis

分析在业务代码修改前完成；范围仅限 REQUIREMENTS.md 的 Isaac Lab 兼容性。

| 维度 | 直接或间接影响 | 分类 |
| --- | --- | --- |
| directly affected modules | `pace_sim2real_env_cfg.py` 的固定根关节字段及 Python 执行器开关；`pace_actuator.py` 参数解析；`cma_es.py` 仿真参数写入；采集/fit CLI；任务 agent 注册；PPO 配置；train/play 配置解析、导出和回放录像 | MUST CHANGE：机械性迁移失效 API |
| indirectly affected modules | ANYmal 子类、公共模板、chirp → fit → plot 数据链、checkpoint 和策略导出 | MAY CHANGE：仅在复现证明迁移必要时；产物结构 MUST NOT CHANGE |
| public APIs | 六个公共符号、两个 Gym ID、entry point、模板 robot 必填、policy 分项字典 | MUST NOT CHANGE；仅添加缺失的 RSL agent 注册，迁移上游 actor/critic schema |
| shared state | robot 配置深复制、执行器延迟缓冲、逐环境参数 | MUST NOT CHANGE；不得借用可变 robot 引用，RL 展平仅作用于 train/play 的配置实例 |
| concurrency impact | 向量环境参数仍按原关节/环境顺序写入；保留多 GPU seed/device 逻辑 | MUST NOT CHANGE；不新增线程、进程、锁或同步机制 |
| real-time impact | dt=0.0025、decimation=1、延迟算法、回放节流 | MUST NOT CHANGE；录像只在显式启用时迁移到 VideoRecorderCfg；无新增运行时阈值 |

MAY CHANGE：回归测试、可重复的 smoke harness 和验证记录；为了交付测试，仅对 .gitignore 中单个测试文件增加例外。

MUST NOT CHANGE：算法、默认值、参数顺序、bias 符号、摩擦语义、日志布局、plt.show()、包版本 0.2.0、平台列表、本地 editable 映射、验收阈值、无关命名与结构。原有需求、TEST_PLAN 和独立评审材料不改动。

基线探针复现了 articulation_props 类型变化、_parse_joint_parameter 移除、RslRlPpoActorCriticCfg 移除。按上游源码和实际 GPU smoke 验证参数写入及录像迁移。未采用已有分支引入的 robot 引用共享和公共观测展平。
