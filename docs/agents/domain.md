# Domain docs

本仓库采用 single-context 布局：

- GLOSSARY.md：根目录领域术语表。
- adr/：根目录决策记录，遵循 AGENTS.md 的内容和审批要求。
- .scratch/issue_N/：Issue 的阶段工作文档与 status.md。

探索领域代码前，读取已有 GLOSSARY.md 和相关 ADR。
文件不存在时继续工作，不提前创建空白术语表或 ADR。
术语明确或需要记录重要决策时，再按批准的阶段创建。

输出使用术语表定义的名称，避免引入含义相同但名称不同的术语。
与已有 ADR 冲突时明确指出，不静默覆盖。
未经用户明确批准，不将 ADR 标为 Accepted。
更新决策时保留历史，通过新记录取代旧记录。
