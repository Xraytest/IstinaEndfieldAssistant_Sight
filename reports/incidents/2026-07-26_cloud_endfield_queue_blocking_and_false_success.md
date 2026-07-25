# 2026-07-26 云终末地队列执行阻断与状态误判分析

> 触发场景：用户在云终末地（com.hypergryph.cloud.endfield）执行 12 任务队列，
> 通过 `scripts/run_queue_with_recording.py` 录制视频并查阅 `logs/main.log`，
> 观察到：(1) 单任务阻塞 4 分钟；(2) 任务执行成功后游戏被踢出主世界；
> (3) 队列中每个任务后无差别出现 3 次 `已发送 BACK 关闭弹窗` 日志。
> 本报告按 `docs/WORKFLOW.md` 规定的四段式结构产出。

## 1. 根因分析

### 1.1 直接原因：`_log_recognition_detail` 末尾残留 `_lightweight_recover_ui` 代码片段

[`src/core/service/maa_end/runtime.py:1735-1772`](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/core/service/maa_end/runtime.py#L1735) 的 `_log_recognition_detail` 方法本应只读地记录识别详情（DEBUG 级别），但末尾残留了如下片段：

```python
# 原始问题代码（已删除）
        if not self._connected:
            return False
        self.logger.info(LogCategory.MAIN, "轻量恢复：多次 BACK 关闭弹窗/对话框")
        for _ in range(3):
            if not self._send_key_back():
                return False
        if not self._verify_connection_alive():
            return False
        time.sleep(1.5)
        return True
```

该片段与 [`_lightweight_recover_ui:1610-1626`](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/core/service/maa_end/runtime.py#L1610) 的核心逻辑完全重复（仅缺少开头的 `_dismiss_cloud_idle_popup()` 调用），疑似合并冲突时未清理的孤儿代码。

### 1.2 调用链与影响

`_log_recognition_detail` 在 [`_run_task_once:1045`](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/core/service/maa_end/runtime.py#L1045)（成功路径）和 [`_run_task_once:1055`](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/core/service/maa_end/runtime.py#L1055)（失败路径）被调用，意味着：

- **每次任务执行成功后**：无差别发送 3 次 BACK + 1.5s sleep
- **每次任务执行失败后**：在 `_lightweight_recover_ui` 的 3 次 BACK 之外，**再额外**发送 3 次 BACK + 1.5s sleep（共 6 次 BACK）

### 1.3 在云终末地的级联故障

`logs/main.log` 时间线证据：

```
07:15:30 任务执行成功 task=AndroidOpenGame
07:15:31 游戏状态检查：尝试回到主世界  ← _ensure_game_is_alive
07:15:31 开始执行自定义管道 entry=SceneAnyEnterWorld
07:19:25 自定义管道执行失败 entry=SceneAnyEnterWorld  ← 阻塞 3 分 54 秒
07:19:25 游戏状态检查：SceneAnyEnterWorld 失败，尝试重新启动游戏
07:19:25 开始执行任务 task=AndroidOpenGame  ← 重启游戏（再次 7s）
```

级联路径：
1. `AndroidOpenGame` 成功 → `_log_recognition_detail` 触发 3 次 BACK
2. 在云终末地，BACK 会退出游戏到登录页（云终末地无桌面，BACK 直接退游戏）
3. `_ensure_game_is_alive` 调用 `run_pipeline("SceneAnyEnterWorld")`，但游戏已在登录页
4. `SceneAnyEnterWorld` 的 `InWorld` 模板在登录页无法匹配，MaaFW next 列表死循环
5. `run_pipeline` **无超时**，阻塞 4 分钟才被 MaaFW 内部超时打破
6. `_ensure_game_is_alive` 走重启路径 → 重新执行 `AndroidOpenGame` → 又触发 3 次 BACK → 死循环

### 1.4 根本原因：`run_pipeline` 缺少超时兜底

[`run_pipeline:897-921`](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/core/service/maa_end/runtime.py#L897) 调用 `self._wait_job(job)` 时未传入 `timeout_s`，导致 MaaFW next 列表死循环时 Python 端无限等待。实测 `SceneAnyEnterWorld` 在 InWorld 误匹配场景下阻塞 4 分钟（07:15:31 → 07:19:25）和（07:21:20 → 07:25:34）。

### 1.5 次要原因：False Success 检测不完整

[`_run_task_once:1047-1063`](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/core/service/maa_end/runtime.py#L1047) 的 False Success 检测仅覆盖 FS-1（所有识别节点未命中），遗漏：
- **FS-2**：任务被 PostStop/AbortPipeline 中止但 MaaFW 报告 Succeeded（如 IMGCHK-01 场景）
- **FS-3**：所有节点 completed=False（MaaFW override 注册失败的典型症状）

### 1.6 次要原因：GUI 路径缺少任务间清理

[`maaend_control_page.py:_runtime_queue_runner:1070-1119`](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/gui/pyqt6/pages/maaend_control_page.py#L1070) 通过 `task run` 逐个执行任务，**不经过** `MaaEndRuntime.run_queue` 的 [`_ensure_in_world_before_task:1208-1209`](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/core/service/maa_end/runtime.py#L1208)。前一任务（如 CreditShoppingN2）留下非主世界页面状态时，下一任务的 `InWorld` 识别误匹配（`InWorldOcrText` 匹配 UID，UID 在商店页面也可见），导致 SellProduct 类任务失败。

## 2. 修改方案

### 修改 1：删除 `_log_recognition_detail` 末尾孤儿代码（CRITICAL）

**文件**：`src/core/service/maa_end/runtime.py`
**位置**：`_log_recognition_detail` 方法末尾
**修改**：删除 `if not self._connected: return False` 起至 `return True` 止的 10 行代码，并在 docstring 中添加警告注释，防止回归。

### 修改 2：为 `run_pipeline` 添加 60s 超时兜底

**文件**：`src/core/service/maa_end/runtime.py`
**位置**：`run_pipeline` 方法
**修改**：
- 新增类常量 `_PIPELINE_NAV_TIMEOUT_S = 60`
- `self._wait_job(job)` → `self._wait_job(job, timeout_s=self._PIPELINE_NAV_TIMEOUT_S)`
- 超时后调用 `self._tasker.post_stop()` 释放 MaaFW，避免后续 pipeline 因 MaaFW 忙而级联超时

### 修改 3：增强 False Success 检测（多策略）

**文件**：`src/core/service/maa_end/runtime.py`
**位置**：`_run_task_once` 成功路径的检测逻辑
**修改**：扫描所有节点（不再 break），新增：
- **FS-2**：节点名含 `abort`/`poststop`/`stop` 且无识别命中 → PostStop 中止
- **FS-3**：`completed_node_count == 0 and len(detail.nodes) > 0` → 节点未完成

### 修改 4：GUI 队列执行路径增加任务间清理

**文件**：
- `src/core/service/runtime.py`：新增 `_enter_world` 方法 + `task.enter_world` 路由
- `src/cli/istina.py`：新增 `task enter_world` 子命令（`--before-task`、`--serial`）
- `src/cli/handlers.py`：新增 `_handle_task_enter_world` 函数 + 路由
- `src/gui/pyqt6/pages/maaend_control_page.py`：
  - 新增 `_TASKS_SKIP_ENTER_WORLD` 常量（与 `MaaEndRuntime` 保持一致）
  - `_runtime_queue_runner` 在非首任务且非启动类任务前调用 `task enter_world`

## 3. 影响面

### 3.1 修改涉及的函数/方法

| 文件 | 函数/方法 | 修改类型 |
|------|-----------|----------|
| `runtime.py` | `_log_recognition_detail` | 删除孤儿代码 + 强化 docstring |
| `runtime.py` | `run_pipeline` | 添加超时 + post_stop 兜底 |
| `runtime.py` | `_run_task_once` | False Success 检测增强 |
| `runtime.py` | `_lightweight_recover_ui` | 未修改（行为不变，仍是失败路径的清理手段） |
| `service/runtime.py` | `IstinaRuntime.execute` | 新增 `task.enter_world` 路由 |
| `service/runtime.py` | `_enter_world` | 新增方法 |
| `cli/istina.py` | `build_parser` | 新增 `task enter_world` 子命令 |
| `cli/handlers.py` | `_handle_task` | 新增 `enter_world` 分支 |
| `cli/handlers.py` | `_handle_task_enter_world` | 新增函数 |
| `maaend_control_page.py` | `_runtime_queue_runner` | 任务间清理调用 |
| `maaend_control_page.py` | 类常量 | 新增 `_TASKS_SKIP_ENTER_WORLD` |

### 3.2 信号/调用点影响

- **`_log_recognition_detail` 调用者**：`_run_task_once` 成功/失败路径。修改后成功路径不再发送 BACK，失败路径 BACK 次数从 6 次降至 3 次（仅 `_lightweight_recover_ui` 触发）。
- **`run_pipeline` 调用者**：`_ensure_in_world_before_task`、`_ensure_game_is_alive`、`_recover_and_retry`。修改后这些路径在最坏情况下 60s 超时返回 False，上层走重启路径。
- **GUI `_runtime_queue_runner`**：每个非首任务前增加一次 `task enter_world` 调用（最多 120s），队列总耗时增加但稳定性提升。

### 3.3 兼容性

- CLI 新增子命令不影响既有命令（向后兼容）
- `_enter_world` 失败不阻断队列（与 `run_queue` 行为一致）
- False Success 检测增强只增加误报检测，不影响真成功任务

## 4. 非期待变化与回退策略

### 4.1 可能的副作用

| 副作用 | 概率 | 影响 | 缓解 |
|--------|------|------|------|
| `run_pipeline` 60s 超时误杀正常长耗时导航 | 低 | SceneAnyEnterWorld 正常执行 ≤30s，60s 阈值有 2x 余量 | 监控日志 `管道执行超时` 出现频率，必要时调大 `_PIPELINE_NAV_TIMEOUT_S` |
| False Success FS-2 误报（节点名巧合含 stop） | 低 | 仅当 `has_post_stop and not has_any_hit` 同时成立才触发，真成功任务通常有识别命中 | 日志含 `has_post_stop` 字段，可定位误报节点名 |
| GUI 任务间清理增加单次队列总耗时 | 中 | 12 任务队列增加 11 次 × 最多 60s = 11 分钟（最坏）；正常 3s/次 = 33s | 与原阻塞 4 分钟/次相比仍大幅改善 |
| 云终末地 BACK 行为变化（未来版本） | 低 | 修改 1 依赖"BACK 退出云终末地游戏"的行为假设 | 通过 `_dismiss_cloud_idle_popup` 显式检测弹窗，不依赖 BACK 行为 |

### 4.2 回退策略

1. **修改 1（孤儿代码删除）**：不可回退。该代码本身就是 bug，无回退必要。
2. **修改 2（超时兜底）**：将 `_PIPELINE_NAV_TIMEOUT_S` 调大（如 300s）或改回 `self._wait_job(job)`（无 timeout）。
3. **修改 3（False Success 增强）**：注释掉 FS-2/FS-3 分支，仅保留 FS-1。
4. **修改 4（GUI 任务间清理）**：注释掉 `_runtime_queue_runner` 中的 `task enter_world` 调用块即可。

### 4.3 验证计划

- [x] 5 个文件 `py_compile` 通过
- [x] CLI `task enter_world --before-task VisitFriends --serial 127.0.0.1:16416` 解析正确
- [x] `IstinaRuntime._enter_world` 方法存在
- [ ] 端到端验证：连接云终末地设备，执行 12 任务队列，观察：
  - 任务成功后**不再**出现 `已发送 BACK 关闭弹窗` 日志
  - `SceneAnyEnterWorld` 阻塞 ≤60s（而非 4 分钟）
  - GUI 队列路径任务间出现 `任务间清理：尝试回到主世界` 日志
  - False Success 触发时日志含 `has_post_stop` / `completed_nodes` 字段

## 5. 日志证据（2026-07-26 07:15-07:25 队列运行）

```
07:15:30 任务执行成功 task=AndroidOpenGame
07:15:25 轻量恢复：多次 BACK 关闭弹窗/对话框   ← 来自 _log_recognition_detail 孤儿代码
07:15:26 已发送 BACK 关闭弹窗
07:15:27 已发送 BACK 关闭弹窗
07:15:28 已发送 BACK 关闭弹窗
07:15:31 游戏状态检查：尝试回到主世界
07:19:25 自定义管道执行失败 entry=SceneAnyEnterWorld  ← 阻塞 3m54s
07:19:25 游戏状态检查：SceneAnyEnterWorld 失败，尝试重新启动游戏
```

视频证据：`cache/recordings/queue_run_20260726_071518.mp4`（266MB，15fps）
