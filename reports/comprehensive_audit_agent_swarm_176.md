# 代码漏洞与用户体验问题全面审计报告（176 Agent Swarm 分模块审计）

**项目**: IstinaEndfieldAssistant (IEA) + MaaEnd
**日期**: 2026-07-09 22:09
**范围**: 全代码库静态审计（IEA Python + MaaEnd Go/C++ + Pipeline JSON + 配置）
**方法**: 176 个独立 Agent Swarm 子代理分模块并行审计
**约束**: 只读分析，不修改任何文件

## 1. 执行摘要

本次审计通过 **176 个独立子代理**对代码库进行分模块深度审计，覆盖：

| 维度 | 数量 | 说明 |
|------|------|------|
| 审计子代理总数 | 176 | 覆盖 IEA Python、MaaEnd Go/C++、Pipeline JSON、配置等 |
| 产生结构化发现的模块 | 86 | 多数模块识别出潜在问题 |
| 发现提及总数 | 548 | 含重复报告，需去重 |

### 1.1 严重程度分布（按提及次数）

| 等级 | 提及次数 | 核心风险 |
|------|----------|----------|
| P0 | 24 | 功能完全失效、安全漏洞、数据丢失 |
| P1 | 83 | 稳定性、资源泄漏、竞态条件 |
| P2 | 211 | 性能瓶颈、死代码、误导命名 |
| P3 | 230 | UX 细节、代码卫生、测试覆盖缺口 |

### 1.2 模块覆盖统计（Top 15）

| 模块 | 审计文件数 | 发现提及数 | P0 | P1 | P2 | P3 |
|------|-----------|-----------|----|----|----|----|
| MaaEnd/agent/cpp-algo/source | 47 | 128 | 2 | 13 | 40 | 73 |
| src/core/capability | 22 | 97 | 11 | 20 | 25 | 41 |
| MaaEnd/agent/go-service/autostockpile | 21 | 69 | 5 | 7 | 40 | 17 |
| src/gui/pyqt6 | 21 | 69 | 2 | 13 | 33 | 21 |
| MaaEnd/agent/go-service/essencefilter | 20 | 55 | 2 | 9 | 20 | 24 |
| MaaEnd/agent/go-service/common | 22 | 46 | 2 | 7 | 11 | 26 |
| src/core/service | 7 | 40 | 0 | 7 | 25 | 8 |
| MaaEnd/agent/go-service/autofight | 5 | 18 | 0 | 2 | 8 | 8 |
| src/cli/handlers.py | 1 | 11 | 0 | 4 | 4 | 3 |
| MaaEnd/agent/go-service/stderr_windows.go | 1 | 6 | 0 | 0 | 3 | 3 |
| src/core/foundation | 3 | 4 | 0 | 0 | 1 | 3 |
| src/cli/istina.py | 1 | 3 | 0 | 0 | 0 | 3 |
| MaaEnd/agent/go-service/register.go | 1 | 1 | 0 | 1 | 0 | 0 |
| MaaEnd/agent/go-service/stderr_other.go | 1 | 1 | 0 | 0 | 1 | 0 |
| MaaEnd/agent/go-service/version.go | 1 | 0 | 0 | 0 | 0 | 0 |

## 2. 关键发现（按严重程度）

### 2.1 P0 — 立即修复

#### src/core/capability/device/android_runtime.py

- **src/core/capability/device/android_runtime.py**: 任意 ADB shell 命令注入 486-490
- **src/core/capability/device/android_runtime.py**: 守护进程零认证 355-360
- **src/core/capability/device/android_runtime.py**: `_decode_loop` socket/fileobj 泄漏 292
- **src/core/capability/device/android_runtime.py**: `_decode_loop` 正常退出时 socket/fileobj 泄漏 292

#### MaaEnd/agent/go-service/autostockpile/options.go

- **MaaEnd/agent/go-service/autostockpile/options.go**: **安全漏洞（-）**：文件仅涉及 JSON 反序列化与数值范围校验，无命令执行、路径遍历、敏感信息泄露或资源未释放路径。`loadAutoStockpileAttach` 对 `ctx` 与 `nodeName` 做了防御性空值校验（第 33–38 行）。
- **MaaEnd/agent/go-service/autostockpile/options.go**: **稳定性（-）**：所有错误路径均显式返回并携带上下文，无 goroutine、文件句柄或内存泄漏风险。`validateServerTimeOffset` 正确识别 `nil` 指针并提前返回（第 22–24 行）。无竞态条件或死锁可能。
- **MaaEnd/agent/go-service/autostockpile/options.go**: **用户不友好设计（-）**：错误信息均通过 `fmt.Errorf` 包装并携带节点名称、具体数值等上下文（第 42、52、55 行），便于排查；无静默丢弃输入或误导性提示。
- **MaaEnd/agent/go-service/autostockpile/options.go**: **代码质量（-）**：代码简洁（59 行），命名清晰，常量定义明确（第 16–19 行），无死代码、重复代码或职责混乱，符合 SRP。

#### MaaEnd/agent/go-service/essencefilter/resource_path.go

- **MaaEnd/agent/go-service/essencefilter/resource_path.go**: 0 -
- **MaaEnd/agent/go-service/essencefilter/resource_path.go**: 0 —

#### src/core/capability/element_recognition/pipeline/pipeline_runner.py

- **src/core/capability/element_recognition/pipeline/pipeline_runner.py**: ****：当前文件无新增  阻塞性 Bug。

