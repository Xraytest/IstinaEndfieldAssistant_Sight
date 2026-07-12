# AndroidOpenGame_CN 未定义 + ADB screencap 回退违反策略

**日期**: 2026-07-12
**触发**: 用户反馈"严禁回退ADB screenshot，图像传输必须走scrcpy。执行队列时卡在游戏的仪表盘然后持续尝试退出到登入页面"

---

## 1. 根因分析

### 问题 A: ADB screencap 回退违反用户策略

上一轮 PREVIEW-01D 修复（commit 3645f82）在 daemon 截图处理器中添加了 ADB screencap 回退逻辑：当 scrcpy 无帧/帧过期时，回退到 `self._adb_manager.screencap(serial)` 获取截图。

用户明确要求"严禁回退ADB screenshot，图像传输必须走scrcpy"。此回退逻辑违反了用户的架构策略。

**代码位置**: `src/core/capability/device/android_runtime.py` L698-707（修改前）

### 问题 B: AndroidOpenGame_CN pipeline entry 未定义

`assets/tasks/AndroidOpenGame.json` 的 CN case 定义了 `pipeline_override`:
```json
{
    "AndroidOpenGame": {"next": ["AndroidOpenGame_CN"]},
    "CloseGame": {"next": ["CloseGame_CN"]}
}
```

但 `AndroidOpenGame_CN` 在所有 pipeline JSON 中**完全未定义**。对比 `CloseGame_CN` 在 `3rd-part/maaend/resource/pipeline/GameSwitch/CloseGame.json` 中有明确定义为空对象 `{}`。

**调用链**:
```
GUI 队列执行 → _runtime_queue_runner → _sync_execute("task run AndroidOpenGame")
→ CLI _run_task → maaend.run_task("AndroidOpenGame", {"ClientVersion": "CN"})
→ build_pipeline_override → override = {'AndroidOpenGame': {'next': ['AndroidOpenGame_CN']}, ...}
→ self._tasker.post_task("AndroidOpenGame", override)
→ MaaFW 执行 AndroidOpenGame → next: ["AndroidOpenGame_CN"] → 未定义
```

**MaaFW 对未定义 task 的行为不确定且不一致**。日志证据（2026-07-07）:

| 时间 | 耗时 | 结果 |
|------|------|------|
| 09:16:24 | 1s | 成功（未定义 task 被视为空节点，立即成功） |
| 09:19:48 | 180s | 超时（MaaEnd job timed out, timeout_s=180.0） |
| 09:24:46 | 24s | 失败 |
| 09:37:16 | 28s | 失败 |
| 09:42:50 | 44s | 失败 |

行为不一致是核心问题：有时 1s 成功（空节点），有时 180s 超时（MaaFW 内部行为不确定）。

### 问题 B 的连锁影响: "退出到登入页面"

当 MaaFW 对未定义的 `AndroidOpenGame_CN` 行为不一致时，可能出现以下场景：

1. **MaaFW 回退到原始 next**: override 将 `AndroidOpenGame.next` 改为 `["AndroidOpenGame_CN"]`，但 `AndroidOpenGame_CN` 未定义时，MaaFW 可能回退到原始 `next: ["OpenGame"]`
2. **OpenGame pipeline 在仪表盘上运行**: `OpenGame` 是登录流状态机，有 13 个 next 分支，其中包括 `CloseButton`（TemplateMatch, ROI [928,10,345,281], green_mask, threshold 0.65, action Click）
3. **EnterGame (InWorld) 不匹配**: 当游戏在仪表盘时，`InWorld`（Or(ProtosyncMenuButton, RegionalDevelopmentButton)）可能不匹配
4. **CloseButton 分支匹配并点击**: 绿色关闭按钮被点击 → 游戏退出到登入页面
5. **JumpBack 重试**: `[JumpBack]CloseButton` 点击后跳回 `OpenGame` 重试所有分支，形成"退出→重试→退出"循环

**直接原因**: `AndroidOpenGame_CN` 未定义，MaaFW 行为不一致，有时回退到 `OpenGame` pipeline，其 `CloseButton` 分支在仪表盘上被误匹配并点击。

**根本原因**: `assets/tasks/AndroidOpenGame.json` 的 CN/Bilibili/Global/VN override 引用了 `AndroidOpenGame_CN` 等变体，但对应 pipeline JSON 中缺少定义。

---

## 2. 修改方案

### 修改 1: 撤销 ADB screencap 回退（问题 A）

**文件**: `src/core/capability/device/android_runtime.py` L698-702

将 ADB screencap 回退替换为纯 scrcpy error 返回：

