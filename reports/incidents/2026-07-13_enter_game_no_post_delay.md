# AndroidOpenGame 后 VisitFriends 失败：post_delay + 弹窗处理器缺失（POSTDELAY-01 + POPUP-01）

**时间**: 2026-07-13 05:56（初版） / 2026-07-13 06:30（修订·补充 POPUP-01）
**影响**: AndroidOpenGame 成功后立即执行 VisitFriends，游戏 UI 仍在过渡且弹窗遮挡，触发 `__ScenePrivateAnyExit` 连续 ESC，游戏被退出到登录页，VisitFriends 失败
**严重度**: 高（直接导致队列第二个任务必失败，与用户反馈"在完成应用启动并进入主世界后直接尝试退出到登入页并提交第二个任务错误"一致）

## 1. 根因分析

### 现象
日志 `logs/main.log` 记录的执行轨迹（三次测试）：

| 测试 | 超时 | AndroidOpenGame | VisitFriends | 备注 |
|------|------|-----------------|--------------|------|
| 1 (90s) | 90s | TIMEOUT (91s>90s) | TIMEOUT | post_delay 使总耗时超过 90s |
| 2 (120s) | 120s | TIMEOUT (>120s) | TIMEOUT | 游戏处于错误状态（上次 ESC 循环已退出游戏） |
| 3 (180s) | 180s | **成功** (42s) | **失败** (10s) | post_delay 生效但 ESC 循环仍触发 |

测试 3 的节点轨迹（AndroidOpenGame 成功）：`['AndroidOpenGame', 'AndroidOpenGame_CN', 'OpenGame', 'ClickContinue'×2, 'WaitBlackScreen'×18, 'WaitLoadingIcon'×23, 'EnterGame']`
- 总耗时 42s = 39s 加载 + 3s `post_delay`
- `EnterGame` 确实执行了，`InWorld` 匹配成功
- VisitFriends 在 AndroidOpenGame 成功的同一秒启动，10s 后失败

### 根因链（完整版）

1. **`EnterGame` 无 `post_delay`（POSTDELAY-01·直接根因之一）**
   `OpenGame.json` 中 `EnterGame` 原定义无 `post_delay`，`InWorld` 识别通过后任务立即成功返回。但此时游戏 UI 仍处于过渡状态。

2. **VisitFriends 立即启动并要求"进入大世界"**
   `VisitFriendsMain` 的 `action` 是 `VisitFriendsMainAction`（占位实例），其 `custom_action` 为 `SubTask`，`sub: ["SceneAnyEnterWorld"]`。即 VisitFriends 的**动作**（不仅是 next）会先执行 `SceneAnyEnterWorld`。

3. **`SceneAnyEnterWorld` 缺少弹窗处理器（POPUP-01·直接根因之二）**
   `SceneAnyEnterWorld.next` 原列表在 `__ScenePrivateAnyEnterWorldSuccess` 之后只有登录/退出相关的 JumpBack，缺少对常见弹窗（签到、月卡、奖励领取、点击继续）和加载画面的处理。
   当 `post_delay: 3000` 给了弹窗出现的时间窗口后，弹窗出现遮挡 `InWorld` 模板，`__ScenePrivateAnyEnterWorldSuccess` 的 `InWorld` 识别在 `pre_wait_freezes` 2000ms 超时内不匹配。

4. **fallback 到 `[JumpBack]__ScenePrivateAnyExit`**
   `SceneAnyEnterWorld.next` 末项为 `[JumpBack]__ScenePrivateAnyExit`，该节点**无 recognition**（DirectMatch，永远匹配），`action: ClickKey key=27`（ESC），`post_delay: 1500`，`max_hit: 100`。

5. **ESC 循环退出游戏**
   每 1500ms 一次 ESC，10s 内约 7 次 ESC，游戏从主世界被退到登录页。`SceneAnyEnterWorld` 最终超时失败 → `SubTask` 失败 → `VisitFriendsMainAction` 失败 → `VisitFriends` 失败。

### 为什么 post_delay 单独不够
`post_delay: 3000` 给了游戏 UI 3s 稳定时间，但这 3s 内游戏可能弹出签到/月卡/奖励等弹窗。这些弹窗遮挡了 `InWorld` 的两个模板（`ProtosyncMenuButton`、`RegionalDevelopmentButton`），导致 VisitFriends 启动后 `__ScenePrivateAnyEnterWorldSuccess` 仍无法匹配。`OpenGame` 的 `next` 列表有这些弹窗的 JumpBack 处理器，但 `SceneAnyEnterWorld` 的 `next` 列表没有 — 这是根本差异。

