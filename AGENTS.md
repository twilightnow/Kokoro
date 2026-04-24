# AGENTS.md

给 Codex / Claude / Gemini 等 coding agent 使用的项目级指南。修改代码前先阅读本文件和 `README.md`。

## 项目要点

Kokoro 是桌面 AI 人格伴侣原型，支持 CLI 对话和 Tauri + Vue 桌面悬浮窗。

```text
CLI / Tauri + Vue -> FastAPI sidecar (Python) -> LLM Provider
```

核心能力：有状态角色扮演对话、情绪状态机、工作/摘要/长期记忆、环境感知、多角色配置、TTS、桌面悬浮交互。

## 环境与命令

环境要求：Python 3.10+、Node.js 18+；桌面模式还需要 Rust、Tauri 环境和 WebView2。运行前参考 `.env.example` 创建 `.env`，至少配置一个可用 LLM provider。

```bash
pip install -r requirements.txt
npm install
npm install --prefix frontend

python main.py
python main.py --debug
python main.py --perception
python main.py --replay data/logs/<file>.jsonl

npm run dev:all
npm run sidecar
npm run frontend:dev
npm run tauri:dev

python -m unittest discover -s tests -v
npm run build --prefix frontend
```

长输出命令优先用 `rtk` 包裹，例如 `rtk git status`、`rtk git diff`、`rtk npm test`。

## 关键目录

```text
characters/            角色配置和资源
data/                  本地数据、记忆、日志
docs/desgin/           设计文档，目录名当前拼写为 desgin
frontend/              Vue 3 + Vite 前端
src/api/               FastAPI sidecar、路由、schema
src/application/       对话编排
src/capability/        LLM / TTS 等外部能力封装
src/memory/            工作、摘要、长期记忆
src/perception/        环境感知、窗口/输入事件、触发规则
src/personality/       角色 schema、情绪状态机、prompt 构建
src-tauri/             Tauri 桌面壳
tests/                 Python 单元测试
```

## 架构约定

- 角色配置位于 `characters/<name>/personality.yaml`，schema 在 `src/personality/character.py`。
- 新增角色通常只新增角色配置和必要资源，不为单个角色改核心代码。
- 情绪状态机在 `src/personality/emotion.py`，prompt 拼装在 `src/personality/prompt_builder.py`；新增情绪要同步检查枚举、触发规则、prompt 和测试。
- 对话编排在 `src/application/conversation_service.py`，provider 细节集中在 `src/capability/llm.py`。
- LLM provider 通过 `.env` 的 `LLM_PROVIDER`、`LLM_MODEL` 和对应 key 控制；不要为了临时测试修改代码默认值。
- FastAPI 入口在 `src/api/server.py` / `src/api/app.py`，路由拆在 `src/api/routes/`。
- 前端只通过 sidecar API 与后端通信，不硬编码 provider key 或模型密钥。

## 开发约束

- 保持改动聚焦，优先复用已有服务、schema、测试工具和目录结构。
- 不提交真实 API key、token、个人路径或本地运行数据。
- 未明确要求时，不修改 `.env`、`data/`、`logs/`、`.venv/`、`node_modules/`、`frontend/node_modules/`。
- 不删除或重写用户已有角色数据、记忆数据、日志数据。
- 新增依赖必须说明理由，并同步更新依赖文件。
- 涉及 API schema、路由返回值或前后端契约时，同时检查 Python API、前端调用点和测试。
- 涉及记忆、人格、情绪、prompt 的改动要谨慎，避免破坏角色一致性和历史数据兼容性。
- 发现 README、`.env.example`、测试和代码约定冲突时，以代码和测试为准，必要时同步文档。

## 测试要求

常规优先运行：

```bash
python -m unittest discover -s tests -v
```

按改动范围补充：

- `src/personality/`：运行 `tests/test_personality.py`，必要时补角色配置测试。
- `src/memory/`：运行 `tests/test_memory.py`。
- `src/capability/llm.py`：运行 `tests/test_llm.py`，避免真实网络调用进入单元测试。
- `src/api/`：运行 `tests/test_api.py`，并检查前端 API 调用。
- `src/perception/`：运行 `tests/test_perception.py`。
- 前端：运行 `npm run build --prefix frontend`。
- 桌面壳：除构建外，手动验证 Tauri 启动。

如果本地缺少环境、依赖或密钥导致无法完整验证，最终说明必须列出未运行项和原因。

