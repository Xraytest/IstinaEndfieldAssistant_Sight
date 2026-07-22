# AndroidOpenGame 误报成功 + 正常失败误触发 RecoverGame（OPENGAME-01 + RECOVER-01）

**时间**: 2026-07-22 08:00
**影响**: AndroidOpenGame 在签到弹窗阶段就误报"已进入大世界"，导致后续 VisitFriends 失败；失败后 _run_task_with_retry 误触发 RecoverGame（StopApp → StartApp → OpenGame），强制关闭刚启动的游戏
**严重度**: 高（队列第二任务必失败 + 游戏被反复重启）

## 1. 根因分析

### 现象

对 `cache/recordings/queue_run_20260722_073917.mp4` 抽帧 OCR（57 帧，2s 间隔）确认：

| 时间点 | 日志标记 | OCR 实际画面 |
|--------|----------|-------------|
| t=0~30s | AndroidOpenGame 启动中 | 健康提示 / 资源检查 / 资源加载 |
| t=32s | - | "点击任意位置继续"（登录页） |
| t=36~60s | - | "NOWLOADING.." + "UID: 1439188325"（加载中） |
| **t=62s** | **AndroidOpenGame 成功** | **"踞渊北眺签到 18天4小时 限时签到 参与签到累计可领取踞渊北眺寻访凭证*5" + "UID; 1439188325"（签到弹窗，非主世界）** |
| t=85s | VisitFriends 失败 | 弹窗仍遮挡 |
| t=113s | RecoverGame 触发 | 游戏被强制关闭 |

### 根因链

1. **`InWorldOcrText` 识别过松（OPENGAME-01·直接根因之一）**
   `3rd-part/maaend/resource/pipeline/Interface/InScene/Region.json` 中 `InWorldOcrText` 使用 ROI `[0,660,400,60]`（屏幕底部左侧）匹配 "UID:" / "UID：" / "(?i)UID"。
   UID 文字在**加载界面**和**签到弹窗**中就已出现，并非主世界独有特征。
   - t=36s 加载画面底部就显示了 "UID: 1439188325"
   - t=62s 签到弹窗底部仍显示 "UID; 1439188325"

2. **`EnterGame` 在 `OpenGame.next` 首位抢先匹配（OPENGAME-01·直接根因之二）**
   `OpenGame.json` 中 `OpenGame.next` 原顺序为 `["EnterGame", "[JumpBack]ClickContinue", "[JumpBack]CheckIn", ...]`。
   MaaFW 按 `next` 顺序穷举，首个命中即返回。当签到弹窗出现时：
   - `EnterGame` = `And(InWorld, __NotLoading)` 被先评估
   - `InWorld` = `Or(ProtosyncMenuButton, RegionalDevelopmentButton, InWorldOcrText)` —— `InWorldOcrText` 命中 UID → `InWorld` 为 true
   - `__NotLoading` = `Or(WaitLoadingIcon, WaitLoadingText, WaitBlackScreen)` 的 inverse —— 加载已完成，无加载特征 → `__NotLoading` 为 true
   - `EnterGame` 命中 → OpenGame 立即成功返回
   - `[JumpBack]CheckIn`（签到弹窗处理器）排在 `EnterGame` 之后，永远不会被评估

3. **`_IN_WORLD_OCR_KEYWORDS` 含 "寻访" 误匹配（OPENGAME-01·备用判据放大器）**
   `src/core/service/runtime.py` 中 `_IN_WORLD_OCR_KEYWORDS` 含 "寻访"。
   签到弹窗文本 "踞渊北眺**寻访**凭证*5" 命中 "寻访" → `_verify_in_world_by_ocr` 返回 True，
   即使 `EnterGame` 模板未命中，OCR 备用判据仍会误判为"已在大世界"。
   且原逻辑仅需命中 1 个关键词即返回 True，过于宽松。

4. **`_run_task_with_retry` 对正常失败误触发 RecoverGame（RECOVER-01·独立根因）**
   `src/core/service/maa_end/runtime.py` 中 `_run_task_with_retry` 在轻量恢复后仍失败时，
   无条件调用 `self._recover_and_retry(task_name, options)`，该函数执行 `RecoverGame` 任务
   （StopApp → StartApp → OpenGame），强制关闭刚启动的游戏。
   - VisitFriends 因签到弹窗遮挡而 OCR 未命中 → `result is False`（正常失败）
   - _run_task_with_retry 触发 _recover_and_retry → RecoverGame → StopApp 关游戏
   - 这违反 project_memory 约束："run_task 中 succeeded=False 是 MaaFW 穷举 entry.next 后仍未命中的'正常失败'... 不得触发 _recover_and_retry/RecoverGame"

