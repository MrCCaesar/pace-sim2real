# 统一关节分组映射与参数布局

Status: Accepted for the explicitly approved decision in CR2 Q16/Q18; detailed interfaces were subsequently approved in Q23.

## Context / problem

Articulation 索引不等于动作列；旧优化器给轮分配了位置偏置维度，摩擦计数还可能重复轮关节。

## Alternatives

沿用全关节位置假设；采集和拟合各维护映射；共用小型数据和名称映射契约。

## Decision and rationale

保留 leg_order/wheel_order，纯腿 joint_order 兼容归一化，混合 combined order=legs+wheels。共用验证与独立测量/动作映射，处理支持的动作缩放偏移。参数块为armature[J],damping[J],friction[J],bias[L],delay[1]，可选末尾ratio[J]。

## Consequences / trade-offs

X5基础维数61、12腿49；未知动作类型与声明冲突显式失败。无轮偏置、无重复轮计数。helper公开签名/路径须最终接口审阅。

## Evidence

Issue #4 research.md / spec.md and installed-source investigation; cr2-research-results.json records feasibility experiments. These are decisions for future implementation, not claims that production code already conforms.

## Approval reference

用户Q16：“接受该布局”；Q18：“接受该共用模块和兼容规则”。

Structure constraint: user subsequently required only necessary structure changes/new files. Retain existing modules/classes; final detailed proposal limits new implementation files to one shared helper and one focused test file, subject to Q23 review.

Final interface approval: Q23 “批准最终契约及两个必要文件”; concrete contracts are recorded in .scratch/issue_4/interfaces.md. No implementation-stage transition implied.

Implementation clarification approved by user (2026-11-17): Newton configuration validation warns and disables separate dynamic friction identification, removing appended ratio bounds before CMA construction. The earlier specification's rejection requirement is superseded; direct unsupported optimizer calls remain guarded. Rationale: Newton cannot set separate dynamic friction, so allocating these optimization variables would be ineffective. PhysX retains optional ratio variables.
