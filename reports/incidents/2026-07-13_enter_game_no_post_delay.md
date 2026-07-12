# EnterGame 缺少 post_delay 导致后续任务失败（POSTDELAY-01）

**时间**: 2026-07-13 05:56
**影响**: AndroidOpenGame 成功后立即执行 VisitFriends，游戏 UI 仍在过渡，触发 `__ScenePrivateAnyExit` 连续 ESC，游戏被退出到登录页，VisitFriends 失败
**严重度**: 高（直接导致队列第二个任务必失败，与用户反馈"在完成应用启动并进入主世界后直接尝试退出到登入页并提交第二个任务错误"一致）

## 1. 根因分析

### 现象
日志 `logs/main.log` L13882-13906 记录的执行轨迹：
```
22:21:38  开始执行任务 task=AndroidOpenGame
22:23:06  任务节点轨迹 nodes=['AndroidOpenGame', 'AndroidOpenGame_CN', 'OpenGame',
          'WaitBlackScreen'×29, 'WaitCloseGameButton'×29, 'ClickContinue'×2,
          'WaitBlackScreen'×14, 'WaitLoadingIcon'×23, 'EnterGame']
22:23:06  任务执行成功 task=AndroidOpenGame
22:23:06  开始执行任务 task=VisitFriends
22:23:17  任务执行失败 task=VisitFriends   ← 仅 11 秒后失败
```

AndroidOpenGame 总耗时 ~88s（22:21:38 → 22:23:06），其中 `EnterGame` 作为终止节点匹配 `InWorld` 后任务立即成功。VisitFriends 在 22:23:06 立即启动，11s 后失败。这 11s 内游戏被退出到登录页。

### 根因链

1. **`EnterGame` 无 `post_delay`（直接根因）**
   `OpenGame.json` 中 `EnterGame` 定义：
   ```json
   "EnterGame": {
       "recognition": {"type": "And", "param": {"all_of": ["InWorld"]}}
   }
   ```
   `InWorld` 识别通过（`ProtosyncMenuButton` 或 `RegionalDevelopmentButton` 模板命中）后，任务**立即成功返回**，没有任何延迟。但此时游戏 UI 仍处于过渡状态：登录后的初始动画、菜单加载、资源异步加载等尚未完成，`InWorld` 的两个模板虽然先一步命中，但 UI 整体尚未稳定。

2. **VisitFriends 立即启动并要求"进入大世界"**
   `VisitFriendsMain` 的 `action` 是 `VisitFriendsMainAction`（占位实例），其 `custom_action` 为 `SubTask`，`sub: ["SceneAnyEnterWorld"]`。即 VisitFriends 的**动作**（不仅是 next）会先执行 `SceneAnyEnterWorld`。

3. **`SceneAnyEnterWorld` 检查 `__ScenePrivateAnyEnterWorldSuccess`**
   该节点用 `InWorld` 识别 + `pre_wait_freezes`（target=[70,80,70,60], time=800, timeout=2000）。但此时游戏 UI 仍在过渡，`InWorld` 模板在 `pre_wait_freezes` 的 2000ms 超时内不匹配（过渡期 UI 抖动）。

4. **fallback 到 `[JumpBack]__ScenePrivateAnyExit`**
   `SceneAnyEnterWorld.next` 末项为 `[JumpBack]__ScenePrivateAnyExit`，该节点**无 recognition**（DirectMatch，永远匹配），`action: ClickKey key=27`（ESC），`post_delay: 1500`，`max_hit: 100`。

5. **ESC 循环退出游戏**
   每 1500ms 一次 ESC，11s 内约 7 次 ESC，游戏从主世界被退到登录页。用户观察到的"直接尝试退出到登入页"即此行为。`SceneAnyEnterWorld` 最终超时失败 → `SubTask` 失败 → `VisitFriendsMainAction` 失败 → `VisitFriends` 失败。

### 为什么 `pre_wait_freezes` 没救回来
`__ScenePrivateAnyEnterWorldSuccess.pre_wait_freezes` 仅 2000ms 超时，且 target 是局部区域 [70,80,70,60]。AndroidOpenGame 刚结束时 UI 过渡可能持续 3-5s（初始菜单弹入、资源加载），2000ms 内 `InWorld` 无法稳定匹配。

### 关键澄清：`AndroidOpenGame_CN` 空 `{}` 不是根因
之前怀疑 `AndroidOpenGame_CN: {}` 会导致 OpenGame 被跳过。但节点轨迹显示 `OpenGame` 确实执行了（节点列表中含 `OpenGame` 及其全部子节点）。原因：`pipeline_override` 对 `next` 字段是**前置合并**而非替换：
- 原 `AndroidOpenGame.next = ["OpenGame"]`
- override `{"AndroidOpenGame": {"next": ["AndroidOpenGame_CN"]}}`
- 合并后 `AndroidOpenGame.next = ["AndroidOpenGame_CN", "OpenGame"]`

`AndroidOpenGame_CN: {}` 作为空任务（DirectMatch + DoNothing）立即成功，然后正常进入 `OpenGame`。**不应**给 `AndroidOpenGame_CN` 加 `next: ["OpenGame"]`，那会导致 `OpenGame` 执行两次。

## 2. 修改方案

**核心修改**：为 `EnterGame` 添加 `post_delay: 3000`，让 `InWorld` 匹配成功后等待 3 秒再结束 AndroidOpenGame 任务，给游戏 UI 充分的稳定时间，确保下一个任务启动时 `InWorld` 模板能稳定匹配。

**修改文件**（两份保持同步）：
1. `3rd-part/maaend/resource/pipeline/OpenGame.json`（运行时副本）
2. `MaaEnd/assets/resource/pipeline/OpenGame.json`（git 跟踪源文件）

**修改内容**：
```json
"EnterGame": {
    "recognition": {
        "type": "And",
        "param": {
            "all_of": ["InWorld"]
        }
    },
    "post_delay": 3000
}
```

**为何选 3000ms**：
- `__ScenePrivateAnyEnterWorldSuccess.pre_wait_freezes` 超时 2000ms，3s 延迟覆盖该窗口并留余量
- 过渡期典型时长 3-5s，3s 是最小可行值；过短（如 1s）可能不足，过长（如 5s）拖慢队列
- 若实测仍失败，可上调至 5000ms

## 3. 影响面

- **正面影响**：AndroidOpenGame 成功后游戏 UI 稳定，VisitFriends 的 `SceneAnyEnterWorld` 能在 `pre_wait_freezes` 窗口内匹配 `InWorld`，不再触发 `__ScenePrivateAnyExit` 的 ESC 循环，VisitFriends 成功率提升
- **副作用**：AndroidOpenGame 任务总耗时增加 3s（88s → 91s），可接受
- **影响范围**：仅影响 AndroidOpenGame 流程的结束阶段，不影响 PCOpenGame（PC 端无此问题，UI 过渡更快且不通过 MaaFW 调度后续任务）
- **不影响**：scrcpy 预览、设备连接、CLI 通信、其他预设任务

## 4. 非期待变化

- **无**：本次修改仅增加一个 `post_delay` 字段，不修改任何识别/动作/next 逻辑，不会引入新的副作用
- **潜在观察点**：若实测发现 3s 仍不足（VisitFriends 仍失败），应进一步排查 `InWorld` 模板本身是否在过渡期误匹配（即 `InWorld` 先短暂命中又消失），此时需改用 `post_wait_freezes` 而非固定 `post_delay`
