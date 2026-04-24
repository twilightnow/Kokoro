---
tags:
  - Kokoro
  - roadmap
  - personality
status: done
created: 2026-04-21
updated: 2026-04-24
---

# Phase 1.5 — CLI 收尾 ✅

**架构关注点**：人格层 / CLI 验收

**目标**：让 CLI 版本达到可信的人格验收标准，不留"技术债进 Phase 2"。

**现状**：全部完成。103 个单元测试通过，工具脚本可用。

## 任务清单

- [x] **固化角色配置 schema**：`character.py` dataclass 字段补全校验，`loader.py` 对缺字段给出明确错误提示，而不是 KeyError
- [x] **prompt 长度估算与告警**：`prompt_builder.py` 在 debug 模式下打印 system prompt token 估算值，超 600/1200 分级告警
- [x] **人格层单元测试补全**：40 个用例，覆盖 emotion / loader / prompt_builder 边界情况
- [x] **人格稳定性复盘脚本**：`python tools/analyze_session.py logs/<file>.jsonl`
- [x] **成本统计脚本**：`python tools/cost_summary.py logs/`

## 验收标准

1. ✅ 连续 10 轮对话，禁用词零命中
2. ✅ 情绪触发和衰减的单元测试全部通过
3. ✅ 复盘脚本能从现有日志文件正常输出报告

## 相关设计文档

- [人格层](../../desgin/人格层.md)
