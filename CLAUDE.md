# CLAUDE.md — Kokoro 项目开发指南

## 项目概述

Kokoro 是一个基于 Claude API 的桌面 AI 人格伴侣平台，核心是一个有状态的角色扮演对话循环。情绪、记忆、角色配置完全解耦，通过依赖注入组合。

## 常用命令

```bash
python main.py               # 启动对话
python main.py --debug       # 调试模式
python main.py --replay logs/<file>.jsonl  # 回放会话
```

## 架构关键点

- **角色配置** 在 `characters/<name>/personality.yaml`，YAML schema 由 `src/personality/character.py` 的 dataclass 定义
- **情绪状态机** 在 `src/personality/emotion.py`：`update()` 触发词匹配 → 情绪迁移；无命中则 `decay()`
- **System prompt** 由 `src/personality/prompt_builder.py` 在每轮对话时动态构建，包含当前情绪
- **工作记忆** (`src/memory/working_memory.py`) 上限 `max_rounds=10`，截断在每轮发送前执行
- **LLM 调用** 封装在 `src/capability/llm.py`；provider 通过 `.env` 中的 `LLM_PROVIDER` 指定，支持 API key 模式（anthropic / openai / gemini / deepseek / openrouter / copilot）和 CLI 模式（claude-cli / gemini-cli）
- **日志** 写入 `logs/`，每次运行独立 JSONL 文件，`session_log.py` 负责写入与摘要

## 开发规范

- 不要修改 `logs/` 下的文件
- 新增角色时只需新建 `characters/<name>/personality.yaml`，无需修改 `src/`
- `personality.yaml` 必须包含 `name`、`emotion_triggers`、`forbidden_words` 字段
- 情绪类型由 `emotion.py` 的枚举定义，新增情绪需同步修改 `prompt_builder.py`
- 切换 provider 只改 `.env` 中的 `LLM_PROVIDER`，切换模型只改 `LLM_MODEL`，不需要动代码

## 依赖

```text
anthropic>=0.40.0
pyyaml>=6.0
python-dotenv>=1.0.0
```

需要 Python 3.10+。
