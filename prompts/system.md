# 系统提示词模板

本文档用于记录项目级根系统提示词。只有会影响 agent 全局行为的规则才写在这里。

## 使用方式

- 将稳定、长期有效、跨任务通用的行为规则写入本文档。
- 任务分类规则写入 `prompts/task_router.md`。
- 输出结构规则写入 `prompts/output_format.md`。
- 设计文档生成规则写入 `prompts/design_doc_prompt.md`。

## 提示词

```text
[填写：项目级系统提示词。]
```

## 变更注意

- 修改全局行为后，检查 `evals/cases.jsonl` 是否需要新增或更新用例。
- 若修改影响输入输出结构，同步更新 `docs/contracts.md`。
