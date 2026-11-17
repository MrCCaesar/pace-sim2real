# 统一归一化扫频中心语义

Status: Accepted for the formula amendment explicitly requested by the user during CR2 Research. Initialization/config/test migration remains pending Specify/Implement.

## Context / problem

CR1 原生采集把 position_centers 解释为物理角度，使用 center + amplitude*sin 后整体乘方向。Isaac Lab 采集采用先加中心系数再整体缩放的公式。用户已修改原生公式并明确要求与 Isaac Lab 保持一致。

## Alternatives

保留两套中心约定并显式换算；统一为物理中心；或统一为归一化中心系数。前两者不符合本次用户明确指定的公式。

## Decision and rationale

采用 (centers + sin(phase)) * amplitudes * directions，centers 在此之前不乘方向符号。实际物理扫频中心为 centers * amplitudes * directions。该公式由用户直接指定，取代 CR1 的物理中心解释；不自行回退用户代码。

## Consequences / trade-offs

相同数值配置可能产生不同的物理中心，旧配置/文档/测试不能直接宣称兼容。初始化位置、控制量和历史指令需与首个目标一致；当前原生实现仍使用未缩放 centers 初始化，尚待修正。用户未要求变更具体系数、幅度或方向数组。如何标识/迁移配置、统一术语及验证初始化将在后续 Specify 明确。已完成 CR1 验证只适用于当时提交。

## Evidence

当前 scripts/pace/mujoco_collection.py 的 centers 和 desired 表达式，以及 scripts/pace/data_collection.py 的 leg_trajectory 生成。研究记录见 .scratch/issue_4/research.md。

## Approval reference

用户原话：“centers单独乘的direction已经去除，按照现在的(centers + np.sin(phase[:, None])) * amplitudes * directions，这样与data_collection.py中轨迹的生成保持一致”。此批准仅覆盖明确的轨迹语义修订，不代表批准其他 CR2 架构或提前实施。
