# 3D 模型支持

## 目标
定义 Kokoro 当前 `model3d` display provider 的真实字段、资源解析和回退规则，确保 3D 资源失败时不阻断聊天主链路。

## 范围
### 包含
- `manifest.yaml` 中 `display.model3d` 的当前字段。
- 单皮肤 `scene.json` 的当前字段和后端可识别的资源格式。
- sidecar 如何把角色目录资源转换为前端可消费的 display 配置。

### 不包含
- 不定义 VRM / GLTF / GLB / FBX 支持。
- 不定义人格、记忆、关系或 TTS 规则。

## 外部锚点引用
- 00-系统设计总览.md#输入 / 输出:display 配置在系统中的位置。
- 06-UI层.md#输入 / 输出:主窗口如何消费 display 配置。
- 07-IPC协议.md#输入 / 输出:资源与显示配置的外部协议。
- 11-扩展与迁移.md#约束与规则:角色目录与 manifest 入口边界。

## 输入 / 输出
### 输入
| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `manifest.display.mode` | enum | 是 | 当前为 `model3d` 时进入本流程。 |
| `manifest.display.model3d.root` | relative path | 是 | 3D 资源根目录，必须位于角色目录内。 |
| `manifest.display.model3d.default_skin` | string | 否 | 默认皮肤 ID；不存在时回退到第一个有效皮肤。 |
| `manifest.display.model3d.skin_order` | `list[str]` | 否 | 前端展示顺序与兜底遍历顺序。 |
| `manifest.display.model3d.auto_switch.enabled` | boolean | 否 | 是否开启按情绪自动换皮；默认 `true`。 |
| `manifest.display.model3d.auto_switch.prefer_manual` | boolean | 否 | 手动选择是否优先；默认 `true`。 |
| `manifest.display.model3d.auto_switch.mood_skins` | `dict[str, str]` | 否 | 情绪到皮肤 ID 的映射。 |
| `manifest.display.model3d.skins.<skin_id>.scene` | relative path | 是 | 指向皮肤 `scene.json`。 |
| `scene.model` | relative path | 是 | PMX 模型路径。 |
| `scene.vmd` | relative path | 否 | 默认动作文件路径。 |
| `scene.mood_vmds` | `dict[str, relative path]` | 否 | 情绪到动作文件路径映射。 |
| `scene.procedural_motion` | string | 否 | 默认程序化动作名。 |
| `scene.mood_procedural_motions` | `dict[str, str]` | 否 | 情绪到程序化动作映射。 |
| `scene.scale` `position` `rotation_deg` | number / vector3 | 否 | 模型变换参数。 |
| `scene.camera` | object | 否 | 相机距离、FOV、target。 |
| `scene.lights` | object | 否 | 环境光和方向光参数。 |
| `scene.morphs` | object | 否 | `mood_weights` 与 `lip_sync` 配置。 |
| `ExpressionEvent` `MotionEvent` `LipSyncLevel` | object / number | 否 | AIRI 合并修正(追加:2026-04-28): DisplayRuntime 的统一输入，用于驱动表情、动作、注视、眨眼和口型。 |

### 输出
| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `display.mode` | string | 是 | 返回 `model3d`。 |
| `display.model3d.default_skin` | string | 是 | 经校验后的默认皮肤。 |
| `display.model3d.skin_order` | `list[str]` | 是 | 有效皮肤顺序。 |
| `display.model3d.auto_switch` | object | 是 | 包含 `enabled`、`prefer_manual`、`mood_skins`。 |
| `display.model3d.skins` | object | 是 | 每个皮肤包含 `label`、`model_url`、`vmd_url?`、`mood_vmd_urls`、`procedural_motion`、`mood_procedural_motions`、`scale`、`position`、`rotation_deg`、`camera`、`lights`、`morphs?`。 |
| `DisplayRuntimeState` | object | 否 | AIRI 合并修正(追加:2026-04-28): 前端运行时状态，包含当前 adapter、loaded、fallback_reason、current_motion、speaking、lip_sync_level。 |

## 流程
1. sidecar 读取 `manifest.yaml` 并检查 `display.mode=model3d`。
2. 解析 `root` 并确保路径位于角色目录内。
3. 遍历 `skins`，逐个读取 `scene.json`。
4. 仅保留模型文件、动作文件和场景配置均合法的皮肤。
5. 生成资源 URL 时统一通过 `/character-assets/{character_id}/{asset_path}` 暴露，不把本地路径暴露给前端。
6. 若 `skin_order` 缺失或不完整，使用有效皮肤的自然顺序补齐。
7. 若 `default_skin` 无效，回退到第一个有效皮肤。
8. 若没有任何有效皮肤，则 sidecar 继续尝试其他 display provider，最终回退到 `placeholder`。
9. 前端消费皮肤时，默认优先使用 `scene.vmd` 作为待机动作；情绪变化时优先使用 `scene.mood_vmds[mood]`，缺失时再回退到 `scene.mood_procedural_motions[mood]` 或默认程序化动作。
10. AIRI 合并修正(追加:2026-04-28): 前端 display provider 必须收敛到 `DisplayRuntime -> Live2DAdapter | Model3DAdapter | SpriteAdapter`；三个 adapter 消费同一组 `ExpressionEvent`、`MotionEvent` 和 `LipSyncLevel`。
11. AIRI 合并修正(追加:2026-04-28): Live2DAdapter 必须支持 motion queue、idle、blink、focusAt；Model3DAdapter 必须支持 morph/motion 事件消费；SpriteAdapter 必须至少支持 emotion 到静态表情切换。