#### src/core/capability/llm/client.py

- **src/core/capability/llm/client.py**: **IEA -4（JPEG/PNG 不匹配）**：`iea_execution_algorithm_analysis.md` 已报告 `LlmClient.chat()` 默认 `image_mime_type="image/png"` 与 `vlm_walk_navigator.py` 的 JPEG 编码冲突。已在 `modification_implementation_report.md` 
- **src/core/capability/llm/client.py**: **已知报告中已覆盖**：1 个（IEA -4 JPEG/PNG 不匹配）

#### MaaEnd/agent/go-service/common/subtask/action.go

- **MaaEnd/agent/go-service/common/subtask/action.go**: 信息泄露 33

#### MaaEnd/agent/go-service/common/charactercontroller/controller.go

- **MaaEnd/agent/go-service/common/charactercontroller/controller.go**: 1 全局计数器竞态

#### MaaEnd/agent/go-service/autostockpile/strategy.go

- **MaaEnd/agent/go-service/autostockpile/strategy.go**: 0 —

#### MaaEnd/agent/cpp-algo/source/Navmesh/BaseNavReader.cpp

- **MaaEnd/agent/cpp-algo/source/Navmesh/BaseNavReader.cpp**: **无  问题**：未发现命令注入、路径遍历（依赖调用者输入）、缓冲区溢出、use-after-free、认证缺失或信息泄露。

#### MaaEnd/agent/cpp-algo/source/RecoGrid/RecoGridPlacement.cpp

- **MaaEnd/agent/cpp-algo/source/RecoGrid/RecoGridPlacement.cpp**: 0 严重安全漏洞

#### src/core/capability/element_recognition/tasks/task_runner.py

- **src/core/capability/element_recognition/tasks/task_runner.py**: `TaskRunner` 图不完整（`_build_task_graph` 仅注入 option override 节点，未包含任务基础 pipeline）
  - 位置: task_runner.py

#### src/gui/pyqt6/pages/log_page.py

- **src/gui/pyqt6/pages/log_page.py**: **** `log_page.py:121` — HTML 转义 no-op（使用 `line.replace("&", "&")` 等无效替换），导致 Qt 渲染执行恶意内容。

#### src/gui/pyqt6/queue_state.py

- **src/gui/pyqt6/queue_state.py**: `queue_persistence_analysis.md` 当前代码已改为返回 `bool` + `warning`，但调用方仍不检查返回值

### 2.2 P1 — 本轮迭代

#### src/core/capability/device/android_runtime.py

- **src/core/capability/device/android_runtime.py**: `_call` 无 socket 读取超时 570-575
- **src/core/capability/device/android_runtime.py**: `_Daemon` 无 `_tcp_port` 初始化 357-358
- **src/core/capability/device/android_runtime.py**: `_ScrcpySession._codec` 未在 stop 时关闭 296-317
- **src/core/capability/device/android_runtime.py**: `_call` 的 tap/swipe 忽略错误返回 558-583
- **src/core/capability/device/android_runtime.py**: `_push_jar` 吞掉所有失败 121-133
- **src/core/capability/device/android_runtime.py**: `_check_jar_cached` 吞掉 ADB 错误 108-116
- **src/core/capability/device/android_runtime.py**: `_Daemon` 无 `_tcp_port` 初始化（失败路径） 357-358

#### MaaEnd/agent/go-service/autostockpile/recognition.go

- **MaaEnd/agent/go-service/autostockpile/recognition.go**: **严重程度**：

#### src/core/service/runtime.py

- **src/core/service/runtime.py**: `src/core/service/runtime.py`
  - 位置: src/core/service/runtime.py

#### src/cli/handlers.py

- **src/cli/handlers.py**: `src/cli/handlers.py`
  - 位置: src/cli/handlers.py
- **src/cli/handlers.py**: 3 静默失败、状态不一致、崩溃风险

#### src/gui/pyqt6/pages/settings_page.py

- **src/gui/pyqt6/pages/settings_page.py**: `_save_settings` 无异常处理（ #38）
- **src/gui/pyqt6/pages/settings_page.py**: 每次按键触发完整 JSON 读写（ #39）
- **src/gui/pyqt6/pages/settings_page.py**: **严重程度**

#### MaaEnd/agent/go-service/common/subtask/action.go

- **MaaEnd/agent/go-service/common/subtask/action.go**: 异常处理缺失/超时缺失 108
- **MaaEnd/agent/go-service/common/subtask/action.go**: 静默失败 62
- **MaaEnd/agent/go-service/common/subtask/action.go**: 异常处理缺失/状态不一致 74

#### src/gui/pyqt6/queue_state.py

- **src/gui/pyqt6/queue_state.py**: 2 数据静默丢失（`load()` 吞异常）、浅拷贝污染内部状态
- **src/gui/pyqt6/queue_state.py**: `src/gui/pyqt6/queue_state.py`
  - 位置: src/gui/pyqt6/queue_state.py

#### src/gui/pyqt6/scripting/recorder.py

- **src/gui/pyqt6/scripting/recorder.py**: **严重程度**

#### MaaEnd/agent/go-service/autofight/screenanalyzer.go

- **MaaEnd/agent/go-service/autofight/screenanalyzer.go**: 50-52, 全体方法 竞态条件
- **MaaEnd/agent/go-service/autofight/screenanalyzer.go**: `MaaEnd/agent/go-service/autofight/screenanalyzer.go`
  - 位置: MaaEnd/agent/go-service/autofight/screenanalyzer.go

