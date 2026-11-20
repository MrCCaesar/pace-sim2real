# 独立回放入口与采集共用仿真逻辑

**状态**　Accepted。用户在 Issue #4 CR8 中指定独立入口、共用仿真逻辑，并在 Explore Q2 选择直接移除旧回放入口。用户在 Specify 答复“批准 Q4、Q5,配套接口”，确认 Q4 的入口与内部职责边界。

**背景**　Isaac Lab 采集使用固定物理参数生成参考数据，回放从已评估的拟合结果恢复参数并验证响应。两个操作有不同的输入校验与输出规则，拆分前由同一入口的模式分支控制。[拆分前入口](https://github.com/MrCCaesar/pace-sim2real/blob/d4f33f25558f4566ae64f0a08401bbd605db4f4c/scripts/pace/data_collection.py#L97)

**备选方案**　两个脚本可分别编排各自工作流，使用同一组仿真例程；也可把现有模式分支整体移入共用运行器，由两个入口选择模式。后者迁移时较少移动执行顺序，但常规采集仍会依赖回放分支，维护采集失败和回放另存两类行为时需要同时理解两个模式。

**决定及理由**　两个入口各自编排。采集拥有固定参数、采集分组和默认文件写入；回放拥有结果选择、轨迹来源、物理兼容性、误差报告及另存保护。两者共享需要数值一致的扫频、关节映射、执行器工况、步进前采样，并复用同一套仿真启动与释放约定。具体契约见 [CR8 接口](../.scratch/issue_4/interfaces.md#cr8-采集与回放接口)。[共用仿真路径](../src/pace_sim2real/utils/trajectory_simulation.py) · [全任务动作与保持目标](../src/pace_sim2real/utils/subset_control.py#L104)

**影响与权衡**　旧回放调用需迁移。独立入口使回放的显式另存与采集的默认写入分别可见，但拆分可能改变后端解析、复位与初态写入、输出落盘的先后次序。全量采集与 v2 文件回放各有既有初态约定，需有回归证据才能合并对应的执行分支。[既有回放验证](../tests/test_fit_replay.py#L199) · [回放落盘顺序](../scripts/pace/replay.py)

**批准依据与证据**　已确认的用户需求见 [CR8-R1 至 R4](../.scratch/issue_4/requirements.md#cr8-独立回放入口与部分关节采集explore--draft)。Research 阶段的源码核对见 [CR8 研究记录](../.scratch/issue_4/research.md#cr8-独立回放与部分关节采集)。

**Specify 决定**　两个脚本分别编排采集与回放，共用的 Isaac Lab 运行例程放入 `pace_sim2real.utils.trajectory_simulation`，沿用既有的分组、子集控制与结果加载模块。Q3 已确认固定参数在部分采集中的作用范围，内部职责由用户在 Q4 批准。[Q4 与验收条件](../.scratch/issue_4/spec.md#cr8-独立回放与部分关节采集specify--approved) · [物理参数决策](0017-partial-collection-parameters.md)