### 为什么 post_delay 单独不够

`EnterGame` 原定义无 `post_delay`，即使加了 `post_delay: 3000`，3s 内签到弹窗不会自动消失。
必须通过 `[JumpBack]CheckIn` 主动点击"领取"按钮关闭弹窗，`EnterGame` 才能在干净的主世界画面上匹配。

## 2. 修改方案

### 修改 1: `OpenGame.json` — 重排 `OpenGame.next` + 添加 `post_delay`

**文件**: `3rd-part/maaend/resource/pipeline/OpenGame.json`

将 `EnterGame` 从 `OpenGame.next` 首位移到末尾，确保所有弹窗/加载处理器先被评估：

```json
"OpenGame": {
    "next": [
        "[JumpBack]ClickContinue",
        "[JumpBack]CheckIn",
        "[JumpBack]CollectRewards",
        "[JumpBack]CheckInConfirmButton",
        "[JumpBack]MonthlyCard",
        "[JumpBack]WaitCloseGameButton",
        "[JumpBack]CloseButton",
        "[JumpBack]ConfirmCharacter",
        "[JumpBack]LoginFailed",
        "[JumpBack]WaitLoadingIcon",
        "[JumpBack]WaitLoadingText",
        "[JumpBack]WaitBlackScreen",
        "EnterGame"
    ]
}
```

为 `EnterGame` 添加 `post_delay: 3000`，让 UI 稳定后再返回成功。

### 修改 2: `Region.json` — 保留 `InWorldOcrText` UID 识别（不改 ROI/expected）

**文件**: `3rd-part/maaend/resource/pipeline/Interface/InScene/Region.json`

**决策**：保留 `InWorldOcrText` 原有的 UID 识别（ROI `[0,660,400,60]`，expected `["UID:","UID：","(?i)UID"]`），仅更新 desc 说明为何保留。

**理由**：
- UID 在加载界面和签到弹窗中确实会出现，但：
  - 加载阶段：`EnterGame = And(InWorld, __NotLoading)` 中 `__NotLoading` 会过滤（`WaitLoadingIcon`/`WaitLoadingText`/`WaitBlackScreen` 命中 → inverse → `__NotLoading` 为 false）
  - 签到弹窗：修改 1 已将 `[JumpBack]CheckIn` 等 JumpBack 处理器排到 `EnterGame` 之前，弹窗会被先点击关闭
- 实测验证：改为菜单文字（"地区建设"/"采购中心" 等 + ROI `[0,0,500,200]`）后 `InWorld` 完全无法命中（模板过时 + OCR 区域不匹配），导致 AndroidOpenGame 必定失败、后续任务全部级联失败
- UID 识别是当前唯一可靠的 OCR 兜底，移除后无替代方案（`ProtosyncMenuButton`/`RegionalDevelopmentButton` 模板已过时）

### 修改 3: `runtime.py` — 移除 "寻访" + 要求多关键词命中

**文件**: `src/core/service/runtime.py`

- 从 `_IN_WORLD_OCR_KEYWORDS` 中移除 "寻访"（签到弹窗文本 "踞渊北眺寻访凭证" 会误匹配）
- 新增 `_IN_WORLD_OCR_MIN_HITS = 2`，要求至少命中 2 个关键词才判定为在大世界
- `_verify_in_world_by_ocr` 改为 `len(matched) >= self._IN_WORLD_OCR_MIN_HITS` 判定

### 修改 4: `maa_end/runtime.py` — 正常失败不再触发 RecoverGame

**文件**: `src/core/service/maa_end/runtime.py`

`_run_task_with_retry` 中 `result is False` 分支（正常失败）：
- 保留轻量 BACK 恢复 + 重试一次
- **移除** `self._recover_and_retry(task_name, options)` 调用
- 轻量恢复后仍失败即返回 False，让上层决定是否继续下一个任务
- `_recover_and_retry`（RecoverGame）只能由用户手动触发，或上层逻辑在显式检测到自动登出弹窗/连接断开时调用

## 3. 影响面