```python
# 修改前（PREVIEW-01D 添加的 ADB 回退）:
self._logger.info("daemon screenshot scrcpy 无帧/帧过期，回退 ADB screencap", serial=serial)
try:
    png_data = self._adb_manager.screencap(serial)
    if png_data and len(png_data) > 4 and png_data[:4] == b"\x89PNG":
        return self._encode_binary(png_data)
    ...
except Exception as exc:
    ...
return {"error": "screenshot failed: scrcpy 无帧且 ADB 回退失败"}

# 修改后:
self._logger.debug("daemon screenshot scrcpy 无帧/帧过期，等待会话自动恢复", serial=serial)
return {"error": "screenshot failed: scrcpy not ready"}
```

scrcpy 无帧/帧过期时返回 error，依赖 `_recv_exact` 的 `max_stalls=3`（90s 无数据强制重建会话）机制自动恢复。

### 修改 2: 定义 AndroidOpenGame_CN 及变体（问题 B）

**文件**: `3rd-part/maaend/resource/pipeline/OpenGame.json`

在 `AndroidOpenGame` 条目后添加 4 个空对象定义，匹配 `CloseGame_CN: {}` 的模式：

```json
"AndroidOpenGame_CN": {},
"AndroidOpenGame_Bilibili": {},
"AndroidOpenGame_Global": {},
"AndroidOpenGame_VN": {}
```

空对象 `{}` 在 MaaFW 中表示：
- 无 recognition → 总是匹配
- 无 action → 不执行任何操作
- 无 next → 任务链结束，成功返回

这使 CN/Bilibili/Global/VN 的 `AndroidOpenGame` override 指向一个明确定义的空节点，行为一致（始终 <1s 成功），避免 MaaFW 回退到原始 `OpenGame` pipeline 导致 `CloseButton` 分支在仪表盘上被误触发。

**设计意图**: 与 `CloseGame_CN: {}` 一致 — CN 客户端的开关游戏由外部管理（用户手动启动或 `_ensure_game_in_world`），MaaEnd pipeline 不参与。

---

## 3. 影响面

### 修改 1 影响面

| 组件 | 影响 |
|------|------|
| `android_runtime.py` daemon 截图处理器 | scrcpy 无帧时返回 error 而非 ADB 回退截图 |
| GUI 预览画面 | scrcpy 编码器停滞期间预览显示"已断开"而非 ADB 回退画面 |
| `_recv_exact` max_stalls 机制 | 不受影响，仍按 90s 无数据强制重建会话 |
| MaaEnd screencap | 不受影响，MaaEnd 使用独立的 ADB screencap 通道（不经过 daemon） |

### 修改 2 影响面

| 组件 | 影响 |
|------|------|
| `AndroidOpenGame` 任务（CN/Bilibili/Global/VN） | 从行为不一致变为始终 <1s 成功（空节点 no-op） |
| DailyFull / QuickDaily / RealtimeAssist 预设 | 首个任务 `AndroidOpenGame` 不再运行 `OpenGame` 登录流，需游戏已启动 |
| `OpenGame` pipeline | 不再被 AndroidOpenGame 的 CN override 间接触发 |
| `daily` 命令的 `_ensure_game_in_world` | 不受影响（直接调 `run_task("AndroidOpenGame")`，同样受 override 影响，但后续 `_wait_for_in_world` 会补偿） |
| `CloseGame` 任务 | 不受影响（`CloseGame_CN` 已定义） |

---

## 4. 非期待变化

### 修改 1 非期待变化

- **预览冻结时间延长**: scrcpy 编码器停滞期间（最多 90s）预览无法显示画面，用户可能感知"预览卡死"。这是 scrcpy 唯一通道策略的预期代价。回退策略：用户可手动重连设备触发 scrcpy 会话重建。
- **MaaEnd 任务执行不受影响**: MaaEnd 使用独立的 ADB screencap 通道，不经过 daemon 截图处理器，因此修改 1 不影响任务执行成功率。

### 修改 2 非期待变化

- **AndroidOpenGame 不再启动游戏**: CN 客户端下 `AndroidOpenGame` 变为 no-op，如果游戏未运行，后续任务会因场景不匹配而失败。回退策略：用户需确保游戏已启动并在大世界界面后再执行队列；或在 `daily` 命令中使用 `_ensure_game_in_world`（会先检查游戏进程并启动）。
- **`OpenGame` pipeline 不再被队列执行触发**: 如果用户期望 `AndroidOpenGame` 处理登录流（自动登录、跳过月卡等），此修改后这些功能在队列执行中不再可用。回退策略：将 `AndroidOpenGame_CN` 改为 `{"next": ["OpenGame"]}` 可恢复原行为，但需同时修复 `OpenGame` pipeline 的 `CloseButton` 分支在仪表盘上误匹配的问题。
- **Bilibili/Global/VN 客户端同样变为 no-op**: 所有客户端版本的 `AndroidOpenGame` 都变为空节点。这与 `CloseGame` 的设计一致。
