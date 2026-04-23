# Kokoro 3D 模型支持设计书

## 1. 设计目标

在不破坏现有 live2d 链路的前提下，为 Kokoro 增加一条与人格层解耦的 3D 角色展示链路。该链路需要满足以下目标：

- 角色展示能力从“具体技术实现”提升为“统一的 display 能力”。
- 人格、情绪、记忆系统不直接依赖任何渲染引擎或模型格式。
- 角色可以拥有多套 3D 皮肤，并支持手动切换与基于上下文的自动切换。
- 当 3D 资产不可用时，系统可优雅回退，不影响对话主流程。
- 管理界面能够查看角色当前展示配置，并提供必要的运营级切换能力。

这份设计只定义结构、职责与边界，不包含实现细节代码。

## 2. 设计哲学

### 2.1 表现层是人格的投影，不是人格本身

角色的语言、情绪与行为逻辑仍由 personality 和 application 层负责。模型系统只消费已经归一化的上下文信号，例如：

- 当前角色 ID
- 当前情绪 mood
- 当前是否在对话中
- 角色展示偏好
- 管理端显式选择的皮肤

3D 模型不直接参与 prompt 构建，也不决定情绪状态机的迁移。

### 2.2 先抽象能力，再接入技术

系统不以“支持 PMX”或“支持 VRM”作为顶层概念，而以“支持 3D display provider”作为顶层概念。

模型格式、加载器、动作驱动方式，都是 provider 内部的实现细节。上层只关心：

- 当前展示模式是什么
- 当前展示资源如何寻址
- 当前该展示哪套皮肤
- 当前该应用哪类姿态或表情映射

### 2.3 回退必须是优雅的

任何单一展示资产损坏，都不应阻断 Kokoro 的对话。渲染失败时应按以下优先级回退：

1. 当前 3D 皮肤失败，回退到该角色默认 3D 皮肤
2. 默认 3D 皮肤失败，回退到角色默认展示模式
3. 默认展示模式失败，回退到 placeholder

## 3. 范围

### 3.1 本次纳入范围

- 在角色 manifest 中引入 3D 展示定义
- 增加 3D 展示资源寻址与元数据组装能力
- 前端增加 3D 渲染容器
- 增加多皮肤切换与自动切换规则
- 增加新角色“流萤”及其双皮肤结构
- 管理界面展示当前 display 配置，并允许切换皮肤

### 3.2 本次不纳入范围

- 复杂骨骼动作编辑器
- 物理参数实时调优面板
- 高级时间线系统
- 多角色同屏 3D 场景编排
- 服务端渲染

## 4. 概念模型

### 4.1 角色目录分层

每个角色目录维持两个正交层：

- personality.yaml: 角色人格、行为、情绪触发规则
- manifest.yaml: 角色展示、资产与运行时元数据

角色资产按展示模式隔离，避免 live2d 与 3D 资源耦合在同一目录。

建议结构：

```text
characters/
  firefly/
    personality.yaml
    manifest.yaml
    assets/
      model3d/
        base/
          scene.json
          model.pmx | model.vrm
          textures/...
        combat/
          scene.json
          model.pmx | model.vrm
          textures/...
      live2d/
        ...
```

其中：

- assets/model3d/{skin-id} 表示一套完整皮肤
- scene.json 作为该皮肤的本地展示描述文件，用于归一化不同源模型的运行参数

### 4.2 display provider

display provider 是 manifest.display.mode 对应的展示实现单元。首批 provider：

- placeholder
- live2d
- model3d

provider 的统一职责：

- 校验 display 配置是否完整
- 解析资产根目录
- 生成前端可消费的展示配置
- 在部分配置缺失时提供稳定默认值

## 5. Manifest 设计

### 5.1 顶层结构

manifest.display.mode 决定当前角色默认采用的展示方式。

示意结构：

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
      rules:
        - when_mood_in: [happy, shy]
          use_skin: base
        - when_mood_in: [angry, cold]
          use_skin: combat
    skins:
      base:
        scene: base/scene.json
      combat:
        scene: combat/scene.json