| 组件 | 影响 |
|------|------|
| `OpenGame` pipeline | 所有调用 AndroidOpenGame/PCOpenGame 的路径（GUI 队列、CLI daily、test_runner）均受益于更准确的完成判定 |
| `InWorld` 识别 | 被 14 个 pipeline 文件引用（SceneMenu/SceneMap/SceneWorld/SceneLogin/ProtocolSpace/TrialOfSwordmancy/SeizeDeliveryJobs/DeliveryJobs 等）。收紧 InWorldOcrText 后，所有依赖 InWorld 的场景判定都会更准确，不会在加载/弹窗阶段误判为在大世界 |
| `_verify_in_world_by_ocr` | OCR 备用判据更严格，减少 false positive。在主城菜单完全可见时仍能命中（"地区建设" + "采购中心" 等多个按钮文字），不影响正常场景 |
| `_run_task_with_retry` | 正常失败不再触发 RecoverGame，避免"任务刚启动就被强制关游戏"。连接断开（result is None）仍走 _try_recover_connection 恢复路径，不受影响 |

## 4. 非期待变化

| 风险 | 说明 | 缓解 |
|------|------|------|
| `InWorldOcrText` 改用菜单文字后，野外大世界场景可能无法命中 | 野外大世界主城菜单不可见，"地区建设"等文字不显示。但 `InWorld` 仍可通过 `ProtosyncMenuButton`/`RegionalDevelopmentButton` 模板匹配命中 | 野外场景通常已有其他识别节点（如 `InDijiangWorld`），不依赖 `InWorld` |
| 要求 2 个关键词命中可能导致主城菜单部分遮挡时无法判定 | 如果弹窗只遮挡部分菜单，可能只剩 1 个关键词命中 | `_verify_in_world_by_ocr` 是备用判据，仅在 `EnterGame` 模板匹配失败时使用；正常场景应通过模板匹配或 pipeline 弹窗处理器先清理弹窗 |
| `_run_task_with_retry` 移除 RecoverGame 后，真正的崩溃场景（如自动登出弹窗）不会自动恢复 | project_memory 约束：自动登出弹窗需要 force-stop 重启，且该弹窗会忽略 adb input | 由上层逻辑（如 queue runner 或 GUI）在显式检测到自动登出弹窗时调用 RecoverGame，或由用户手动触发。本次修改不影响 _recover_and_retry 函数本身，仅修改调用边界 |

---

# INVERSE-01：MaaFW 任务级 `inverse: true` 在 And/Or 子识别中不生效 + 第三次队列运行验证

**时间**: 2026-07-22 08:30（补充调查）
**影响**: 修复 OPENGAME-01 后第二次队列运行仍失败——`EnterGame = And(InWorld, __NotLoading)` 中 `__NotLoading`（inverse）在 And 子识别中不生效，导致主世界漏报（And 失败 → EnterGame 不命中 → AndroidOpenGame 超时）
**严重度**: 高（OpenGame 修复无效，仍无法进入主世界）

## 1. 根因分析

### 现象

第二次队列运行（修复 OPENGAME-01 后）MaaFW 日志（`3rd-part/maaend/agent/debug/maafw.log`）：

```
08:11:xx EnterGame recognition FAILED
  - InWorld: TemplateMatch ProtosyncMenuButton score=0.7445/0.8 → SUCCEEDED
  - __NotLoading: Or(WaitLoadingIcon, WaitLoadingText, WaitBlackScreen)
    → all sub-recognition box=null (无加载特征)
    → Or returns box=null
  - And(InWorld, __NotLoading): __NotLoading box=null → And FAILED
```

**关键矛盾**：`__NotLoading` 设为 `inverse: true`，本意是「无加载特征时 __NotLoading 为 true」。但 Or 在所有子识别都未命中时返回 `box=null`，而 And 只看 box 是否非 null——`inverse` 完全被忽略。

### MaaFW inverse 限制（核心发现）

MaaFW Pipeline 中任务级 `inverse: true` 的实际行为：
- **任务作为 next 列表直接项时**：inverse 生效。例如 `WaitLoadingIcon` 若设 `inverse: true`，匹配失败时该任务反而「命中」（box 取整屏）。
- **任务作为 And/Or 的 all_of/any_of 子识别时**：inverse **完全不生效**。And 只检查子识别的 `box` 是否非 null；Or 同理。inverse 标志在 And/Or 上下文中被丢弃。

这导致两种误判：
1. **加载中误报**（第一次队列运行的根因）：`__NotLoading = Or(...)` 的 inverse 不生效 → Or 匹配到 WaitBlackScreen（box 非 null）→ And 通过 → EnterGame 误报成功
2. **主世界漏报**（第二次队列运行的根因）：`__NotLoading = Or(...)` 的 inverse 不生效 → Or 无匹配（box=null）→ And 失败 → EnterGame 漏报

