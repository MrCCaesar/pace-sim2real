# 保存已评估最佳候选及其匹配响应

Status: Accepted for the explicitly approved decision in CR2 Q19; detailed interfaces were subsequently approved in Q23.

## Context / problem

旧mean文件属于分布均值，而best_trajectory来自某个采样候选，旧代均值也可能误配最新轨迹。

## Alternatives

继续独立文件并猜测配对；额外评估最终均值；保存全程已评估最佳候选及对应响应。

## Decision and rationale

选择全程最佳已评估候选为主结果，成套保存参数、两组轨迹、误差、代数及身份；均值仅作诊断，绘图读取匹配记录。

## Consequences / trade-offs

无需额外均值回放；版本化结果消费者需迁移。无法证明配对的旧结果须明确提示，不能伪造准确配对。

## Evidence

Issue #4 research.md / spec.md and installed-source investigation; cr2-research-results.json records feasibility experiments. These are decisions for future implementation, not claims that production code already conforms.

## Approval reference

用户Q19：“接受，以最佳实测候选为主”。

Final interface approval: Q23 “批准最终契约及两个必要文件”; concrete contracts are recorded in .scratch/issue_4/interfaces.md. No implementation-stage transition implied.
