# AIRI Live2D 实现分析

本文分析 airi 主仓中 Live2D 的渲染、资源加载、动作更新和与音频/情绪的联动。

## 结论

- Live2D 是 airi 当前主仓里非常完整的一条能力线，不是 README 级宣称。
- 仓内已经有独立包 packages/stage-ui-live2d，负责组件、store、动作控制、表情控制、资源加载工具。
- 构建层明确接入了 Cubism SDK 下载插件，运行层明确使用 pixi-live2d-display/cubism4。
- 为了适配实际模型包，仓内还维护了对 pixi-live2d-display 的 patch 和 zip loader 修正。
- Live2D 已经与情绪、待机动作、自动眨眼、视线跟随、节拍同步、口型同步联动。

## 模块结构

核心包：

- packages/stage-ui-live2d

关键文件：

- packages/stage-ui-live2d/src/components/scenes/live2d/Model.vue
- packages/stage-ui-live2d/src/composables/live2d/motion-manager.ts
- packages/stage-ui-live2d/src/composables/live2d/beat-sync.ts
- packages/stage-ui-live2d/src/composables/live2d/expression-controller.ts
- packages/stage-ui-live2d/src/stores/live2d.ts
- packages/stage-ui-live2d/src/utils/live2d-zip-loader.ts
- patches/pixi-live2d-display.patch

## 渲染与舞台接入

### 1. 主组件

Model.vue 是核心控制器，承担：

- 加载 Live2DModel。
- 接到 Pixi Application stage。
- 按组件宽高和偏移计算模型位置与缩放。
- 绑定表情控制器、动作控制器、Beat Sync 和主题色阴影。
- 在模型重载时完成旧模型释放与新模型挂载。

这不是简单展示组件，而是完整的运行时控制器。

### 2. 舞台集成

Stage.vue 中直接使用 Live2DScene，并把：

- mouthOpenSize
- paused
- focusAt
- idle animation / auto blink / expression / shadow 等开关

作为 Live2D 运行时参数传入。

说明 Live2D 是 stage 的一等渲染后端，不是附属 demo 页面。

## 动作、表情和待机逻辑

### 1. Motion Manager Hook

motion-manager.ts 通过插件式 hookUpdate 机制改写 motionManager 更新流程，已内置几类插件：

- Beat Sync
- Idle disable
- Idle focus
- Auto eye blink
- Expression

它做的不是单一 motion 播放，而是把 Live2D motion manager 变成可插拔控制总线。

### 2. 待机与注视

从 motion-manager.ts 和相关 animation util 可以确认：

- idle 动画可整体开关。
- 即使关闭 idle motion，仍保留眼睛跟随与眨眼等细节更新。
- focusAt 会驱动模型朝光标或目标点看去。

### 3. 情绪联动

Stage.vue 中 emotionsQueue 会把情绪映射到：

- VRM expression 或
- Live2D motion group

Live2D 侧的常量和 expression controller 负责把情绪 token 映射成具体表情/动作。

## 音频与节拍联动

### 1. 口型同步

Stage.vue 使用 @proj-airi/model-driver-lipsync 创建 live2dLipSync，并把 mouthOpenSize 回写给 Live2D 场景。

这意味着 Live2D 嘴型不是静态参数，而是实时从播放中的音频能量估算得出。

### 2. Beat Sync

beat-sync.ts 提供 createBeatSyncController，功能包括：

- 根据节拍时间戳估计节拍间隔。
- 生成多种头部摆动风格：punchy-v、balanced-v、swing-lr、sway-sine。
- 对 ParamAngleX / Y / Z 做平滑过渡，而不是硬切。

这部分更像“表演层增强”，说明仓库不只满足于静态 Live2D 展示。

## 资源加载与工程化适配

### 1. SDK 构建接入

apps/stage-web/vite.config.ts 和 apps/stage-pocket/vite.config.ts 都接入了：

- @proj-airi/unplugin-live2d-sdk/vite

同时把 Live2D framework 相关模块列入 optimizeDeps.exclude，说明团队明确处理了 Cubism SDK 在 Vite 下的构建兼容性。

### 2. 第三方库补丁

patches/pixi-live2d-display.patch 修改了 pixi-live2d-display 的 settings 文件选择逻辑，显式避开 items_pinned_to_model.json 等非模型入口文件。

这说明项目在实际模型资产兼容上踩过坑，并做了仓内补丁维护。

### 3. ZIP 模型加载修正

live2d-zip-loader.ts 做了两件非常关键的事情：

- 如果 zip 中没有标准 .model3.json / .model.json，就根据 moc、贴图、motion、physics 自动构造 fake settings。
- 用 JSZip 接管 ZipLoader 的读取逻辑。

这让 airi 能加载“非完全标准打包”的 Live2D 模型资源，而不是只接受官方样板结构。

## 当前状态判断

可以判定为“已实现且工程化程度高”。

判断依据：

- 独立包而不是散落代码。
- 有构建插件、运行时组件、状态 store、动作插件、资源修正工具和第三方补丁。
- 与情绪、TTS、字幕和主舞台联动。

## 当前边界

- Live2D 资源本身不在仓库里完整托管，.gitignore 也忽略 assets/live2d/models。
- 许多行为仍依赖具体模型参数命名和 motion group 约定，不是完全无模型假设的统一层。
- 当前实现主打 Web/Electron 渲染链，非前端环境下没有独立 Live2D runtime。

## 最值得关注的文件

- packages/stage-ui-live2d/src/components/scenes/live2d/Model.vue
- packages/stage-ui-live2d/src/composables/live2d/motion-manager.ts
- packages/stage-ui-live2d/src/composables/live2d/beat-sync.ts
- packages/stage-ui-live2d/src/utils/live2d-zip-loader.ts
- patches/pixi-live2d-display.patch
- apps/stage-web/vite.config.ts
- apps/stage-pocket/vite.config.ts
