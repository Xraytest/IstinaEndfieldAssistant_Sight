# VF-01: VisitFriendsEnterShipSuccess ClickKey Y 键无效导致任务超时

## 时间
2026-07-14 16:35 ~ 16:48

## 现象
DailyFull 队列执行 VisitFriends 任务时，240s 超时失败。maafw.log 显示 pipeline 卡在 `VisitFriendsEnterShipConfirm → VisitFriendsEnterShipSuccess → VisitFriendsEnterMenuTerminalSuccess` 循环中：
1. `VisitFriendsEnterShipSuccess` OCR 成功识别"打开访客终端"文字（score=0.9998）
2. 执行 `ClickKey` key=89（Y键）试图打开访客终端菜单
3. `VisitFriendsEnterMenuTerminalSuccess` OCR 期望识别"访客终端"文字，但实际识别到"离开"（score=0.9899）
4. 回退到 `VisitFriendsEnterShipConfirm`（JumpBack），形成死循环

## 1. 根因分析

### 直接原因
`VisitFriendsEnterShipSuccess` 节点使用 `ClickKey` action 按下 Android keycode 89（KEYCODE_Y），但 Y 键在游戏中不会打开访客终端菜单。按键后游戏画面未变化，仍显示好友船界面（"离开"按钮可见），导致后续 `VisitFriendsEnterMenuTerminalSuccess` OCR 识别失败。

### 根本原因
Pipeline 设计者可能假设 Y 键是打开访客终端的快捷键，但：
- 游戏 UI 更新后 Y 键可能不再绑定到此功能
- 或者 Y 键从未是正确的快捷键，应直接点击"打开访客终端"按钮

### 代码位置
- 文件：`3rd-part/maaend/resource/pipeline/VisitFriends/Exectue.json`
- 节点：`VisitFriendsEnterShipSuccess`（第44-85行）
- 原始配置：`"action": "ClickKey", "key": 89`

### 调用链
```
VisitFriendsEnterShipConfirm (Click confirm button)
  → [JumpBack]SceneWaitLoadingExit (wait for loading)
  → VisitFriendsEnterShipSuccess (OCR "打开访客终端" → ClickKey Y ← 问题在此)
  → VisitFriendsEnterMenuTerminalSuccess (OCR "访客终端" → 失败)
  → 回退到 VisitFriendsEnterShipConfirm (JumpBack 循环)
```

## 2. 修改方案

将 `VisitFriendsEnterShipSuccess` 的 action 从 `ClickKey` 改为 `Click`：
- `Click` action 会点击 OCR 识别到的"打开访客终端"文字所在位置（box中心）
- 移除 `"key": 89` 配置
- 添加 `pre_delay: 500`（等待画面稳定）和 `post_delay: 500`（等待终端菜单加载）

### 修改内容
```json
// 修改前
"action": "ClickKey",
"key": 89,
"post_delay": 0,

// 修改后
"pre_delay": 500,
"action": "Click",
"post_delay": 500,
```

## 3. 影响面

### 受影响节点
- `VisitFriendsEnterShipSuccess` — action 从 ClickKey 改为 Click
- `VisitFriendsEnterMenuTerminalSuccess` — 间接受益（前置节点正确打开终端后，此节点才能识别"访客终端"文字）

### 不受影响
- `VisitFriendsEnterShipConfirm` — 不变
- `VisitFriendsEnterShip` — 不变
- 其他 VisitFriends 子节点 — 不变

### 回退策略
如修改后仍无法打开终端菜单，备选方案：
1. 检查"打开访客终端"按钮是否可点击（可能需要点击特定位置而非文字中心）
2. 尝试其他按键（如 ESC key=27）
3. 使用固定坐标点击

## 4. 非期待变化

- **Or 识别的 TemplateMatch 分支**：`ShipEscButton.png` 的 TemplateMatch 从未匹配成功（score < 0.4），改为 Click 后如果 TemplateMatch 匹配，会点击 ESC 按钮位置。但实际运行中此分支不会匹配，不影响行为。
- **pre_delay 500ms**：增加 500ms 等待，确保画面加载完成后再点击。可能略微增加总执行时间，但提高了识别可靠性。
- **post_delay 500ms**：给终端菜单加载时间，避免 `VisitFriendsEnterMenuTerminalSuccess` 在菜单未完全加载时进行 OCR 识别。