#### MaaEnd/agent/go-service/essencefilter/resource_path.go

- **MaaEnd/agent/go-service/essencefilter/resource_path.go**: 0 -
- **MaaEnd/agent/go-service/essencefilter/resource_path.go**: 0 —

#### MaaEnd/agent/go-service/essencefilter/state.go

- **MaaEnd/agent/go-service/essencefilter/state.go**: **严重程度：**

#### MaaEnd/agent/go-service/essencefilter/matchapi/loader.go

- **MaaEnd/agent/go-service/essencefilter/matchapi/loader.go**: **具体描述**: `weaponTypeToID` 中 `"Handcannon"` 与 `"Pistol"` 都映射到 `4`，`"Arts Unit"` 与 `"Wand"` 都映射到 `5`。虽然可能是业务上故意合并，但映射表命名为 `weaponTypeToID` 暗示一一对应。此外，若数据文件中出现未列出的 weapon_type，会触发前述  的静默零值问题。
- **MaaEnd/agent/go-service/essencefilter/matchapi/loader.go**: **建议优先关注  的两项静默跳过/零值问题，它们在现有代码中会直接造成数据完整性问题。**

#### MaaEnd/agent/go-service/essencefilter/matchapi/util.go

- **MaaEnd/agent/go-service/essencefilter/matchapi/util.go**: 1 非确定性替换导致匹配不稳定

#### MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp

- **MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp**: 空指针解引用 303
- **MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp**: 资源未释放（线程阻塞） 305

#### MaaEnd/agent/cpp-algo/source/MapNavigator/action_executor.cpp

- **MaaEnd/agent/cpp-algo/source/MapNavigator/action_executor.cpp**: `MaaEnd/agent/cpp-algo/source/MapNavigator/action_executor.cpp`
  - 位置: MaaEnd/agent/cpp-algo/source/MapNavigator/action_executor.cpp

### 2.3 P2 — 后续清理

#### src/core/service/runtime.py

- **src/core/service/runtime.py**: `src/core/service/runtime.py`
  - 位置: src/core/service/runtime.py

#### MaaEnd/agent/go-service/autofight/screenanalyzer.go

- **MaaEnd/agent/go-service/autofight/screenanalyzer.go**: 80-82 资源浪费/空帧堆积
- **MaaEnd/agent/go-service/autofight/screenanalyzer.go**: 54-63, 124-132 重复逻辑
- **MaaEnd/agent/go-service/autofight/screenanalyzer.go**: 89-103 死代码路径
- **MaaEnd/agent/go-service/autofight/screenanalyzer.go**: 139-168 死代码
- **MaaEnd/agent/go-service/autofight/screenanalyzer.go**: `MaaEnd/agent/go-service/autofight/screenanalyzer.go`
  - 位置: MaaEnd/agent/go-service/autofight/screenanalyzer.go

#### MaaEnd/agent/go-service/autostockpile/recognition.go

- **MaaEnd/agent/go-service/autostockpile/recognition.go**: **严重程度**：

#### MaaEnd/agent/go-service/essencefilter/matchapi/matcher.go

- **MaaEnd/agent/go-service/essencefilter/matchapi/matcher.go**: `matcher.go:466-505` 资源泄漏/内存风险
- **MaaEnd/agent/go-service/essencefilter/matchapi/matcher.go**: `matcher.go:345-352` 逻辑缺陷/静默失败
- **MaaEnd/agent/go-service/essencefilter/matchapi/matcher.go**: `matcher.go:265-394` 违反 SRP
- **MaaEnd/agent/go-service/essencefilter/matchapi/matcher.go**: `matcher.go:105-119` 误导性命名
- **MaaEnd/agent/go-service/essencefilter/matchapi/matcher.go**: `matcher.go:466-505` 资源泄漏 / 内存风险
- **MaaEnd/agent/go-service/essencefilter/matchapi/matcher.go**: `matcher.go:105-119, 345-352` 逻辑缺陷 / 死代码

#### src/core/service/navigation/vlm_walk_navigator.py

- **src/core/service/navigation/vlm_walk_navigator.py**: 49 配置失效
- **src/core/service/navigation/vlm_walk_navigator.py**: 288-297 异常处理
- **src/core/service/navigation/vlm_walk_navigator.py**: 124-258 稳定性
- **src/core/service/navigation/vlm_walk_navigator.py**: 219, 226 稳定性
- **src/core/service/navigation/vlm_walk_navigator.py**: 252 指标失真
- **src/core/service/navigation/vlm_walk_navigator.py**: 194-195, 299-301 资源/性能
- **src/core/service/navigation/vlm_walk_navigator.py**: 281-282 线程阻塞
- **src/core/service/navigation/vlm_walk_navigator.py**: —
  - 位置: navigator.py

#### src/gui/pyqt6/cli_bridge.py

- **src/gui/pyqt6/cli_bridge.py**: **严重程度**
- **src/gui/pyqt6/cli_bridge.py**: **严重程度**：

#### MaaEnd/agent/go-service/autostockpile/types.go

- **MaaEnd/agent/go-service/autostockpile/types.go**: 稳定性 nil map 写操作将引发 panic
- **MaaEnd/agent/go-service/autostockpile/types.go**: 稳定性 状态分类方法与校验逻辑不一致
- **MaaEnd/agent/go-service/autostockpile/types.go**: 代码质量 白名单使用线性搜索，可维护性差

