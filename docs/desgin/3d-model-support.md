# 3D 模型支持

3D 模型支持是 Kokoro 表现层的一种 display provider。它的职责是把角色状态渲染为可视化形象，而不是参与人格、记忆、关系或 prompt 决策。

## 设计目标

- 让 3D 展示与人格系统解耦
- 让不同模型格式通过统一 display 配置接入
- 支持多皮肤、多动作和情绪表现
- 支持失败回退，不影响核心对话
- 与 Live2D 和 placeholder 共用表现状态模型

## Display Provider 模型

角色展示由 `display.mode` 决定。

可选 provider：

- `placeholder`
- `live2d`
- `model3d`

`model3d` provider 负责：

- 解析 3D 资源配置
- 校验模型、贴图、动作文件路径
- 生成前端可消费的 URL
- 提供相机、灯光、缩放、位移等参数
- 提供情绪到动作、表情、皮肤的映射

provider 不负责：

- 生成台词
- 修改情绪
- 修改关系状态
- 读取记忆

## 角色目录结构

推荐结构：

```text
characters/<id>/
  manifest.yaml
  personality.yaml
  assets/
    model3d/
      <skin_id>/
        scene.json
        model.pmx | model.vrm | model.glb
        textures/
        motions/
```

每个 `skin_id` 表示一套完整视觉外观。多皮肤属于同一角色，不代表多个人格。

## manifest 设计

manifest 描述角色具备哪些展示能力。

示意：

```yaml
display:
  mode: model3d
  model3d:
    root: assets/model3d
    default_skin: base
    skin_order:
      - base
      - combat
    auto_switch:
      enabled: true
      prefer_manual: true
      mood_skins:
        happy: base
        shy: base
        angry: combat
    skins:
      base:
        scene: base/scene.json
      combat:
        scene: combat/scene.json
```

设计原则：

- manifest 只描述资源入口和能力
- 具体模型调参放到 `scene.json`
- 角色人格仍在 `personality.yaml`
- 用户运行时选择不写回角色包

## scene.json 设计

`scene.json` 是单皮肤展示描述。

可包含：

- 模型主文件
- VMD / motion 文件
- 相机距离、FOV、目标点
- 模型缩放、位置、旋转
- 环境光、方向光
- morph 映射
- 情绪到动作的映射
- 口型同步参数

设计边界：

- `scene.json` 不存用户偏好
- `scene.json` 不存业务规则
- `scene.json` 只解决资产差异和展示调参

## 自动切换策略

自动切换必须可预测。

优先级：

1. 用户当前手动锁定皮肤
2. 当前会话临时选择
3. 情绪或状态映射
4. 角色默认皮肤

自动切换只影响视觉表现，不应改变角色人格或情绪状态。

## 表现状态映射

3D renderer 消费统一 `DisplayState`。

映射示例：

- `mood=happy`：轻快动作、笑脸 morph
- `mood=angry`：严肃表情、动作强度提高
- `thinking=true`：视线游移或轻微待机动作
- `speaking=true`：口型同步和说话态动作
- `attention=true`：看向用户或短暂前摇

状态映射由配置驱动，不应写死在具体角色逻辑里。

## 回退策略

回退顺序：

1. 当前皮肤失败，尝试默认皮肤
2. 默认皮肤失败，尝试其他 display provider
3. 所有资源失败，显示 placeholder

资源失败不应阻断聊天、记忆或 TTS。

## 前后端职责

后端负责：

- 读取 manifest
- 解析 scene 配置
- 校验资源路径
- 生成 URL 和统一 display 配置

前端负责：

- 根据 display mode 选择 renderer
- 加载模型和动作
- 应用相机、灯光、morph 和动作
- 处理播放、销毁和资源回收

## 格式演进

首批可支持 PMX / VMD。未来可扩展：

- VRM
- GLTF / GLB
- FBX
- 动作标签系统
- 表情预设库

格式扩展不应影响人格层和记忆层。

## 设计约束

- 3D 是 display provider，不是业务层
- 角色核心人格不随皮肤切换
- 多皮肤共享同一 `character_id`
- 资源路径必须受后端校验
- 前端渲染失败必须可回退
- 展示能力不能反向决定 prompt 内容
