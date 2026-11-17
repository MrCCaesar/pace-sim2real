# Issue tracker

本仓库使用 GitHub Issues：
https://github.com/MrCCaesar/pace-sim2real

使用 gh CLI，并显式指定 --repo MrCCaesar/pace-sim2real，
避免将操作发送至上游仓库。

读取 Issue：
gh issue view N --repo MrCCaesar/pace-sim2real \
  --json number,title,body,labels,comments,url

列出 Issue：
gh issue list --repo MrCCaesar/pace-sim2real --state open

Issue 是初始需求来源，不代表实现授权。
用户已确认的需求和决策优先于旧 Issue 内容。

工作文档保存在 .scratch/issue_N/。
开始工作前读取现有文档和 status.md，遵守 AGENTS.md 的阶段审批规则。

创建、编辑、评论、关闭 Issue 等写操作须有用户明确授权。
多行正文写入临时文件，通过 --body-file 提交。

PRs as a request surface: no.

技能要求“发布到 issue tracker”时，指创建 GitHub Issue；
仍须遵守上述授权要求。
技能要求“获取相关 ticket”时，读取对应 Issue 及评论。