#### src/core/capability/element_recognition/scene_service.py

- **src/core/capability/element_recognition/scene_service.py**: 稳定性 行 94
- **src/core/capability/element_recognition/scene_service.py**: 稳定性 行 122–134
- **src/core/capability/element_recognition/scene_service.py**: 用户不友好 行 104–112
- **src/core/capability/element_recognition/scene_service.py**: 稳定性 第 94 行
- **src/core/capability/element_recognition/scene_service.py**: 稳定性 第 122–134 行
- **src/core/capability/element_recognition/scene_service.py**: 用户不友好 第 104–112 行

#### src/core/capability/element_recognition/element_info.py

- **src/core/capability/element_recognition/element_info.py**: **严重程度**：

#### src/gui/pyqt6/queue_state.py

- **src/gui/pyqt6/queue_state.py**: 综合审计报告 未修复，`write_text` 直接覆盖
- **src/gui/pyqt6/queue_state.py**: 综合审计报告 未修复，所有集合操作无线程同步
- **src/gui/pyqt6/queue_state.py**: 3 键类型不一致、空字符串语义错误、无效数据静默丢弃
- **src/gui/pyqt6/queue_state.py**: `src/gui/pyqt6/queue_state.py`
  - 位置: src/gui/pyqt6/queue_state.py

#### MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp

- **MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp**: 竞态条件 337–366、431
- **MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp**: 静默失败 443–446
- **MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp**: 异常处理缺失 100–106
- **MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp**: 静默失败 383–385
- **MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp**: 错误信息不明确 422

#### MaaEnd/agent/go-service/autostockpile/overrides.go

- **MaaEnd/agent/go-service/autostockpile/overrides.go**: **严重程度**：

#### MaaEnd/agent/go-service/autostockpile/reconcile.go

- **MaaEnd/agent/go-service/autostockpile/reconcile.go**: 118 死代码 / 误导性条件
- **MaaEnd/agent/go-service/autostockpile/reconcile.go**: 138–146, 169–174, 205–213 重复代码（DRY 违反）
- **MaaEnd/agent/go-service/autostockpile/reconcile.go**: 160–167, 196–203 重复代码（DRY 违反）
- **MaaEnd/agent/go-service/autostockpile/reconcile.go**: 17–227（全函数） 职责过多 / SRP 违反

#### MaaEnd/agent/go-service/autostockpile/daily_storage.go

- **MaaEnd/agent/go-service/autostockpile/daily_storage.go**: 78-84 状态不一致
- **MaaEnd/agent/go-service/autostockpile/daily_storage.go**: 197 输入切片副作用
- **MaaEnd/agent/go-service/autostockpile/daily_storage.go**: 34 空指针风险
- **MaaEnd/agent/go-service/autostockpile/daily_storage.go**: 206-213 数据一致性

#### MaaEnd/agent/cpp-algo/source/MapLocator/MapLocator.cpp

- **MaaEnd/agent/cpp-algo/source/MapLocator/MapLocator.cpp**: **严重程度：**

### 2.4 P3 — 长期优化

#### src/core/capability/element_recognition/backends/scene_geometry.py

- **src/core/capability/element_recognition/backends/scene_geometry.py**: 无错误处理：`analyze` 方法中 `cv2.cvtColor` 等调用无 try/except 保护 #73
- **src/core/capability/element_recognition/backends/scene_geometry.py**: saliency 顶部权重被覆盖：`_extract_candidates` 中 0.12 区域被两次缩放 #74, #95
- **src/core/capability/element_recognition/backends/scene_geometry.py**: 魔法数字泛滥：大量硬编码阈值、权重、FOV 参数 #75
- **src/core/capability/element_recognition/backends/scene_geometry.py**: 误导性命名：`estimated_distance_m` 和 `view_angle_deg` 语义不准确 #76
- **src/core/capability/element_recognition/backends/scene_geometry.py**: 冗余字段：`contact_point_px` 与 `ground_contact_px` 存相同值 #77
- **src/core/capability/element_recognition/backends/scene_geometry.py**: `_estimate_ground` 算法复杂度偏高 #78
- **src/core/capability/element_recognition/backends/scene_geometry.py**: 冗余类型转换：`hsv[:, :, 1].astype(np.float32)` 重复操作 #79
- **src/core/capability/element_recognition/backends/scene_geometry.py**: 零测试覆盖 #80

#### MaaEnd/agent/go-service/essencefilter/matchapi/matcher.go

- **MaaEnd/agent/go-service/essencefilter/matchapi/matcher.go**: `matcher.go:265-394` 性能
- **MaaEnd/agent/go-service/essencefilter/matchapi/matcher.go**: `matcher.go:191-235` 状态不同步/误导性输出
- **MaaEnd/agent/go-service/essencefilter/matchapi/matcher.go**: `matcher.go:449-463` 操作无反馈
- **MaaEnd/agent/go-service/essencefilter/matchapi/matcher.go**: `matcher.go:46` 硬编码魔法数
- **MaaEnd/agent/go-service/essencefilter/matchapi/matcher.go**: `matcher.go:156-159` 数据一致性隐患
- **MaaEnd/agent/go-service/essencefilter/matchapi/matcher.go**: `matcher.go:507-519` 重复代码
- **MaaEnd/agent/go-service/essencefilter/matchapi/matcher.go**: `matcher.go:265-394` 性能 / 资源消耗
- **MaaEnd/agent/go-service/essencefilter/matchapi/matcher.go**: `matcher.go:191-235` 状态不一致

