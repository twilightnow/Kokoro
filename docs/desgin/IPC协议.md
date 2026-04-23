# Kokoro Sidecar IPC 协议

这份文档只记录当前代码真实存在的协议。

## 基本信息

- sidecar：FastAPI
- 默认地址：`127.0.0.1`
- 默认端口：`18765`
- 启动命令：`python -m src.api.server`

当前项目里，sidecar 需要单独启动，Tauri 还没有自动拉起它。

## CORS

当前允许的来源：

- `tauri://localhost`
- `http://localhost:1420`
- `http://127.0.0.1:1420`
- `http://localhost:5173`
- `http://127.0.0.1:5173`

## HTTP 接口

### `POST /chat`

请求：

```json
{
  "message": "你好"
}
```

响应：

```json
{
  "reply": "……笨蛋，你终于开口了啊。",
  "mood": "normal",
  "mood_changed": false,
  "flagged": false,
  "turn": 1,
  "usage": {
    "input_tokens": 100,
    "output_tokens": 30,
    "provider": "openai",
    "model": "gpt-4o-mini"
  }
}
```

说明：

- `message` 长度限制为 `1-2000`
- `usage` 在 CLI 类 provider 下可能为 `null`
- LLM 失败时返回 `503`

### `GET /state`

响应：

```json
{
  "character_id": "asuka",
  "character_name": "惣流·明日香·兰格雷",
  "display": {
    "mode": "model3d"
  },
  "mood": "normal",
  "persist_count": 0,
  "turn": 3,
  "memory_summary_count": 1,
  "memory_fact_count": 2,
  "session_token_total": {
    "input": 120,
    "output": 56
  }
}
```

说明：

- `display` 是当前角色的展示配置，前端据此决定渲染 placeholder / Live2D / 3D
- `memory_summary_count` 和 `memory_fact_count` 是当前最近一次记忆上下文的注入数量
- 不是全量历史统计

### `GET /health`

响应：

```json
{
  "status": "ok",
  "character": "惣流·明日香·兰格雷",
  "version": "1.0.0"
}
```

### `POST /switch-character?name=<id>`

示例：

```text
POST /switch-character?name=rei
```

响应：

```json
{
  "character_id": "rei",
  "character_name": "绫波丽",
  "display": {
    "mode": "live2d"
  },
  "status": "ok"
}
```

说明：

- 参数 `name` 是 `characters/<name>/personality.yaml` 中的目录名
- 切换时会先执行旧会话收尾，再重建新的 `ConversationService`

## WebSocket 接口

### `GET ws://127.0.0.1:18765/stream`

客户端发送：

```json
{ "message": "你好" }
```

服务端当前会发这几类帧：

```json
{ "type": "thinking", "content": "" }
```

```json
{ "type": "token", "content": "角色回复增量文本" }
```

```json
{
  "type": "done",
  "content": "角色回复文本",
  "mood": "happy",
  "flagged": false
}
```

```json
{ "type": "error", "content": "LLM 调用失败" }
```

补充说明：

- 前端类型里有 `proactive`，但当前 sidecar 不会发送这个帧
- 当前真实可依赖的是 `thinking`、`token`、`done`、`error`

### `POST /tts`

请求：

```json
{
  "text": "你好，这是语音播放测试。",
  "voice": "zh-CN-XiaoxiaoNeural",
  "rate": "+0%",
  "volume": "+0%"
}
```

响应：

- `200 audio/mpeg`
- 响应体为 mp3 二进制音频

说明：

- `text` 长度限制为 `1-400`
- `voice`、`rate`、`volume` 都是可选参数；不传时走环境变量或默认值
- 当前实现为句段级调用，适合前端收到 token 后分段合成并连续播放

## 模块边界

为了保持简单，当前 IPC 层只负责协议，不负责业务决策：

- 路由层不直接写人格逻辑
- 路由层不操作记忆文件
- 所有真实对话处理都下沉到 `ConversationService`

如果后续加新接口，优先保持这一条，不要把 sidecar 路由写成第二套业务层。