### 关键澄清：`AndroidOpenGame_CN` 空 `{}` 不是根因
之前怀疑 `AndroidOpenGame_CN: {}` 会导致 OpenGame 被跳过。但节点轨迹显示 `OpenGame` 确实执行了。原因：`pipeline_override` 对 `next` 字段是**前置合并**而非替换：
- 原 `AndroidOpenGame.next = ["OpenGame"]`
- override `{"AndroidOpenGame": {"next": ["AndroidOpenGame_CN"]}}`
- 合并后 `AndroidOpenGame.next = ["AndroidOpenGame_CN", "OpenGame"]`

`AndroidOpenGame_CN: {}` 作为空任务（DirectMatch + DoNothing）立即成功，然后正常进入 `OpenGame`。

## 2. 修改方案

### 修改 1：EnterGame 添加 post_delay（POSTDELAY-01·已提交 f56f82e）
为 `EnterGame` 添加 `post_delay: 3000`，让 `InWorld` 匹配成功后等待 3 秒再结束 AndroidOpenGame 任务。

**修改文件**（两份 gitignored 副本保持同步）：
1. `3rd-part/maaend/resource/pipeline/OpenGame.json`（运行时副本）
2. `MaaEnd/assets/resource/pipeline/OpenGame.json`（上游源文件）

```json
"EnterGame": {
    "recognition": {"type": "And", "param": {"all_of": ["InWorld"]}},
    "post_delay": 3000
}
```

### 修改 2：SceneAnyEnterWorld 添加弹窗 JumpBack 处理器（POPUP-01·本次修改）
在 `SceneAnyEnterWorld.next` 的 `[JumpBack]__ScenePrivateAnyExit` 之前添加 6 个弹窗/加载画面 JumpBack 处理器，与 `OpenGame` 的 `next` 列表保持一致。

**修改文件**（三份保持同步）：
1. `3rd-part/maaend/resource/pipeline/Interface/Scene.json`（运行时副本·MaaFW 实际加载）
2. `MaaEnd/assets/resource/pipeline/Interface/Scene.json`（上游源文件）
3. `assets/pipelines/scene_navigation.json`（git 跟踪·IEA PipelineLoader 源）

新增的 JumpBack 处理器（在 `[JumpBack]SceneWaitLoadingExit` 之后、`[JumpBack]__ScenePrivateAnyExit` 之前）：
```json
"[JumpBack]ClickContinue",       // 点击继续文字
"[JumpBack]CheckIn",             // 每日签到弹窗
"[JumpBack]CollectRewards",      // 奖励领取弹窗
"[JumpBack]MonthlyCard",         // 月卡弹窗
"[JumpBack]WaitBlackScreen",     // 黑屏等待
"[JumpBack]WaitLoadingIcon"      // 加载图标等待
```

这些处理器的 recognition/action 定义已存在于 `OpenGame.json` 中，JumpBack 机制会跨 pipeline 文件查找同名节点。

### 修改 3：GUI 每任务超时 90→120s（TIMEOUT-01·本次修改）
`src/gui/pyqt6/pages/maaend_control_page.py` 第 1039 行，将 `_sync_execute` 的 `timeout` 参数从 90 改为 120，容纳 AndroidOpenGame 加载（~88s）+ EnterGame post_delay（3s）+ 余量。

## 3. 影响面

- **正面影响**：
  - AndroidOpenGame 成功后游戏 UI 有 3s 稳定期
  - VisitFriends 启动后若遇弹窗，`SceneAnyEnterWorld` 能通过 JumpBack 处理器自动处理弹窗而非触发 ESC 循环
  - GUI 超时从 90s 提升到 120s，避免 post_delay 导致的误超时
- **副作用**：
  - AndroidOpenGame 任务总耗时增加 3s（88s → 91s），可接受
  - 弹窗 JumpBack 处理器仅在弹窗出现时触发，无弹窗时不影响流程
- **影响范围**：仅影响 AndroidOpenGame → VisitFriends 的交接阶段，不影响其他预设任务
- **不影响**：scrcpy 预览、设备连接、CLI 通信、其他任务

