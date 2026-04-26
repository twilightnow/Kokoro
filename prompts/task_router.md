# 任务路由提示词模板

本文档用于记录 agent 如何判断任务类型，以及不同任务应读取哪些上下文。

## 任务类型

| 类型 | 触发条件 | 先读文档 |
|------|----------|----------|
| 新增或修改功能 | 用户要求新增、调整、删除功能 | `docs/overview.md`、`docs/roadmap.md`、`docs/design/`、`docs/contracts.md` |
| 修复 bug 或排查异常 | 用户描述错误、异常、失败或不符合预期 | `docs/runbook.md`、`docs/contracts.md`、`docs/design/`、`docs/changelog.md` |
| 修改提示词或 agent 行为 | 用户要求调整提示词、路由、输出格式或 agent 行为 | `prompts/`、`docs/contracts.md`、`evals/cases.jsonl` |
| 调整文档结构 | 用户要求新增、移动、删除或重组文档 | `README.md`、`AGENTS.md`、`docs/overview.md` |
| 增加评估用例 | 用户要求补充或修改评估 | `evals/cases.jsonl`、`prompts/`、`docs/contracts.md` |

## 路由原则

- 先选一个主任务类型。
- 只读取完成当前任务所需的最小文档。
- 如果任务同时影响接口、流程或输出格式，同步读取对应文档。
- 无法判断任务类型时，先列出歧义点，再请求确认。

## 提示词

```text
[填写：用于任务分类和上下文选择的提示词。]
```