#### MaaEnd/agent/cpp-algo/source/RecoGrid/GridRecognizer.cpp

- **MaaEnd/agent/cpp-algo/source/RecoGrid/GridRecognizer.cpp**: 22–48 用户不友好设计 — 静默失败
- **MaaEnd/agent/cpp-algo/source/RecoGrid/GridRecognizer.cpp**: 65–95 用户不友好设计 — 静默丢弃输入
- **MaaEnd/agent/cpp-algo/source/RecoGrid/GridRecognizer.cpp**: 97–103 稳定性 — 边界检查缺失
- **MaaEnd/agent/cpp-algo/source/RecoGrid/GridRecognizer.cpp**: 34–36, 271 代码质量 — 静默截断
- **MaaEnd/agent/cpp-algo/source/RecoGrid/GridRecognizer.cpp**: 161 代码质量 — 潜在整数溢出

#### MaaEnd/agent/go-service/common/autoalt/long_press.go

- **MaaEnd/agent/go-service/common/autoalt/long_press.go**: **严重程度**：

#### MaaEnd/agent/go-service/autofight/screenanalyzer.go

- **MaaEnd/agent/go-service/autofight/screenanalyzer.go**: 86-103, 107-109 调试功能不可用
- **MaaEnd/agent/go-service/autofight/screenanalyzer.go**: 56, 125, 243, 262, 270, 278, 282, 286, 292, 296, 315, 319, 323, 376, 386, 396, 406, 416, 426, 434, 438, 442 魔法数
- **MaaEnd/agent/go-service/autofight/screenanalyzer.go**: 234-238, 257-259, 289, 300, 326-331, 333-338 硬编码屏幕坐标
- **MaaEnd/agent/go-service/autofight/screenanalyzer.go**: 54-63, 124-132 违反 DRY 原则
- **MaaEnd/agent/go-service/autofight/screenanalyzer.go**: `MaaEnd/agent/go-service/autofight/screenanalyzer.go`
  - 位置: MaaEnd/agent/go-service/autofight/screenanalyzer.go

#### MaaEnd/agent/cpp-algo/source/MapNavigator/steering_controller.cpp

- **MaaEnd/agent/cpp-algo/source/MapNavigator/steering_controller.cpp**: 25–51 输入无校验（NaN/Inf Propagation）
- **MaaEnd/agent/cpp-algo/source/MapNavigator/steering_controller.cpp**: 31, 49–50 操作无反馈（生产环境）
- **MaaEnd/agent/cpp-algo/source/MapNavigator/steering_controller.cpp**: 14–21 硬编码魔法数
- **MaaEnd/agent/cpp-algo/source/MapNavigator/steering_controller.cpp**: 25–26 缺乏文档
- **MaaEnd/agent/cpp-algo/source/MapNavigator/steering_controller.cpp**: 25–51 缺乏文档

#### src/core/capability/element_recognition/element_info.py

- **src/core/capability/element_recognition/element_info.py**: **严重程度**：

#### MaaEnd/agent/go-service/autostockpile/daily_storage.go

- **MaaEnd/agent/go-service/autostockpile/daily_storage.go**: 46-48 静默失败
- **MaaEnd/agent/go-service/autostockpile/daily_storage.go**: 50-52 静默丢弃输入
- **MaaEnd/agent/go-service/autostockpile/daily_storage.go**: 全文 无操作反馈
- **MaaEnd/agent/go-service/autostockpile/daily_storage.go**: 69
  - 位置: debug/record/ElasticGoodsPrices.json
- **MaaEnd/agent/go-service/autostockpile/daily_storage.go**: 17 测试缝侵入生产
- **MaaEnd/agent/go-service/autostockpile/daily_storage.go**: 92, 101 硬编码魔法数
- **MaaEnd/agent/go-service/autostockpile/daily_storage.go**: 14 硬编码魔法数

#### MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp

- **MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp**: 信息泄露 347–348
- **MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp**: 资源未释放（线程阻塞） 468
- **MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp**: 未定义行为（潜在） 166–170
- **MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp**: 状态不一致 474–477
- **MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp**: 硬编码魔法数 / 依赖环境 341–342
- **MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp**: 硬编码魔法数 214
- **MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp**: 误导性命名 277–288

#### MaaEnd/agent/go-service/common/clearhitcount/action.go

- **MaaEnd/agent/go-service/common/clearhitcount/action.go**: **严重程度**

#### MaaEnd/agent/cpp-algo/source/RecoGrid/GridDetector.cpp

- **MaaEnd/agent/cpp-algo/source/RecoGrid/GridDetector.cpp**: 代码质量 行 21–56、58–83**
- **MaaEnd/agent/cpp-algo/source/RecoGrid/GridDetector.cpp**: 代码质量/性能 行 108**
- **MaaEnd/agent/cpp-algo/source/RecoGrid/GridDetector.cpp**: 稳定性 行 142**
- **MaaEnd/agent/cpp-algo/source/RecoGrid/GridDetector.cpp**: 稳定性/用户不友好 行 143–151**
- **MaaEnd/agent/cpp-algo/source/RecoGrid/GridDetector.cpp**: 代码质量 行 92、85–106**
- **MaaEnd/agent/cpp-algo/source/RecoGrid/GridDetector.cpp**: 代码质量 行 187–194**

