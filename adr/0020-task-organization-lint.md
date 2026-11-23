# 强化学习任务组织规范的静态检查

**状态**　Accepted。Issue #22 Research 中，用户明确同意 Ruff 承担通用 Python 检查，使用独立 Python 静态检查处理包结构和配置到实现的引用关系。

**背景**　任务的 MDP 可以同时导出本地和上游定义。创建一个 rewards.py 即可满足目录存在性检查，即使某个奖励函数实际定义在环境配置中。全库存量代码也须通过适用检查。[需求 R4–R9](../.scratch/issue_22/requirements.md)

**决定与理由**　采用 Ruff 承担通用 Python 检查，用独立的 Python 静态检查处理项目级包结构，以及任务配置到实现定义之间的引用关系。通过 pre-commit 支持其他项目复用。若 agent 判断复用需要独立 GitHub 仓库，须说明必要性并单独申请，创建须经用户明确批准。该组合可利用已声明的开发依赖，以完整的相关源码处理跨模块关系。

**备选方案**　Flake8 插件能收到文件名和语法树，但仍需跨文件定位定义。目录和文本规则易于维护，可承担简单的包名检查，对别名、重导出和错放的实现覆盖有限。Ruff 当前不提供第三方 lint 插件接口。[Flake8 插件输入](https://flake8.pycqa.org/en/latest/plugin-development/plugin-parameters.html) · [Ruff 插件支持](https://docs.astral.sh/ruff/faq/#can-i-write-my-own-linter-plugins-for-ruff)

**影响与权衡**　独立检查需维护任务配置引用、源码存根与别名的解析，并随上游版本调整。动态绑定的处理和跨文件检查触发条件仍需明确。既有格式工具的保留范围、公共入口及完整验收命令留待 Specify。现阶段证据为源码和文档核对，尚无覆盖率或运行成本测量。[Issue #22 研究](../.scratch/issue_22/research.md)