## 约束与规则
- 当前只接受 PMX 模型和可选 VMD 动作文件。
- 前端只消费 sidecar 生成的 URL 和场景配置，不读取本地角色目录。
- `model3d` provider 不得修改人格、记忆、情绪或关系状态。
- 所有资源路径都必须受 `_resolve_within()` 约束，禁止逃逸角色目录。
- 当前文档只描述已实现字段；其他格式进入代码前必须先追加本文件。
- `scene.morphs.lip_sync.names` 缺失、为空，或模型中找不到对应 morph 时，口型同步必须静默跳过，不把资源缺口升级为前端错误。
- AIRI 合并修正(追加:2026-04-28): 角色卡的 `modules.display` 或 `manifest.display` 必须作为 display profile 的来源；前端不得把角色名称硬编码为 display mode。
- AIRI 合并修正(追加:2026-04-28): 模型加载失败时必须产生 `fallback_reason`，并回退到下一个可用 display provider；失败不得阻断聊天、TTS 或主动事件接收。
- `[待定:VRM / GLTF / GLB / FBX 扩展字段与加载器尚未定义]`。

## 验收标准
- 提供合法的 `manifest.display.model3d` 与 `scene.json`；`/state.display.mode` 返回 `model3d` 且带有效 `skins`。
- `default_skin` 指向不存在的皮肤；sidecar 回退到第一个有效皮肤。
- 某个皮肤的 `scene.model` 文件不存在；该皮肤被忽略，其他有效皮肤仍可使用。
- 所有皮肤均无效；主窗口最终回退到非 `model3d` provider 或 `placeholder`，文本聊天仍可用。
- `scene.model` 使用逃逸路径；sidecar 拒绝该资源。
- `scene.mood_vmds` 缺少当前情绪条目但存在 `mood_procedural_motions`；前端继续播放程序化动作而不是报错。
- `scene.morphs.lip_sync.names` 未配置或名称与模型不匹配；模型继续渲染且不显示口型相关错误。
- 向 DisplayRuntime 投递 `MotionEvent(name=nod)`；当前 adapter 播放对应动作或记录 `fallback_reason=motion_not_supported`，主窗口不崩溃。
- 模型资源加载失败；`DisplayRuntimeState.fallback_reason` 非空，主窗口回退到 image 或 placeholder，聊天仍可发送。

## 待定汇总
- `[待定:VRM / GLTF / GLB / FBX 扩展字段与加载器尚未定义]`。

## Amendments
<!-- 变更记录,只追加,不改写。 -->

### 2026-04-28
- 变更:追加 AIRI 合并的 DisplayRuntime 规范，统一 Live2D、3D 和 Sprite 对 ExpressionEvent、MotionEvent、LipSyncLevel 的消费边界。
- 原因:级联自 00-系统设计总览.md 的同日变更
- 影响:06-UI层.md / 07-IPC协议.md / 11-扩展与迁移.md

### 2026-04-26
- 变更:按 `prompts/design_doc_prompt.md` 将 3D 模型支持文档重构为目标、范围、锚点、输入输出、流程、约束和验收标准格式。
- 影响:无
- 级联更新:无

### 2026-04-26
- 变更:按当前 `character_assets.py` 的真实实现同步 `model3d` 字段、scene.json 字段和回退规则，删除未实现的状态映射叙述。
- 影响:无
- 级联更新:06-UI层.md、07-IPC协议.md、11-扩展与迁移.md

### 2026-04-26
- 变更:补充 3D 皮肤的 VMD 优先级、程序化动作回退和口型同步静默降级规则，匹配当前前端表现层实现。
- 影响:06-UI层.md / 07-IPC协议.md
- 级联更新:06-UI层.md、07-IPC协议.md

## 本次级联更新汇总
- 触发源:`docs/desgin/09-3d-model-support.md`
- 已更新:`docs/desgin/06-UI层.md`(消费规则同步)、`docs/desgin/07-IPC协议.md`(显示协议同步)、`docs/desgin/11-扩展与迁移.md`(角色包边界同步)
- 无需更新:`docs/desgin/00-系统设计总览.md`、`docs/desgin/10-安全与边界.md`(仅引用 provider 边界, 本次字段变化不影响总览和安全约束)
