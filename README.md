# Kokoro

基于命令行的 AI 角色对话 Demo，支持情绪状态、短期记忆和会话日志。支持 `deepseek`、`openai`、`anthropic`、`gemini`、`openrouter` 多供应商。

## 快速开始

```powershell
pip install -r requirements.txt
Copy-Item .env.example .env
python main.py
```

## 配置

编辑 `.env`，最常用的 DeepSeek 配置：

```env
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat
DEEPSEEK_API_KEY=your_key_here
```

也支持统一写法 `LLM_API_KEY`。多个供应商 key 共存时必须显式设置 `LLM_PROVIDER`。

## 运行

```powershell
python main.py              # 正常对话
python main.py --debug      # 调试模式
python main.py --replay logs\<file>.jsonl  # 回放日志
```

## 测试

```powershell
python -m unittest discover -s tests -v
```

## 支持的供应商

| Provider | `LLM_PROVIDER` | 默认模型 | API Key 变量 |
| --- | --- | --- | --- |
| DeepSeek | `deepseek` | `deepseek-chat` | `DEEPSEEK_API_KEY` |
| OpenAI | `openai` | `gpt-5-mini` | `OPENAI_API_KEY` |
| Anthropic | `anthropic` | `claude-haiku-4-5-20251001` | `ANTHROPIC_API_KEY` |
| Gemini | `gemini` | `gemini-2.5-flash` | `GEMINI_API_KEY` |
| OpenRouter | `openrouter` | `openai/gpt-5-mini` | `OPENROUTER_API_KEY` |
