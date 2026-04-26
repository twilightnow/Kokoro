---
tags:
  - Kokoro
  - roadmap
  - memory
status: done
created: 2026-04-21
updated: 2026-04-24
---

# Phase 2A — 轻记忆 ✅

**架构关注点**：记忆层

**目标**：让她在对话结束后"记得住"，下次开聊时有上下文，不像每次重置。

## 设计原则

- 记得准，不乱记。只写入用户明确说出的事实，不写模型推断
- 首版不依赖 ChromaDB / mem0，用 JSON 文件，够用为止
- 记忆注入受 token budget 约束，不把 context 撑爆

## 任务清单

- [x] **`MemoryService.get_context(character_id, token_budget)`**：统一记忆注入入口，按优先级（长期 > 摘要）填充，超出则截断并写入 `TruncationLog`
- [x] **会话摘要自动生成**：`on_session_end()` 调用 LLM 生成摘要，写入 `memories/<character_id>/summaries.jsonl`
- [x] **长期记忆结构化写入**：LLM 提取用户显式陈述的事实，写入 `memories/<character_id>/facts.json`，冲突时标记 `pending_confirm`
- [x] **记忆注入 system prompt**：`prompt_builder.py` 接受 `MemoryContext`，在人格段之后注入"关于用户的记忆"段落
- [x] **被截断记忆日志**：`TruncationLog` 记录每次因 token 超限被丢弃的条目
- [x] **`MemoryService` 核心接口**：`get_context()`、`on_session_end()`、`working_memory` 落地并有测试

## 验收标准

1. ✅ 用户在第一次会话说"我叫 X"，第二次对话开口时她能在合适时机提到这个名字
2. ✅ 记忆注入不超过 token budget（`_token.py` 估算 + 截断逻辑验证）
3. ✅ 会话结束时摘要文件正常写入

## 相关设计文档

- [记忆层](../../desgin/03-记忆层.md)