#### src/core/capability/element_recognition/scene_service.py

- **src/core/capability/element_recognition/scene_service.py**: 用户不友好 行 77–82
- **src/core/capability/element_recognition/scene_service.py**: 稳定性 行 78
- **src/core/capability/element_recognition/scene_service.py**: 稳定性 全类（无特定行）
- **src/core/capability/element_recognition/scene_service.py**: 用户不友好 第 77–82 行
- **src/core/capability/element_recognition/scene_service.py**: 稳定性 第 78 行

#### MaaEnd/agent/cpp-algo/source/MapLocator/MapLocator.cpp

- **MaaEnd/agent/cpp-algo/source/MapLocator/MapLocator.cpp**: **严重程度：**

#### src/gui/pyqt6/pages/settings_page.py

- **src/gui/pyqt6/pages/settings_page.py**: 数据竞争 / 无原子写入 / 无脏状态跟踪 / 无浏览按钮（ #41-43）
- **src/gui/pyqt6/pages/settings_page.py**: **严重程度**

#### src/gui/pyqt6/theme/icons.py

- **src/gui/pyqt6/theme/icons.py**: **严重程度**：

## 3. 跨模块风险总结

### 3.1 高频问题模式

- **静默失败**: 39 次提及
- **硬编码/魔法数**: 21 次提及
- **死代码**: 10 次提及
- **资源泄漏**: 10 次提及
- **异常处理缺失**: 7 次提及
- **命令/代码注入**: 6 次提及
- **竞态条件**: 5 次提及
- **超时缺失**: 4 次提及

## 4. 修复优先级建议

### 第一波（1 天内）

基于 176 个 agent 的交叉验证，以下问题被多个独立模块重复报告，置信度最高：

1. **`_sync_execute` 阻塞 GUI / 超时 1200ms** — 被多个 GUI 模块独立报告，直接导致任务执行失败
2. **空预设清空队列 / 选项合并顺序错误** — 队列/任务模块报告的数据丢失风险
3. **ADB shell 命令注入** — 设备控制层广泛存在，本地权限提升风险
4. **守护进程零认证** — 网络服务暴露无认证，本地恶意软件可完全控制设备
5. **And/Or 恒真匹配** — 自动化流程误触发，被多个识别后端报告

### 第二波（1 周内）

1. **资源泄漏系统性存在** — socket/进程/文件描述符/goroutine 在多个模块中被报告
2. **异常处理一刀切** — 多个 handler/模块宽泛捕获 Exception，掩盖真实错误
3. **状态单向闩锁** — 连接/任务状态在多处为单向更新，失败时不回写
4. **HTML 转义缺失** — 日志/聊天页面存在注入风险
5. **Agent 启动时序/就绪等待** — Go service 初始化时序错误

### 第三波（技术债登记）

1. **死代码累积** — 多个文件存在未使用方法/类
2. **误导性命名** — Proxy/Adapter/Facade 命名与实际实现不符
3. **性能微调类问题** — O(n²) 拼接、正则未预编译、路径重复 I/O
4. **架构重构需求** — PipelineRunner 违反 SRP、TaskRunner 注入缺失

## 5. 审计局限说明

1. **静态分析为主**：本次审计以静态代码分析为主，未进行动态 runtime 验证
2. **Pipeline JSON 部分覆盖**：已审计 ~100 个 pipeline/task JSON，但 MaaEnd/assets/resource/pipeline/ 仍有部分未覆盖
3. **测试覆盖缺口**：部分模块零测试覆盖，审计发现可能遗漏运行时行为问题
4. **外部依赖**：未审计 3rd-part/ 第三方依赖（ADB、llama-cpp、ultralytics 等）
5. **C 扩展层**：MaaFramework C++ DLL 内部实现未审计，可能存在未暴露的风险

## 6. 完整发现清单（按模块）

以下列出各模块的主要发现，完整细节请参考各子代理原始输出。

### MaaEnd/agent/cpp-algo/source

审计文件数: 47，发现提及数: 128

- [P2] MaaEnd/agent/cpp-algo/source/MapLocator/MapLocator.cpp: **严重程度：**
- [P3] MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp: 信息泄露 347–348
- [P1] MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp: 空指针解引用 303
- [P1] MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp: 资源未释放（线程阻塞） 305
- [P2] MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp: 竞态条件 337–366、431
- [P2] MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp: 静默失败 443–446
- [P2] MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp: 异常处理缺失 100–106
- [P3] MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp: 资源未释放（线程阻塞） 468
- [P3] MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp: 未定义行为（潜在） 166–170
- [P2] MaaEnd/agent/cpp-algo/source/MapLocator/MapLocateAction.cpp: 静默失败 383–385

### src/core/capability

审计文件数: 22，发现提及数: 97

- [P1] src/core/capability/device/adb_manager.py: `src/core/capability/device/adb_manager.py`
- [P0] src/core/capability/device/android_runtime.py: 任意 ADB shell 命令注入 486-490
- [P0] src/core/capability/device/android_runtime.py: 守护进程零认证 355-360
- [P0] src/core/capability/device/android_runtime.py: `_decode_loop` socket/fileobj 泄漏 292
- [P1] src/core/capability/device/android_runtime.py: `_call` 无 socket 读取超时 570-575
- [P1] src/core/capability/device/android_runtime.py: `_Daemon` 无 `_tcp_port` 初始化 357-358
- [P1] src/core/capability/device/android_runtime.py: `_ScrcpySession._codec` 未在 stop 时关闭 296-317
- [P1] src/core/capability/device/android_runtime.py: `_call` 的 tap/swipe 忽略错误返回 558-583
- [P1] src/core/capability/device/android_runtime.py: `_push_jar` 吞掉所有失败 121-133
- [P1] src/core/capability/device/android_runtime.py: `_check_jar_cached` 吞掉 ADB 错误 108-116