## 4. 非期待变化

- **无**：本次修改仅增加 `post_delay` 字段和 `next` 列表中的 JumpBack 条目，不修改任何识别/动作逻辑
- **潜在观察点**：
  - 若实测仍失败，应检查 `InWorld` 模板本身是否在过渡期误匹配（先短暂命中又消失），此时需改用 `post_wait_freezes` 而非固定 `post_delay`
  - 若弹窗处理器误触发（如 `ClickContinue` 在非弹窗场景误匹配），应检查对应模板的 ROI/阈值
  - 6 个弹窗处理器均为 MaaEnd 上游已有节点，JumpBack 机制跨文件查找，若上游删除这些节点会导致处理失效

---

# LOGOUT-01：OpenGame.next 缺少自动登出 JumpBack 处理器

**时间**: 2026-07-13 16:30
**影响**: 设备处于"长时间未操作自动登出"提示页面时，执行器无法自动处理该弹窗，陷入死循环
**严重度**: 高（执行器完全卡死，需用户手动干预）

## 1. 根因分析

### 现象
用户报告"异常处理模块的触发与执行存在问题，当前设备处于'长时间未操作自动登出'提示页面，执行器直接卡在这里了"。

MaaFW debug log（`3rd-part/maaend/agent/debug/maafw.log`）记录的完整识别序列：

```
08:18:33.677 NextList.Starting list=[
  EnterGame (jump_back=false),
  ClickContinue (jump_back=true),    ← 无 __ScenePrivateLoggedOutConfirm
  CheckIn, CollectRewards, CheckInConfirmButton, MonthlyCard,
  WaitCloseGameButton, CloseButton, ConfirmCharacter, LoginFailed,
  WaitLoadingIcon, WaitLoadingText, WaitBlackScreen
]
08:18:33.688 EnterGame recognition FAILED (InWorld: TemplateMatch score=0.175/0.270 → 不匹配)
08:18:33.747 ClickContinue FAILED (OCR: all=[] 无匹配)
08:18:33.748 CheckIn FAILED, CollectRewards FAILED, CheckInConfirmButton FAILED
08:18:33.752 MonthlyCard FAILED (OCR detected "确认" at [666,496,48,30] score=0.999, 但 expected 列表不含"确认")
08:18:33.801 LoginFailed FAILED (OCR detected "长时间没有操作自动登出" at [507,344,264,26] score=0.999, 但 expected 列表不含此文本)
08:18:33.804 WaitBlackScreen SUCCEEDED (ColorMatch: box=[705,128,65,15] count=626 ← 误匹配小黑块)
→ DoNothing → loop back → 重复上述循环
```

### 根因链

1. **`OpenGame.next` 缺少 `[JumpBack]__ScenePrivateLoggedOutConfirm`（直接根因）**
   `OpenGame.next` 有 12 个 JumpBack 处理器，但不包含 `__ScenePrivateLoggedOutConfirm`。对比 `SceneAnyEnterWorld.next` 已包含此处理器。当设备处于自动登出弹窗页面时，OCR 检测到 "长时间没有操作自动登出" 文本，但无处理器检查 "自动登出" 关键词。

2. **`LoginFailed` OCR 误检但不匹配**
   `LoginFailed` 的 OCR ROI [477,314,329,59] 覆盖了弹窗文本区域，检测到 "长时间没有操作自动登出"（score=0.999），但 `expected` 列表为 `["重新挑战", "登录失败", "检查网络", ...]`，不包含 "自动登出"。识别正确失败，但该文本本应被 `__ScenePrivateLoggedOutConfirm` 捕获。

3. **`WaitBlackScreen` 误匹配导致无限循环**
   `WaitBlackScreen` 使用 `ColorMatch` 检测 ROI [657,30,308,124] 的纯黑区域。弹窗背景的暗色区域 [705,128,65,15]（count=626）满足条件，使 `WaitBlackScreen` 每轮都 SUCCEEDED。由于 `WaitBlackScreen` 的 `action` 为 `DoNothing`（无动作），MaaFW 执行空动作后跳回 `next` 列表头部重新检测，形成死循环。

4. **pipeline 未热重载**
   修复文件在 08:26:14 修改，但 MaaFW 在 08:18:06 已加载 pipeline（`load_resource()` 时一次性加载），运行中的 Resource 不会感知文件变更。用户 08:18:13 执行 `task run AndroidOpenGame` 时加载的是旧 pipeline。