### 根因链

1. **MaaFW 框架限制**：`inverse` 不在 And/Or 子识别中生效（MaaFW 设计缺陷或文档未明示的限制）
2. **EnterGame 错误依赖 `__NotLoading`**：原设计 `And(InWorld, __NotLoading)` 试图用 `__NotLoading` 过滤加载阶段，但因 inverse 限制无法工作
3. **OpenGame.next 重排后 EnterGame 仍无法命中**：即使弹窗处理器在前、EnterGame 在后，EnterGame 自身的 And 条件仍因 `__NotLoading` 失败而无法命中

## 2. 修改方案

### 修改 5：移除 `__NotLoading`，简化 `EnterGame` 为 `And(InWorld)`

**文件**（两份保持同步）：
1. `3rd-part/maaend/resource/pipeline/OpenGame.json`（运行时副本·MaaFW 实际加载）
2. `assets/pipelines/open_game.json`（git 跟踪·IEA PipelineLoader 源）

修改前：
```json
"EnterGame": {
    "recognition": {"type": "And", "param": {"all_of": ["InWorld", "__NotLoading"]}}
}
```

修改后：
```json
"EnterGame": {
    "desc": "确认已进入大世界。OpenGame.next 已将弹窗处理器放在 EnterGame 之前（CheckIn/CollectRewards/MonthlyCard 等），弹窗会被先处理。post_delay 让 UI 稳定后再返回成功。注意：__NotLoading(inverse) 已移除——MaaFW 的任务级 inverse 在 And/Or 子识别中不生效（And 只看 box 非 null，忽略 inverse），导致加载中误报（Or 匹配到黑屏 box 非 null→And 通过）而主世界漏报（Or 无匹配 box=null→And 失败）",
    "recognition": {"type": "And", "param": {"all_of": ["InWorld"]}},
    "pre_delay": 0,
    "post_delay": 3000
}
```

**理由**：
- `OpenGame.next` 重排后，所有弹窗/加载 JumpBack 处理器在 EnterGame 之前评估
- 当所有 JumpBack 处理器都未命中时，屏幕必然处于「无弹窗、无加载」状态
- 此时 EnterGame 只需检查 InWorld 即可——`__NotLoading` 的过滤职责已由 next 列表顺序承担
- 移除 `__NotLoading` 节点定义本身（不再被任何任务引用）

## 3. 第三次队列运行验证

### 执行环境

- 设备：`127.0.0.1:16416`
- 视频：`cache/recordings/queue_run_20260722_082134.mp4`（5464 帧，364.3s，15fps，ctime=08:21:34）
- 任务队列：QuickDaily（AndroidOpenGame → VisitFriends → DijiangRewards → CreditShoppingN2 → SellProduct → DailyRewards）
- MaaFW 日志：`3rd-part/maaend/agent/debug/maafw.log`

### 任务执行结果

| 任务 | 日志标记 | 耗时 | 视频时间点 | 视频帧 OCR 验证 |
|------|----------|------|-----------|-----------------|
| AndroidOpenGame | ✅ SUCCESS | 73s | 0-73s (08:21:34-08:22:47) | 56s 主世界出现（UID 可见）；70s EnterGame 命中（InWorld 匹配 ProtosyncMenuButton score=0.996）；73s 任务完成 |
| VisitFriends | ❌ FAIL | ~10s | 73-103s | 主世界画面（好友列表未能进入或锚点模板过期） |
| DijiangRewards | ❌ FAIL | ~50s | 103-153s | 送货任务对话框（任务前驱状态未满足） |
| CreditShoppingN2 | ✅ SUCCESS | ~22s | 153-203s | 信用商店页面（"245/300"、"立即刷新"）— 与任务一致 |
| SellProduct | ❌ FAIL | ~22s | 203-225s | 信用商店页面（卡在上一任务页面） |
| DailyRewards | ❌ FAIL | ~48s | 225-273s | 主世界画面（导航超时） |

### AndroidOpenGame 成功验证（关键）