### MaaEnd/agent/go-service/autostockpile

审计文件数: 21，发现提及数: 69

- [P2] MaaEnd/agent/go-service/autostockpile/register.go: **严重程度**：
- [P2] MaaEnd/agent/go-service/autostockpile/decision.go: 28 代码质量 / 死代码 / 误导性错误处理
- [P2] MaaEnd/agent/go-service/autostockpile/strategy.go: 19-38 魔法数硬编码：价格阈值、调整值全部在源码中，缺少外部配置入口
- [P2] MaaEnd/agent/go-service/autostockpile/strategy.go: 64-65 `loc` 参数无 nil 检查，可能 panic
- [P3] MaaEnd/agent/go-service/autostockpile/strategy.go: 52 错误消息 `%d` 格式化 `time.Weekday`，输出整数而非可读名称
- [P3] MaaEnd/agent/go-service/autostockpile/strategy.go: 64-66 `buildSelectionConfig` 仅做一步转换后转发，职责可合并
- [P2] MaaEnd/agent/go-service/autostockpile/strategy.go: 3 稳定性(2)、代码质量(1)
- [P3] MaaEnd/agent/go-service/autostockpile/strategy.go: 2 用户不友好设计(1)、代码质量(1)
- [P0] MaaEnd/agent/go-service/autostockpile/strategy.go: 0 —
- [P0] MaaEnd/agent/go-service/autostockpile/options.go: **安全漏洞（-）**：文件仅涉及 JSON 反序列化与数值范围校验，无命令执行、路径遍历、敏感信息泄露或资源未释放路径。`loadAutoStockpileAttach` 对 `ctx` 与 `no

### src/gui/pyqt6

审计文件数: 21，发现提及数: 69

- [P3] src/gui/pyqt6/main.py: `src/gui/pyqt6/main.py`
- [P2] src/gui/pyqt6/cli_bridge.py: **严重程度**
- [P2] src/gui/pyqt6/cli_bridge.py: **严重程度**：
- [P1] src/gui/pyqt6/pages/settings_page.py: `_save_settings` 无异常处理（ #38）
- [P1] src/gui/pyqt6/pages/settings_page.py: 每次按键触发完整 JSON 读写（ #39）
- [P2] src/gui/pyqt6/pages/settings_page.py: `_raw_preview` 误导读名（ #40）
- [P2] src/gui/pyqt6/pages/settings_page.py: `_apply_preview_interval` 紧耦合（ #41）
- [P3] src/gui/pyqt6/pages/settings_page.py: 数据竞争 / 无原子写入 / 无脏状态跟踪 / 无浏览按钮（ #41-43）
- [P0] src/gui/pyqt6/pages/log_page.py: **** `log_page.py:121` — HTML 转义 no-op（使用 `line.replace("&", "&")` 等无效替换），导致 Qt 渲染执行恶意内容。
- [P2] src/gui/pyqt6/pages/log_page.py: **** `log_page.py:70–72` — 刷新按钮仅连接 `_load_selected_log`，不刷新文件列表。

### MaaEnd/agent/go-service/essencefilter

审计文件数: 20，发现提及数: 55

- [P3] MaaEnd/agent/go-service/essencefilter/register.go: `MaaEnd/agent/go-service/essencefilter/register.go`
- [P2] MaaEnd/agent/go-service/essencefilter/actionsAfterBattle.go: 34 日志注入
- [P1] MaaEnd/agent/go-service/essencefilter/actionsAfterBattle.go: 44–59
- [P2] MaaEnd/agent/go-service/essencefilter/actionsAfterBattle.go: 33–35, 39–41 反馈缺失/静默失败
- [P3] MaaEnd/agent/go-service/essencefilter/actionsAfterBattle.go: 75–76 硬编码魔法数/误导性注释
- [P3] MaaEnd/agent/go-service/essencefilter/actionsAfterBattle.go: 44–59 误导性命名/隐式控制流
- [P2] MaaEnd/agent/go-service/essencefilter/ocr_utils.go: `MaaEnd/agent/go-service/essencefilter/ocr_utils.go`
- [P0] MaaEnd/agent/go-service/essencefilter/resource_path.go: 0 -
- [P2] MaaEnd/agent/go-service/essencefilter/resource_path.go: 3 静默失败 ×2、状态不一致 ×1
- [P3] MaaEnd/agent/go-service/essencefilter/resource_path.go: 3 死代码 ×2、信息泄露 ×1

### MaaEnd/agent/go-service/common

审计文件数: 22，发现提及数: 46

- [P0] MaaEnd/agent/go-service/common/subtask/action.go: 信息泄露 33
- [P1] MaaEnd/agent/go-service/common/subtask/action.go: 异常处理缺失/超时缺失 108
- [P1] MaaEnd/agent/go-service/common/subtask/action.go: 静默失败 62
- [P1] MaaEnd/agent/go-service/common/subtask/action.go: 异常处理缺失/状态不一致 74
- [P2] MaaEnd/agent/go-service/common/subtask/action.go: 错误信息不明确 89
- [P2] MaaEnd/agent/go-service/common/subtask/action.go: 操作无反馈/状态不同步 62, 115
- [P2] MaaEnd/agent/go-service/common/subtask/action.go: 静默丢弃输入 54, 97
- [P3] MaaEnd/agent/go-service/common/subtask/action.go: 重复代码/误导性防御 54, 97
- [P3] MaaEnd/agent/go-service/common/subtask/action.go: 违反 SRP/可读性差 23-134
- [P3] MaaEnd/agent/go-service/common/subtask/action.go: 误导性命名 93

### src/core/service

审计文件数: 7，发现提及数: 40

- [P1] src/core/service/runtime.py: `src/core/service/runtime.py`
- [P1] src/core/service/navigation/navigator.py: **严重程度**
- [P2] src/core/service/navigation/vlm_walk_navigator.py: 49 配置失效
- [P2] src/core/service/navigation/vlm_walk_navigator.py: 288-297 异常处理
- [P2] src/core/service/navigation/vlm_walk_navigator.py: 124-258 稳定性
- [P2] src/core/service/navigation/vlm_walk_navigator.py: 219, 226 稳定性
- [P2] src/core/service/navigation/vlm_walk_navigator.py: 252 指标失真
- [P2] src/core/service/navigation/vlm_walk_navigator.py: 194-195, 299-301 资源/性能
- [P2] src/core/service/navigation/vlm_walk_navigator.py: 281-282 线程阻塞
- [P2] src/core/service/navigation/vlm_walk_navigator.py: —

### MaaEnd/agent/go-service/autofight

审计文件数: 5，发现提及数: 18

- [P1] MaaEnd/agent/go-service/autofight/screenanalyzer.go: 50-52, 全体方法 竞态条件
- [P2] MaaEnd/agent/go-service/autofight/screenanalyzer.go: 80-82 资源浪费/空帧堆积
- [P2] MaaEnd/agent/go-service/autofight/screenanalyzer.go: 54-63, 124-132 重复逻辑
- [P3] MaaEnd/agent/go-service/autofight/screenanalyzer.go: 86-103, 107-109 调试功能不可用
- [P2] MaaEnd/agent/go-service/autofight/screenanalyzer.go: 89-103 死代码路径
- [P2] MaaEnd/agent/go-service/autofight/screenanalyzer.go: 139-168 死代码
- [P3] MaaEnd/agent/go-service/autofight/screenanalyzer.go: 56, 125, 243, 262, 270, 278, 282, 286, 292, 296, 315, 319, 323, 376, 386, 396, 406, 416, 426, 434, 4
- [P3] MaaEnd/agent/go-service/autofight/screenanalyzer.go: 234-238, 257-259, 289, 300, 326-331, 333-338 硬编码屏幕坐标
- [P3] MaaEnd/agent/go-service/autofight/screenanalyzer.go: 54-63, 124-132 违反 DRY 原则
- [P1] MaaEnd/agent/go-service/autofight/screenanalyzer.go: `MaaEnd/agent/go-service/autofight/screenanalyzer.go`

### src/cli/handlers.py

审计文件数: 1，发现提及数: 11

- [P1] src/cli/handlers.py: `src/cli/handlers.py`
- [P1] src/cli/handlers.py: 3 静默失败、状态不一致、崩溃风险
- [P2] src/cli/handlers.py: 3 类型不一致、静默失败、DRY违反
- [P3] src/cli/handlers.py: 2 逻辑错误、误导性提示

### MaaEnd/agent/go-service/stderr_windows.go

审计文件数: 1，发现提及数: 6

- [P2] MaaEnd/agent/go-service/stderr_windows.go: **严重程度：**

### src/core/foundation

审计文件数: 3，发现提及数: 4

- [P2] src/core/foundation/paths.py: **严重程度**：
- [P3] src/core/foundation/gpu_check.py: `src/core/foundation/gpu_check.py`

### src/cli/istina.py

审计文件数: 1，发现提及数: 3

- [P3] src/cli/istina.py: ** #16**: `_json_dumps` 重复定义 (handlers.py:23-27 / istina.py:224-228) — 不要重复报告
- [P3] src/cli/istina.py: **对用户的影响**：外部脚本或攻击者可借此了解内部目录结构、运行时状态及配置信息。与报告中 handlers.py 特定 handler 的泄露（ #11/#12）不同，此处是全局兜底暴露面，覆盖所
- [P3] src/cli/istina.py: **具体描述**：`scene identify/verify/elements` 与 `llm prompt` 的 `--image` 参数接受 base64 数据，但未设置任何大小上限。报告中仅在

### MaaEnd/agent/go-service/register.go

审计文件数: 1，发现提及数: 1

- [P1] MaaEnd/agent/go-service/register.go: **严重程度**

### MaaEnd/agent/go-service/stderr_other.go

审计文件数: 1，发现提及数: 1

- [P2] MaaEnd/agent/go-service/stderr_other.go: `MaaEnd/agent/go-service/stderr_other.go`

### MaaEnd/agent/go-service/version.go

审计文件数: 1，发现提及数: 0


### MaaEnd/agent/go-service/autosell

审计文件数: 2，发现提及数: 0


---

**报告生成方式**: 176 个 Agent Swarm 子代理并行审计 + 自动聚合
**下一步**: 基于本报告制定按波次修复计划，优先处理 P0 逻辑硬伤。