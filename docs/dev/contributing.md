# Isaac Lab 环境组织检查

在 Python 3.12 开发环境中运行以下命令。独立检查器只读取源码、存根和资源路径；通用 Python 规则沿用本项目的 Ruff 配置。

```bash
uv sync --locked --group dev
uv run isaaclab-task-lint
uv run ruff check .
uv run pre-commit run --all-files
```

任务位于 `src/<项目包>/tasks/<任务>/`，PACE、Direct 单智能体和 Direct 多智能体的家族目录分别形如 `pace/`、`walk_direct/` 和 `walk_marl_direct/`，机器人变体在 `config/<robot>/`，自定义 MDP 按实际类别组织到 `mdp/`。可复用的框架扩展位于 `src/<项目包>_isaaclabs/` 下相应职责目录。检查器接受 `--root PATH` 和 `--package NAME`；默认从当前目录的 pyproject.toml 读取项目名。

在消费项目的 `.pre-commit-config.yaml` 中加入以下配置，并确保 PATH 中的 `python3` 为 Python 3.12。示例的 `rev` 固定到 Issue #22 的实现提交。pre-commit 从该修订加载检查器，在消费项目的工作树中检查源码，无需安装 PACE 或 Isaac Lab。

```yaml
repos:
  - repo: https://github.com/MrCCaesar/pace-sim2real
    rev: 6669745cb8e8c8c1c03c55607166a5bd66e46b9a
    hooks:
      - id: isaaclab-task-lint
```

`pre-commit run isaaclab-task-lint --all-files` 与直接调用检查器采用同一套规则。每次扫描完整的相关项目源码，包括仅删除文件的变更。诊断给出绑定或定义的位置。ORG005 表示绑定未解析，ORG008 表示发现的组件缺少归属规则。组织违规、未解析及缺少规则的计数均为零时退出 0；规则失败退出 1；输入、配置或源码读取失败退出 2。

所有消费项目均采用 [Isaac Lab v3.0.0 正式版外部项目生成器](https://github.com/isaac-sim/IsaacLab/blob/v3.0.0/tools/template/generator.py) 的布局。框架导出名索引从本地 Isaac Lab Git 仓库中的正式版提交读取，可用 `python scripts/generate_isaaclab_lint_catalog.py ../IsaacLab` 重建。更新组织规则时，为同一职责补充合法位置、错放定义或断链的测试，再用 `uv run pytest -q tests/test_task_organization.py` 检查。运行时工厂、无法定位的资源及不明确的导出会给出失败诊断，修复位置以报告的绑定和定义为准。
