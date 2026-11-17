# 统一反馈与测量的编码器偏置

Status: Accepted for physical semantics by explicit CR2 Specify Q11. Native target-offset mechanism and initial states were additionally approved in Q14/Q15; Q20 additionally rejects old measurement-only-model data and requires recollection.

## Context / problem

Isaac Lab 的 PaceDCMotor 在 PD 反馈中使用 q-b，采集和拟合位置同样使用 q-b。原生 MuJoCo 旧采集只在保存的位置中减去 b，PD 使用真实 q。两者具有不同的闭环响应，不能仅凭相同数据字段认定物理模型一致。

## Alternatives

保留来源相关的两种偏置模式并显式配置；统一为仅测量偏置；统一为 Isaac Lab 原有的反馈和测量均减偏置。用户选择第三种，拒绝本轮提出的双模式方案。

## Decision and rationale

后续 Isaac Lab、原生 MuJoCo 采集与拟合统一采用腿关节反馈 q-b、位置测量 q-b。轮关节不引入位置或速度偏置参数。保持用户要求的统一反馈语义，避免在两个来源之间隐含切换物理模型。该决定不授权将随机测量噪声加入反馈。

## Consequences / trade-offs

取代 ADR0001 中“偏置仅影响原生测量，不影响反馈”的范围；其余原生 PD、限幅、延迟和碰撞模型约束不因此废除。原生采集实现、初始化及历史控制、规格、示例和回归测试均需迁移。Q14 已批准向原生位置伺服提交 desired+b，同时保存原始 desired；仅在执行器传动、控制限幅及历史初始化满足等价条件时成立，必须在实施中验证这些约束。Q15 批准拟合初始化：腿物理角度为首条测量加候选偏置，轮速取首条测量；轮角度和腿速度取任务初始配置并记录、每轮恢复。

已有 measurement-only 原生数据记录的是旧闭环响应，事后平移数组不能使其成为新模型的数据。Q17 选择由拟合配置声明来源语义；Q20 批准旧模型数据不兼容、需要重新采集，不新增数据元文件。现有 Isaac Lab 历史数据的时间解释与本偏置决定相互独立。

## Evidence

Installed/current `src/pace_sim2real/utils/pace_actuator.py` supplies `joint_pos - encoder_bias` to DCMotor; Research records native measurement-only handling and its physical discrepancy. Earlier probes establish backend feasibility, not this future native implementation's equivalence.

## Approval reference

用户原话：“11. 统一为Isaac Lab 原有模式在 PD 反馈和保存的位置中都减去偏置的方式”。仅批准明确的物理语义；没有批准所有后续接口、迁移策略或提前实施。

Q14 用户回答“接受”；Q15 回答“接受，采用任务配置初始值”。这批准了上述控制输入与初始化方案，兼容性验证仍须在实施/验证阶段完成。
