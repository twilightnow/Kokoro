# 3D 模型支持

## 目标
将 3D 角色资源作为 Kokoro 表现层的 `model3d` display provider 接入，并保证资源失败不阻断对话、记忆、人格、关系或 TTS 链路。

## 范围
### 包含
- 定义 `model3d` provider 的职责边界。
- 定义角色包中的 3D 资源目录、`manifest.yaml` 入口字段和单皮肤 `scene.json` 字段。
- 定义皮肤选择、状态映射、资源校验、URL 输出和失败回退流程。
- 定义前端 `Model3DRenderer` 与后端 display 配置生成的职责分工。
- 定义首批格式支持范围为 PMX 模型与 VMD 动作。

### 不包含
- 不定义人格、记忆、关系、情绪迁移或 prompt 决策规则。
- 不定义 TTS 合成、STT 输入、LLM provider 鉴权或能力层调用策略。
- 不定义用户偏好持久化的存储 schema。
- 不定义 VRM、GLTF / GLB、FBX、动作标签系统和表情预设库的字段规范；这些格式进入实现前必须追加本文件。

## 外部锚点引用
- `系统设计总览.md#核心数据契约`:引用 `DisplayState` 作为表现层输入契约。
- `系统设计总览.md#系统分层`:引用 UI / API / Application / Personality / Memory / Capability 的职责边界。
- `UI层.md#表现状态模型`:引用前端围绕 `DisplayState` 消费展示状态的规则。
- `UI层.md#Renderer 抽象`:引用 `AvatarSurface`、`PlaceholderRenderer`、`Live2DRenderer`、`Model3DRenderer` 的 renderer 分发规则。
- `UI层.md#角色资源加载`:引用前端通过 sidecar display 配置加载资源、失败回退和手动皮肤优先规则。
- `IPC协议.md#Display 配置`:引用 display mode、资源配置和前后端协议边界。
- `扩展与迁移.md#角色包结构`:引用角色包目录、manifest 与用户数据分离规则。

## 输入 / 输出
### 输入
| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `character_id` | string | 是 | 当前角色 ID；所有皮肤共享同一个 `character_id`。 |
| `character_root` | path | 是 | 后端解析后的角色目录，例如 `characters/<id>/`。 |
| `manifest.display.mode` | enum | 是 | 允许值为 `placeholder`、`live2d`、`model3d`；本文件只定义 `model3d`。 |
| `manifest.display.model3d.root` | relative path | 是 | 3D 资源根目录；路径必须位于 `character_root` 内。 |
| `manifest.display.model3d.default_skin` | string | 是 | 默认皮肤 ID；必须存在于 `skins`。 |
| `manifest.display.model3d.skin_order` | string[] | 否 | 手动选择和兜底遍历顺序；值必须存在于 `skins`。 |
| `manifest.display.model3d.auto_switch.enabled` | boolean | 否 | 是否允许按 `DisplayState` 自动选择皮肤；缺失时按 `false` 处理。 |
| `manifest.display.model3d.auto_switch.prefer_manual` | boolean | 否 | 手动锁定是否优先于自动切换；缺失时按 `true` 处理。 |
| `manifest.display.model3d.auto_switch.mood_skins` | object | 否 | `mood` 到 `skin_id` 的映射；目标皮肤必须存在于 `skins`。 |
| `manifest.display.model3d.skins` | object | 是 | 皮肤表；key 为 `skin_id`。 |
| `manifest.display.model3d.skins.<skin_id>.scene` | relative path | 是 | 指向该皮肤的 `scene.json`；路径必须位于 `model3d.root` 内。 |
| `scene.model.file` | relative path | 是 | 模型主文件；首批允许扩展名为 `.pmx`。 |
| `scene.motions` | object | 否 | 动作表；首批允许动作文件扩展名为 `.vmd`。 |
| `scene.camera` | object | 否 | 相机距离、FOV 和目标点；缺失时 renderer 使用内置默认值。 |
| `scene.transform` | object | 否 | 模型缩放、位置和旋转；缺失时 renderer 使用内置默认值。 |
| `scene.lighting` | object | 否 | 环境光和方向光配置；缺失时 renderer 使用内置默认值。 |
| `scene.morphs` | object | 否 | 表情或口型 morph 映射。 |
| `scene.state_map` | object | 否 | `DisplayState` 到动作、morph、皮肤或强度的映射。 |
| `display_state` | object | 是 | 当前表现状态；字段来源见 `系统设计总览.md#核心数据契约` 与 `UI层.md#表现状态模型`。 |
| `manual_skin_lock` | string \| null | 否 | 用户当前手动锁定皮肤；这是运行时偏好，不写回角色包。 |
| `session_skin` | string \| null | 否 | 当前会话临时皮肤；会话结束后失效。 |

