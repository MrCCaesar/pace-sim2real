# 显式解释参考数据时间

Status: Accepted for the explicitly approved decision in CR2 Q12; detailed interfaces were subsequently approved in Q23.

## Context / problem

旧采集的 endpoint-inclusive linspace 标签不等于真实采样时刻，直接每行执行 env.step 又可能忽略 decimation。

## Alternatives

自动重采样；一律拒绝历史数据；显式 strict/legacy_index 两种时间解释。

## Decision and rationale

新数据以实际采样时刻保存；默认 strict，间隔须匹配 env.step_dt。历史模式须提供真实间隔，按索引构造有效时间，保留原始标签供溯源。不自动重采样。

## Consequences / trade-offs

兼容历史文件需要操作者提供真实间隔，不能从错误标签恢复未知物理时间。浮点容差和短数据限制留在接口最终审阅。

## Evidence

Issue #4 research.md / spec.md and installed-source investigation; cr2-research-results.json records feasibility experiments. These are decisions for future implementation, not claims that production code already conforms.

## Approval reference

用户：“12. 接受，历史数据显式指定真实间隔”。

Final interface approval: Q23 “批准最终契约及两个必要文件”; concrete contracts are recorded in .scratch/issue_4/interfaces.md. No implementation-stage transition implied.
