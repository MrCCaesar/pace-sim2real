# 按组缩放并加权混合响应误差

Status: Accepted for the explicitly approved decision in CR2 Q13; detailed interfaces were subsequently approved in Q23.

## Context / problem

腿角度与轮角速度单位不同，直接求和也会使通道较多的组占优。

## Alternatives

直接混合平方误差；按激励幅度或噪声归一化；可配置物理尺度及组权重。

## Decision and rationale

各组除以尺度后，在时间和关节维度取均方；按正组权重加权并除以有效组权重和。位置/速度尺度默认1 rad/1 rad/s，权重各1；另报告原单位 RMSE。纯腿只计算位置组。

## Consequences / trade-offs

尺度不是验收容差；操作者可调整相对重视程度。损失数值与旧按关节求和不同，旧绝对数值不可直接比较。

## Evidence

Issue #4 research.md / spec.md and installed-source investigation; cr2-research-results.json records feasibility experiments. These are decisions for future implementation, not claims that production code already conforms.

## Approval reference

用户：“13. 接受，可配置尺度与组权重”。

Final interface approval: Q23 “批准最终契约及两个必要文件”; concrete contracts are recorded in .scratch/issue_4/interfaces.md. No implementation-stage transition implied.