MaaFW 日志时间线（08:22:30-08:22:47）：
```
08:22:30.886  WaitLoadingIcon SUCCEEDED (score 0.998243, box [663,297,275,77])
...           (12 cycles of WaitLoadingIcon matching, ~0.8s per cycle)
08:22:42.428  NextList.Starting (cycle 13)
08:22:44.734  NextList.Starting (cycle 14)
08:22:44.850  EnterGame Recognition.Starting
08:22:44.861  EnterGame Recognition.SUCCEEDED
              - algorithm: And
              - box: [1203,10,55,55] (InWorld matched, likely RegionalDevelopmentButton)
08:22:44.862  EnterGame Action.Starting (DoNothing)
08:22:44.862  EnterGame Action.Succeeded
08:22:47.864  EnterGame PipelineNode.Succeeded (post_delay:3000ms 完成)
```

**结论**：AndroidOpenGame SUCCESS 标记**名副其实**——
- EnterGame 在 08:22:44.861 通过 InWorld 匹配（And 单条件，无 __NotLoading 干扰）
- post_delay:3000ms 等待 UI 稳定后于 08:22:47.864 完成
- 视频帧 OCR 在 56s（08:22:30）已显示主世界 UID，确认主世界在 EnterGame 命中时已可见
- VisitFriends 任务于 08:22:48 启动，08:22:51 好友列表打开（`__ScenePrivateWorldEnterMenuFriendsList SUCCEEDED`）

### 次要发现：WaitLoadingIcon 过度匹配

**现象**：08:22:30-08:22:42（12 个 pipeline cycle，约 12s）期间，WaitLoadingIcon 持续以 score 0.998243 匹配 box [663,297,275,77]。但视频帧显示主世界在 56s（08:22:30）已出现。

**分析**：
- WaitLoadingIcon 的 ROI `[638,272,325,127]` 位于屏幕中央，模板 `OpenGame/LoadingIcon.png`
- 视频在 50-55s 显示「送货任务」对话框（送货任务残留弹窗），对话框中央可能有加载图标或类似元素
- 56s 后主世界出现，但 WaitLoadingIcon 仍持续匹配 12s——可能是 MaaFW screencap 与 scrcpy 视频流存在时间偏差，或模板在主世界某些 UI 元素上误匹配
- 此问题未导致任务失败（最终 EnterGame 命中），但增加了 ~12s 的额外等待

**状态**：已记录，不在本次修复范围。建议后续：检查 LoadingIcon.png 模板是否需要更新，或为 WaitLoadingIcon 添加 `threshold` 提高匹配阈值。

### 任务失败原因（非 OpenGame 修复范围）

- **VisitFriends FAIL**：好友列表锚点模板 `__ScenePrivateMenuFriendsEnterMenuFriendsAnchor` 过期（与 2026-07-13 报告 TMPL-01 一致）
- **DijiangRewards FAIL**：前置任务未完成（送货任务对话框遮挡）
- **SellProduct FAIL**：卡在 CreditShopping 页面（前驱 CreditShoppingN2 完成但页面未正确退出）
- **DailyRewards FAIL**：导航节点 `__ScenePrivateMenuListEnterMenuProtocolPass` 超时（与 2026-07-13 报告 NAV-01 一致）

## 4. 影响面（INVERSE-01）

| 组件 | 影响 |
|------|------|
| `EnterGame` 识别 | 移除 `__NotLoading` 后，EnterGame 不再依赖 inverse 机制。在 OpenGame.next 重排保障下，仅靠 InWorld 即可正确判定 |
| `__NotLoading` 节点 | 已删除定义（无其他任务引用） |
| MaaFW inverse 限制 | 已记录在 EnterGame.desc 中，防止后续维护者重新引入 `__NotLoading` 或类似 inverse 依赖 |

## 4. 非期待变化（INVERSE-01）

| 风险 | 说明 | 缓解 |
|------|------|------|
| 无 `__NotLoading` 过滤后，加载阶段若 InWorld 误命中会导致 OpenGame 过早成功 | InWorld 的 `InWorldOcrText`（UID 识别）在加载界面也会命中 | `OpenGame.next` 重排后，WaitLoadingIcon/WaitLoadingText/WaitBlackScreen 等 JumpBack 处理器在 EnterGame 之前评估，加载阶段会被这些处理器优先匹配，EnterGame 不会被评估 |
| WaitLoadingIcon 在主世界某些 UI 上误匹配 | 已观察到 ~12s 的过度匹配（不影响任务结果但增加耗时） | 后续可更新 LoadingIcon.png 模板或提高 threshold |
| 视频时间与 MaaFW 日志时间存在 ~10-15s 偏差 | scrcpy 视频流与 MaaFW screencap 是独立路径，可能存在延迟差异 | 视频验证以 MaaFW 日志的 Recognition 事件为准，视频帧仅作辅助确认 |
