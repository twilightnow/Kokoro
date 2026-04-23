# 2026-04-23 流式 TTS / 动作联动处理结果

## 本次完成

- WebSocket `/stream` 从“只发最终 done”改为真正发送 `thinking -> token* -> done`
- `LLMClient` 增加 `stream_chat()` 抽象，OpenAI Compatible / Anthropic provider 已接入真实增量输出
- 新增 `src/capability/tts.py` 与 `POST /tts`，默认 provider 为 `edge-tts`
- 前端新增句段级语音播放管线：收到 token 后按句段切分，边合成边排队播放
- 前端新增基础 STT 入口：输入栏可直接启停麦克风，识别完成后自动发送
- `SpritePanel` / `Live2DCanvas` / `Model3DCanvas` 已接入 `lipSyncLevel`
- 3D 模型支持配置驱动的 `mood_vmd_urls`、`morphs`、`mood_procedural_motions`
- Firefly 两套 `scene.json` 增加了程序化动作和 Morph 示例配置

## 自我 Review

- 已发现并修复：`three-stdlib` helper 的类型约束导致前端构建失败
- 已发现并修复：`Uint8Array` 泛型约束导致音频分析缓冲区类型错误
- 复查后未继续发现新的阻塞性编译/测试错误

## 实际执行与结果

### 1. Python API 测试

命令：

```powershell
f:/3_WorkSpace/1_GitHub/MyRepositories/Kokoro/.venv/Scripts/python.exe -m unittest tests.test_api -v
```

结果：`9` 个测试全部通过。

覆盖点：

- `/chat`
- `/state`
- `/health`
- `/stream` token 流式协议
- `/tts`

### 2. 前端构建

命令：

```powershell
Push-Location frontend; npm run build; Pop-Location
```

结果：构建成功。

备注：Vite 仍提示 `Live2DCanvas` / `Model3DCanvas` chunk 较大，但这是打包体积告警，不是构建失败。

### 3. TTS 真实冒烟

执行代码：

```python
import asyncio
from src.capability.tts import create_tts_client

async def main():
    client = create_tts_client()
    result = await client.synthesize('你好，这是 Kokoro 的语音合成冒烟测试。')
    print({'bytes': len(result.audio_bytes), 'voice': result.voice, 'content_type': result.content_type})

asyncio.run(main())
```

结果：

```python
{'bytes': 24768, 'voice': 'zh-CN-XiaoxiaoNeural', 'content_type': 'audio/mpeg'}
```

## 当前边界

- 真正的情绪 -> VMD 切换链路已经就绪，但仓库内还没有 `.vmd` 资源文件，所以当前主要依赖程序化动作兜底
- STT 目前使用浏览器语音识别接口，不是 Whisper；结构上已拆成独立 composable，后续可替换成 sidecar / Whisper provider
- `edge-tts` 需要联网访问微软语音服务；当前不是离线 TTS

## 后续建议

1. 给 Firefly 补一组实际 `.vmd` 文件，并在 `scene.json` 写入 `mood_vmds`
2. 如果你要本地离线 STT/TTS，再单独接 Whisper.cpp + 本地语音模型
3. 如果你要把这一套作为正式能力发布，再补 sidecar 打包和前端设置页开关