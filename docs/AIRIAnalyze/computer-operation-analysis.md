# AIRI 操作电脑能力分析

本文分析 airi 主仓里与“操作电脑、控制应用、操作浏览器、执行终端命令、屏幕观测”相关的实现。

## 结论

- 这部分是 airi 主仓里最成熟、最工程化的能力之一。
- 核心实现集中在 services/computer-use-mcp。
- 这不是单纯的鼠标点击 demo，而是带有审批、审计、运行状态、工作流和 reroute 策略的 MCP 执行底座。
- 另有 packages/electron-screen-capture 作为屏幕捕获辅助能力，偏 Electron 集成，不等于完整 computer use。
- 当前主执行器明显偏向 macOS，本仓尚未形成完整 Windows 本地执行后端。

## 核心包：computer-use-mcp

关键文件：

- services/computer-use-mcp/README.md
- services/computer-use-mcp/src/server/register-tools.ts
- services/computer-use-mcp/src/server/action-executor.ts
- services/computer-use-mcp/src/policy.ts
- services/computer-use-mcp/src/strategy.ts
- services/computer-use-mcp/src/task-memory/*
- services/computer-use-mcp/src/workflows/*

README 已经把它的定位写得非常清楚：

- AIRI 是 control plane。
- computer-use-mcp 是本地执行和 workflow substrate。
- 目标不是“演示鼠标会动”，而是把桌面、浏览器和终端统一成一个可控任务系统。

## 已实现的工具面

从 register-tools.ts 可以直接确认已注册的工具族。

### 1. 桌面观察与控制

已注册工具包括：

- desktop_get_capabilities
- desktop_observe_windows
- desktop_screenshot
- desktop_open_app
- desktop_focus_app
- desktop_click
- desktop_type_text
- desktop_press_keys
- desktop_scroll
- desktop_wait

这条线已经覆盖：

- 获取当前环境能力
- 观察窗口
- 截图
- 打开和切换应用
- 鼠标点击
- 键盘输入
- 组合键
- 滚动

### 2. 终端控制

已注册工具包括：

- terminal_exec
- terminal_get_state
- terminal_reset_state

说明该系统不是只会 GUI 操作，也会优先走更确定性的 shell 执行路径。

### 3. 浏览器 DOM 控制

已注册工具包括：

- browser_agent_get_status
- browser_agent_run
- browser_dom_get_bridge_status
- browser_dom_get_active_tab
- browser_dom_read_page
- browser_dom_find_elements
- browser_dom_click
- browser_dom_read_input_value
- browser_dom_set_input_value
- browser_dom_check_checkbox
- browser_dom_select_option
- browser_dom_wait_for_element
- browser_dom_get_element_attributes
- browser_dom_get_computed_styles
- browser_dom_trigger_event

这说明 airi 没有把浏览器自动化硬塞进桌面坐标点击，而是明确区分：

- 桌面表面
- 浏览器 DOM 表面
- 终端表面

这是这套系统工程质量较高的标志。

### 4. 审批、追踪和工作流

已注册工具包括：

- desktop_list_pending_actions
- desktop_approve_pending_action
- desktop_reject_pending_action
- desktop_get_session_trace
- desktop_get_state
- workflow_open_workspace
- workflow_validate_workspace
- workflow_run_tests
- workflow_inspect_failure
- workflow_browse_and_act
- workflow_resume

这部分说明系统已经内建：

- 审批队列
- 审计轨迹
- 运行时状态
- 可恢复工作流

不是一次性 action 执行器。

## 策略和安全边界

从 README、policy.ts、strategy.ts 可以总结出当前设计特点：

- 终端命令默认需要 approval。
- open/focus app 需要 approval。
- AIRI 自身默认在 deny list，避免自操作。
- 浏览器 DOM、桌面点击、PTY、终端 exec 会根据场景 reroute。
- 当 terminal_exec 面对 TUI 场景不合适时，策略层会建议切到 PTY。

这说明作者不是在追求“能动起来就行”，而是在追求“可恢复、可审计、尽量确定性”。

## 执行器现状

README 已明确当前执行模式：

- dry-run
- macos-local
- linux-x11（保留实验/遗留）

其中 macos-local 是当前主后端。

这意味着：

- 仓内 computer-use 的主故事是 macOS 本地执行。
- 对 Windows 用户来说，虽然仓库整体支持 Windows 开发，但 computer-use-mcp 这一包当前不是以 Windows 本地执行为主线设计。

## 任务记忆

与 computer use 直接相关的一点是 task-memory。

它不是人格长期记忆，而是自动化任务上下文，记录：

- goal
- currentStep
- confirmedFacts
- blockers
- nextStep
- status

这让 computer-use 行为能跨多个 action 保持“现在做到哪一步”的上下文。

## 辅助能力：Electron 屏幕捕获

关键文件：

- packages/electron-screen-capture/src/main/index.ts
- packages/electron-screen-capture/src/vue/use-electron-screen-capture.ts

这条线主要负责：

- Electron main/renderer 间屏幕捕获接线。
- 获取可捕获 source。
- 选定 source 后执行 getDisplayMedia。
- macOS 权限检查和请求。

它更像“观测能力”和 Electron 集成层，而不是完整的 computer-use 系统。

## 当前状态判断

建议分类为“已实现，且成熟度高”。

同时要强调两个边界：

- 这套能力主要沉淀在 computer-use-mcp，不是整个 stage 主应用随处可用的 UI 功能。
- 当前 v1 主后端是 macOS，本仓没有看到对 Windows 本地桌面控制同等成熟的执行器。

## 最值得关注的文件

- services/computer-use-mcp/README.md
- services/computer-use-mcp/src/server/register-tools.ts
- services/computer-use-mcp/src/server/action-executor.ts
- services/computer-use-mcp/src/policy.ts
- services/computer-use-mcp/src/strategy.ts
- services/computer-use-mcp/src/task-memory/manager.ts
- packages/electron-screen-capture/src/main/index.ts
