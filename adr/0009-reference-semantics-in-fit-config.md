# 参考数据语义由拟合配置声明

Status: Accepted for the explicitly approved decision in CR2 Q17; detailed interfaces were subsequently approved in Q23.

## Context / problem

三/五字段文件无法自行证明关节顺序、时间解释或偏置物理语义；添加元文件可提供来源记录但增加管理负担。

## Alternatives

数据内嵌元数据；同名JSON侧车；完全由拟合配置声明。

## Decision and rationale

采用用户指定的配置声明方式，不新增数据元文件或改变原张量字段；将解析后的配置保存在拟合结果中。

## Consequences / trade-offs

声明依赖操作者正确性，不能根据文件名猜测或保证声明真实。Q20 已批准旧 measurement-only 数据不兼容、需重新采集；不得仅平移保存值伪造新闭环响应。

## Evidence

Issue #4 research.md / spec.md and installed-source investigation; cr2-research-results.json records feasibility experiments. These are decisions for future implementation, not claims that production code already conforms.

## Approval reference

用户Q17：“不增加元数据，全部由拟合配置声明”。

Additional approval Q20: “接受，旧模型数据需重新采集,不需要兼容”。

Final interface approval: Q23 “批准最终契约及两个必要文件”; concrete contracts are recorded in .scratch/issue_4/interfaces.md. No implementation-stage transition implied.
