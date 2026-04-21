# Kokoro Sidecar IPC 协议文档

---

## 概述

Kokoro sidecar 是一个轻量 FastAPI 进程，与 Tauri 前端通过本地 HTTP/WebSocket 通信。

- **默认端口**：`18765`（可通过 `--port` 参数覆盖）
- **绑定地址**：`127.0.0.1`（仅本地访问，不暴露到公网）
- **启动命令**：`python -m src.api.server`

---

## 跨域配置

允许以下来源：

- `tauri://localhost`
- `http://localhost:1420`
- `http://127.0.0.1:1420`

---

## 接口列表

### `POST /chat` — 同步对话

**请求**

```json
{
  "message": "用户输入的内容"
}
```

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `message` | string | 1–2000 字符 | 用户输入 |

**响应（200 OK）**

```json
{
  "reply": "角色回复文本",
  "mood": "happy",
  "mood_changed": true,
  "flagged": false,
  "turn": 3,
  "usage": {
    "input_tokens": 120,
    "output_tokens": 45,
    "provider": "anthropic",
    "model": "claude-3-5-haiku-20241022"
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `reply` | string | 角色回复内容 |
| `mood` | string | 本轮结束后的情绪 |
| `mood_changed` | bool | 本轮是否发生情绪变化 |
| `flagged` | bool | 回复中是否出现禁用词 |
| `turn` | int | 当前轮次编号（从 1 开始） |
| `usage` | object \| null | token 用量（CLI/CLI 模式下为 null） |

**错误响应**

- `422 Unprocessable Entity`：`message` 不满足约束（空或超长）
- `503 Service Unavailable`：LLM 调用失败

---

### `GET /state` — 当前状态

**响应（200 OK）**

```json
{
  "character_name": "惣流·明日香·兰格雷",
  "mood": "normal",
  "persist_count": 0,
  "turn": 5,
  "memory_summary_count": 2,
  "memory_fact_count": 1
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `character_name` | string | 当前角色名 |
| `mood` | string | 当前情绪 |
| `persist_count` | int | 情绪剩余持续轮数 |
| `turn` | int | 已完成轮数 |
| `memory_summary_count` | int | 当前注入的摘要条数 |
| `memory_fact_count` | int | 当前注入的长期事实条数 |

---

### `GET /health` — 健康检查

**响应（200 OK）**

```json
{
  "status": "ok",
  "character": "惣流·明日香·兰格雷",
  "version": "1.0.0"
}
```

---

### `WebSocket /stream` — 流式对话

**连接**：`ws://127.0.0.1:18765/stream`

**客户端发送（JSON）**

```json
{ "message": "用户输入" }
```

**服务端推送（StreamChunk）**

每次对话产生两条消息：

1. 思考中帧（立即）：
```json
{ "type": "thinking", "content": "", "mood": null, "flagged": null }
```

2. 完成帧（LLM 返回后）：
```json
{
  "type": "done",
  "content": "角色回复文本",
  "mood": "happy",
  "flagged": false
}
```

**错误帧**：
```json
{ "type": "error", "content": "错误描述", "mood": null, "flagged": null }
```

**`type` 枚举值**

| 值 | 触发时机 | content 含义 |
|----|---------|-------------|
| `thinking` | LLM 调用开始前 | 空字符串 |
| `done` | LLM 返回后 | 完整回复文本 |
| `error` | 格式错误或 LLM 失败 | 错误描述 |
| `token` | 未来流式扩展 | 单个 token 文本 |

> **流式升级路径**：当 LLM provider 支持流式输出后，服务端将逐 token 发送 `type="token"` 帧，最后以 `type="done"` 结束。客户端检测 `done` 帧即可，无需改动接收逻辑。

---

## Tauri 侧调用示例（伪代码）

```typescript
// HTTP 同步对话
const response = await fetch("http://127.0.0.1:18765/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message: userInput }),
});
const data = await response.json();
// data.reply, data.mood, data.flagged ...

// WebSocket 流式对话
const ws = new WebSocket("ws://127.0.0.1:18765/stream");
ws.onopen = () => ws.send(JSON.stringify({ message: userInput }));
ws.onmessage = (e) => {
  const chunk = JSON.parse(e.data);
  if (chunk.type === "thinking") showTypingIndicator();
  if (chunk.type === "done") displayReply(chunk.content);
  if (chunk.type === "error") showError(chunk.content);
};
```

---

## sidecar 启动/关闭时序

Tauri 应用通过 `Command::new("python").args(["-m", "src.api.server", "--prod"])` 启动 sidecar：

1. **应用启动**：Tauri `setup` 钩子启动 sidecar 子进程
2. **就绪检测**：轮询 `GET /health` 直到返回 200
3. **正常通信**：通过 HTTP 或 WebSocket 交互
4. **应用关闭**：Tauri `on_window_event(CloseRequested)` 发送 `SIGTERM` 给 sidecar 子进程，FastAPI lifespan 清理资源