### 关键证据
- MaaFW log `NextList.Starting` 事件的 `list` 数组中不包含 `__ScenePrivateLoggedOutConfirm`
- OCR 检测到 "长时间没有操作自动登出"（score=0.999）证明文本在屏幕上且可识别
- `__ScenePrivateLoggedOutConfirm` 的 OCR ROI [350,250,550,202] 覆盖文本位置 [507,344,264,26]
- `__ScenePrivateLoggedOutConfirm` 的 expected 包含 "自动登出"，是 "长时间没有操作自动登出" 的子串，MaaFW OCR 使用 contains 语义

## 2. 修改方案

### 修改 4：OpenGame.next 添加 `[JumpBack]__ScenePrivateLoggedOutConfirm`（LOGOUT-01·本次修改）

在 `OpenGame.next` 的 `EnterGame` 之后、`[JumpBack]ClickContinue` 之前添加 `[JumpBack]__ScenePrivateLoggedOutConfirm`。

**修改文件**（三份保持同步）：
1. `3rd-part/maaend/resource/pipeline/OpenGame.json`（运行时副本·MaaFW 实际加载）
2. `MaaEnd/assets/resource/pipeline/OpenGame.json`（上游源文件）
3. `assets/pipelines/open_game.json`（git 跟踪·IEA PipelineLoader 源）

```json
"OpenGame": {
    "next": [
        "EnterGame",
        "[JumpBack]__ScenePrivateLoggedOutConfirm",    ← 新增
        "[JumpBack]ClickContinue",
        ...
    ]
}
```

**参考 MaaEnd 做法**：`SceneAnyEnterWorld.next` 已包含 `[JumpBack]__ScenePrivateLoggedOutConfirm`（位于 `[JumpBack]SceneWaitLoadingExit` 之后）。本次修改使 `OpenGame.next` 与 `SceneAnyEnterWorld.next` 在自动登出处理上保持一致。

**`__ScenePrivateLoggedOutConfirm` 定义**（`SceneManager/SceneCommon.json` L17-44，已存在无需修改）：
- recognition: And
  - OCR: roi=[350,250,550,202], expected=["自动登出","自動登出","Logged out","自動的にロ","장시간 활동"]
  - YellowConfirmButtonType1: YellowButtonBackground(ColorMatch) + icon(TemplateMatch)
- box_index: 1（点击 YellowConfirmButtonType1 返回的 box）
- action: Click
- pre_wait_freezes: 100

## 3. 影响面

- **正面影响**：
  - 设备处于自动登出弹窗页面时，`OpenGame` 能自动识别并点击确认按钮
  - 消除 `WaitBlackScreen` 误匹配导致的死循环（弹窗被处理后 `WaitBlackScreen` 不再匹配）
  - 与 `SceneAnyEnterWorld.next` 的异常处理保持一致
- **副作用**：
  - 无：`__ScenePrivateLoggedOutConfirm` 仅在自动登出弹窗出现时触发，无弹窗时 OCR/ColorMatch 不匹配，不影响流程
- **影响范围**：仅影响 `OpenGame` 任务（游戏启动阶段），不影响其他任务
- **不影响**：scrcpy 预览、设备连接、CLI 通信、其他任务

**注意事项**：修改 pipeline JSON 文件后必须重新连接设备（`system connect`）才能加载新 pipeline。MaaFW 的 `Resource.post_bundle()` 在 `load_resource()` 时一次性加载，运行中不会热重载。

## 4. 非期待变化

- **无**：本次修改仅在 `next` 列表中新增一个 JumpBack 条目，`__ScenePrivateLoggedOutConfirm` 处理器定义已存在于 `SceneCommon.json`
- **潜在观察点**：
  - 若 `YellowButtonBackground` 的 ColorMatch 阈值 `count: 3000` 未满足（截图分析发现约 2981 个黄色像素），需降低阈值或调整色域范围
  - 若 `YellowConfirmButtonType1` 模板匹配失败，需检查按钮图标是否与模板 `YellowConfirmButtonType1.png` / `YellowConfirmButtonType1Hover.png` 一致
  - MaaEnd 无全局 JumpBack 机制，每个需要处理自动登出的 task 必须各自在 `next` 中包含 `[JumpBack]__ScenePrivateLoggedOutConfirm`