### 输出
| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `display_mode` | enum | 是 | 成功输出时为 `model3d`；回退到其他 provider 时输出目标 provider。 |
| `character_id` | string | 是 | 与输入 `character_id` 一致。 |
| `active_skin` | string | 是 | 本轮实际选中的皮肤 ID。 |
| `model_url` | URL | `display_mode=model3d` 时是 | 后端生成的模型资源 URL；前端不得拼接本地路径。 |
| `texture_urls` | URL[] | `display_mode=model3d` 且模型需要外部贴图时是 | 后端生成的贴图 URL 列表。 |
| `motion_urls` | object | 否 | 后端生成的动作 URL 表。 |
| `camera` | object | 否 | 前端 renderer 可直接消费的相机配置。 |
| `transform` | object | 否 | 前端 renderer 可直接消费的模型变换配置。 |
| `lighting` | object | 否 | 前端 renderer 可直接消费的灯光配置。 |
| `morphs` | object | 否 | 前端 renderer 可直接消费的 morph 映射。 |
| `state_map` | object | 否 | 前端 renderer 可直接消费的状态映射。 |
| `fallback_provider` | enum \| null | 否 | 当前 provider 失败后的候选 provider；无候选时为 `null`。 |
| `errors` | object[] | 否 | 资源校验或加载失败记录；不得包含 API key、绝对私密路径或未脱敏日志。 |

## 流程
1. 后端读取 `characters/<id>/manifest.yaml`。
2. 后端检查 `display.mode`；值不是 `model3d` 时终止本流程并交给对应 display provider。
3. 后端读取 `display.model3d.root`、`default_skin`、`skin_order`、`auto_switch` 和 `skins`。
4. 后端校验 `root`、每个 `skins.<skin_id>.scene`、`scene.model.file`、`scene.motions` 均位于 `characters/<id>/` 内。
5. 后端按皮肤选择优先级确定候选皮肤：`manual_skin_lock`、`session_skin`、`auto_switch.mood_skins[display_state.mood]`、`default_skin`、`skin_order` 中剩余皮肤。
6. 后端读取候选皮肤的 `scene.json`。
7. 后端校验模型文件、贴图文件和动作文件存在；首批只接受 `.pmx` 模型和 `.vmd` 动作。
8. 校验成功时，后端生成 `model_url`、`texture_urls`、`motion_urls` 和 renderer 参数，返回 `display_mode=model3d`。
9. 当前候选皮肤校验失败时，后端记录错误并尝试下一候选皮肤。
10. 所有 `model3d` 候选皮肤失败时，后端按 display provider 回退顺序输出其他 provider 配置。
11. 所有 display provider 均失败时，后端输出 `placeholder` 配置。
12. 前端 `AvatarSurface` 根据 `display_mode` 创建或复用对应 renderer。
13. `Model3DRenderer` 只消费后端输出的 URL、renderer 参数和 `DisplayState`；不得读取角色本地路径。
14. `Model3DRenderer` 应用模型、动作、morph、相机、灯光和变换参数。
15. `Model3DRenderer` 加载或播放失败时向前端状态层报告错误，并触发 provider 回退；失败不得禁用文本输入、文字回复、记忆写入或 TTS 队列。

