# Kokoro

桌面 AI 人格伴侣原型，支持两种运行方式：

- CLI 对话
- Tauri + Vue 桌面悬浮窗

当前实现包含轻量情绪状态机、会话记忆、环境感知和多角色切换。

## 运行结构

```text
CLI / Tauri + Vue
        |
        v
FastAPI sidecar（Python）
        |
        v
LLM Provider
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
npm install
npm install --prefix frontend
```

### 2. 配置 `.env`

参考 `.env.example`，最少需要配置一个可用的 LLM。

示例：

```env
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat
DEEPSEEK_API_KEY=your_key_here
```

也支持统一变量 `LLM_API_KEY`。如果同时配置了多个 provider 的 key，建议显式设置 `LLM_PROVIDER`。

## 启动方式

### CLI

```bash
python main.py
```

常用参数：

```bash
python main.py --debug
python main.py --perception
python main.py --replay data/logs/<file>.jsonl
```

### 桌面模式

一键启动：

```bash
npm run dev
npm run dev:kill  # 清理调试残留的 sidecar / Vite / Tauri 进程
```

分开启动：

```bash
npm run sidecar   # Python sidecar，默认 18765
npm run dev       # Vite + Tauri
```

说明：

- Tauri 启动时会自动拉起 sidecar；开发时也可以用 `npm run sidecar` 单独调试后端
- 桌面模式依赖 Node.js 18+、Rust、WebView2
- 打包 Python sidecar：`npm run sidecar:build`，产物位于 `dist/kokoro-sidecar.exe`
- 管理界面提供健康检查、基础设置和脱敏诊断导出

## 支持的 LLM Provider

API Key 模式：

- `deepseek`
- `openai`
- `anthropic`
- `gemini`
- `openrouter`
- `copilot`

CLI 模式：

- `claude-cli`
- `gemini-cli`
- `codex-cli`

具体默认模型和环境变量见 [src/capability/llm.py](/C:/WorkSpace/6_Source/2_VScode/99_gitProject/Kokoro/src/capability/llm.py)。

## 主要功能

- 情绪状态机：关键词触发 + 持续轮数衰减
- 会话记忆：工作记忆、摘要记忆、长期事实记忆
- 环境感知：窗口标题、活跃状态、时间段触发
- 桌面交互：透明悬浮窗、托盘、边缘吸附、点击穿透
- 多角色：`characters/<name>/personality.yaml`

## 关键目录

```text
characters/            角色配置
data/                  本地数据与日志
docs/desgin/           设计文档
frontend/              Vue 前端
src/                   Python 主逻辑
src/api/               FastAPI sidecar
src/application/       对话编排层
src/personality/       人格层
src/memory/            记忆层
src/perception/        感知层
src/capability/        LLM 能力层
src-tauri/             Tauri 桌面壳
tests/                 单元测试
main.py                CLI 入口
```

## 测试

```bash
python -m unittest discover -s tests -v
```