```

### 5.2 scene.json 的职责

scene.json 不是业务配置，而是单皮肤展示描述文件。用于归一化每套皮肤的局部差异，例如：

- 模型主文件路径
- 相机距离与朝向
- 模型缩放
- 模型平移
- 环境光与主光
- 可选待机动画名
- 心情到表情预设的映射

scene.json 的存在意义是把“模型导出差异”封装在皮肤内部，而不是把大量低层渲染参数散落到 manifest 顶层。

### 5.3 自动切换策略

自动切换策略必须满足“可预测”。规则优先级如下：

1. 管理端当前手动指定皮肤
2. 会话内显式锁定皮肤
3. auto_switch 规则
4. default_skin

该优先级保证“用户/运营显式选择”高于“系统推断”。

## 6. 运行时职责分配

### 6.1 后端职责

后端负责：

- 读取 manifest
- 验证展示模式是否合法
- 解析默认皮肤与皮肤列表
- 解析 scene.json 所需 URL
- 根据 mood 和当前展示上下文给出建议皮肤
- 向前端返回统一 display 配置

后端不负责：

- 直接渲染 3D
- 解释底层 WebGL 细节
- 维护复杂相机状态

### 6.2 前端职责

前端负责：

- 根据 display.mode 选择对应 renderer
- 加载 3D provider 返回的 scene 配置
- 创建渲染上下文
- 响应皮肤切换、窗口尺寸变化、资源重载
- 在资源异常时给出可见但不侵入的失败提示

前端不负责：

- 推断角色人格
- 生成皮肤选择规则
- 直接修改角色持久化配置

## 7. 3D 渲染抽象

### 7.1 Avatar Surface

前端展示层应以统一 Avatar Surface 为入口。该入口只做分发：

- 当 mode 为 live2d 时，挂载 Live2D renderer
- 当 mode 为 model3d 时，挂载 3D renderer
- 否则显示 placeholder

Avatar Surface 只负责模式分发，不内聚任何 live2d 或 3D 的引擎细节。

### 7.2 3D renderer 的最小职责

3D renderer 内部应继续拆分：

- 场景初始化
- 模型加载
- 灯光与相机应用
- 情绪映射应用
- 销毁与资源回收

这保证未来从 PMX 扩展到 VRM、GLTF 时，不必重写整个展示层。

## 8. 流萤角色设计

### 8.1 角色定位

新增角色 ID 建议为 firefly。

原因：

- 目录 ID 使用稳定、ASCII、可预测命名，便于 URL、配置和跨平台路径处理
- 展示名称仍可在 personality.yaml 中保留“流萤”

### 8.2 皮肤设计

流萤当前有两套 3D 皮肤：

- base: 常态流萤
- combat: 武装或变身态

语义上，皮肤不是两个角色，而是同一角色的两个视觉状态。人格配置应保持单一，皮肤切换由 manifest.display.model3d 管理。

### 8.3 自动切换建议

建议默认规则：

- happy、shy、normal 优先使用 base
- angry、cold 优先使用 combat

该规则只表达视觉倾向，不改变底层情绪状态机。

## 9. 管理界面设计

管理界面应增加但不泛化过度。首批仅支持：

- 查看当前角色默认展示模式
- 查看当前角色支持的皮肤列表
- 查看当前默认皮肤
- 临时切换当前会话皮肤
- 开关自动切换

管理界面不应承担模型编辑器职责，不提供逐项渲染参数调节。若需调参与资产重建，应回到角色目录配置文件进行维护。

## 10. 兼容与演进

### 10.1 向后兼容

现有 live2d 角色无需修改 personality.yaml。

manifest 缺失 model3d 节点时，系统维持原行为。display.mode 不是 model3d 的角色完全不进入 3D 链路。

### 10.2 演进方向

未来可在不破坏当前结构的前提下扩展：

- model3d 支持更多模型格式
- scene.json 增加动画片段定义
- 引入“基于动作标签”的状态切换，而不只按 mood 切换
- 支持更多展示上下文，如待机、思考中、主动开口、夜间模式

## 11. 设计总结

本设计的核心不是“把 3D 接进来”，而是把 Kokoro 的角色展示能力提升为一个稳定、可扩展、可退化的抽象层。

3D 是新的 provider，不是新的耦合源。

流萤的双皮肤能力是这层抽象的第一个完整用例：

- 一个人格
- 多套视觉外观
- 手动与自动共存
- 失败可回退
- 管理可观测

只有在这个边界稳定之后，3D 支持才会是优雅的，而不是一次性的特例接线。