## 约束与规则
- `model3d` 是 display provider，不是业务层。
- `model3d` 不得生成台词、修改情绪、修改关系状态、读取记忆或参与 prompt 拼装。
- 角色人格只由 `personality.yaml` 和人格层规则决定；皮肤切换不得改变人格。
- 多皮肤必须共享同一个 `character_id`。
- `manifest.yaml` 只描述资源入口和展示能力；模型调参必须放入 `scene.json`。
- `scene.json` 只描述单皮肤资产差异和展示调参；不得保存用户偏好或业务规则。
- 用户手动锁定皮肤、会话临时皮肤、显示缩放和平移属于运行时偏好，不得写回角色包。
- `auto_switch.prefer_manual=true` 时，`manual_skin_lock` 必须优先于 `mood_skins`。
- 自动切换只影响视觉表现，不得写回 `DisplayState` 的 `mood`、`emotion_intensity`、`relationship` 或 prompt 输入。
- 后端必须拒绝跳出角色目录的相对路径、绝对路径注入和符号链接逃逸结果。
- 前端只能使用后端提供的 URL，不得拼接 `characters/<id>/` 本地路径。
- 窗口 resize 不得触发 `manifest.yaml` 或 `scene.json` 重新解析；renderer 可根据容器尺寸更新相机或画布。
- 资源加载失败不得阻断聊天、记忆、关系状态、TTS 或管理界面。
- PMX / VMD 之外的格式在本文件追加字段、流程和验收标准前不得进入默认启用路径。
- VRM、GLTF / GLB、FBX、动作标签系统和表情预设库为 `[待定:格式扩展字段和加载器未定义]`。

## 验收标准
- 执行 `manifest.display.mode=model3d` 且 `default_skin=base` 的角色加载；后端输出包含 `display_mode=model3d`、`active_skin=base` 和 `model_url`。
- 将 `manual_skin_lock` 设置为 `combat`，同时设置 `display_state.mood=happy` 且 `mood_skins.happy=base`；后端输出 `active_skin=combat`。
- 清空 `manual_skin_lock` 并设置 `display_state.mood=angry`、`mood_skins.angry=combat`；后端输出 `active_skin=combat`。
- 将当前皮肤模型文件路径改为不存在的相对路径；后端记录当前皮肤错误并尝试默认皮肤或下一个 `skin_order` 皮肤。
- 将所有 `model3d` 皮肤模型文件路径改为不存在的相对路径；前端显示 `placeholder`，文本输入仍可发送。
- 将 `scene.model.file` 设置为 `../../outside.pmx`；后端拒绝该资源并返回资源校验错误。
- 将 `scene.model.file` 设置为绝对路径；后端拒绝该资源并返回资源校验错误。
- 将 `scene.model.file` 设置为 `.vrm` 文件；在格式扩展未追加到本文件前，后端拒绝默认启用该模型。
- 执行窗口 resize；前端不得重新请求 `manifest.yaml`，不得销毁并重建 renderer。
- 触发 `speaking=true`；`Model3DRenderer` 消费 `DisplayState` 并应用口型或说话态映射，不修改 `DisplayState`。
- 触发 `thinking=true`；`Model3DRenderer` 消费 `DisplayState` 并应用待机或思考态映射，不修改 prompt 输入。
- 检查后端输出的 `errors`；结果不得包含 API key、用户绝对私密路径或未脱敏日志。

## 待定汇总
- `[待定:格式扩展字段和加载器未定义]`:VRM、GLTF / GLB、FBX、动作标签系统和表情预设库尚未定义字段、加载器和验收标准。

## Amendments
<!-- 变更记录,只追加,不改写。 -->

### 2026-04-26
- 变更:按 `prompts/design_doc_prompt.md` 将 3D 模型支持文档重构为目标、范围、锚点、输入输出、流程、约束和验收标准格式。
- 影响:无
- 级联更新:无

## 本次级联更新汇总
- 触发源:`docs/desgin/3d-model-support.md`
- 已更新:无
- 无需更新:`docs/desgin/UI层.md`、`docs/desgin/IPC协议.md`、`docs/desgin/扩展与迁移.md`、`docs/desgin/系统设计总览.md`(现有引用与本次规范化后的字段和流程兼容)
