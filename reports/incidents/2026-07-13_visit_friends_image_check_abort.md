# VisitFriends 打开 dashboard 后即退出并失败：SceneImageCheck 误中止任务（IMGCHK-01）

**时间**: 2026-07-13 17:30
**影响**: VisitFriends 任务启动后仅打开菜单列表（dashboard），随即点击左下角退出按钮触发"是否退出至登录界面？"对话框，因 `CancelButton`（X 关闭按钮模板）不匹配文本按钮，触发 `__SceneCheckAbortPipeline`（PostStop）中止整个 VisitFriendsMain 任务，反馈失败
**严重度**: 高（直接导致 VisitFriends 任务必失败，且因 PostStop 终止整个 Tasker，后续恢复任务也立即失败）
**相关历史**: 本文与 POSTDELAY-01 / POPUP-01 / LOGOUT-01 同属 AndroidOpenGame 后续任务启动系列问题，但根因独立

## 1. 根因分析

### 现象
用户反馈："访问好友任务在开始后仅打开 dashboard 然后就尝试退出并反馈失败"。
`logs/main.log` 记录 VisitFriends 在 AndroidOpenGame 成功后启动，约 10s 后失败。
`3rd-part/maaend/config/debug/maafw.log` 第 37429-37772 行完整记录了失败链路。

### 执行轨迹（maafw.log task_id=200000002）

| 时间 | 节点 | 事件 |
|------|------|------|
| 11:05:38.477 | SceneAnyEnterWorld | InWorld 命中，进入大世界成功 |
| 11:05:43 | __ScenePrivateWorldEnterMenuFriendsList | InWorld 命中 |
| 11:05:43 | __ScenePrivateMenuListEnterMenuFriends | OCR "好友" 未命中（菜单未稳定） |
| 11:05:43 | [JumpBack]__ScenePrivateWorldEnterMenuList | 打开菜单列表（dashboard） |
| 11:05:49 | __SceneImageCheck | InMenuList + ImageCheckNotPassedRecognition 命中，点击 [32, 661]（左下角退出按钮） |
| 11:05:49 | __SceneImageCheckDialogIn | OCR "登录界面" 匹配 "是否退出至登录界面？"，score=0.974983 |
| 11:05:50 | [JumpBack]__SceneCheckOSD | max_hit=1 已达上限，跳过 |
| 11:05:50 | [JumpBack]__SceneImageCheckAICPlanColor | DirectHit，总是匹配 |
| 11:05:50 | __SceneImageCheckAICPlanColorSuccess | FAILED：CancelButton 模板分数 0.303~0.455，远低于阈值 |
| 11:05:50 | __SceneImageCheckAICPlanColorFailedFinish | 命中（DirectHit）→ Screencap |
| 11:05:50.034 | __SceneCheckAbortPipeline | 执行 PostStop → Tasker.post_stop() |
| 11:05:50.034 | need_to_stop | node.name=VisitFriendsMain，任务被终止 |
| 11:05:50 | task end | ret=true（MaaFW 报告成功，但实际是中止） |

### 根因链

1. **`__SceneImageCheck` 特性设计**
   `SceneImageCheck.json` 定义了一个"场景图像检查"特性：当进入菜单列表时，`__SceneImageCheck` 通过 `ImageCheckNotPassedRecognition`（自定义识别）判断是否需要图像检查；若"未通过"，则点击屏幕左下角退出按钮（target `[30, -60, 10, 10]`）触发登出对话框，然后通过 `__SceneImageCheckAICPlanColorSuccess` 验证对话框是否包含 `CancelButton`（X 关闭按钮）+ `YellowConfirmButtonType1`（黄色确认按钮）。

2. **`__SceneImageCheck` 在菜单列表入口被无条件引用**
   `SceneMenu.json` 第 117 行：`__ScenePrivateWorldEnterMenuList.next = ["__SceneImageCheck", "__ScenePrivateAnyEnterMenuListSuccess"]`。即每次从大世界进入菜单列表时，都会先尝试 `__SceneImageCheck`。

3. **`ImageCheckNotPassedRecognition` 默认返回"未通过"**
   该自定义识别在未配置图像检查基线时返回"未通过"，触发 `__SceneImageCheck` 点击退出按钮。

4. **登出对话框使用文本按钮，不是 X 关闭按钮**
   游戏内"是否退出至登录界面？"对话框只有"取消"/"确定"两个文本按钮，没有 X 关闭按钮图标。但 `__SceneImageCheckAICPlanColorSuccess` 要求同时匹配 `CancelButton`（= `And(WhiteButtonBackground, __CancelButtonIcon)`，其中 `__CancelButtonIcon` = `Or(CancelButtonType1Icon, HoverIcon, LineIcon, LineHoverIcon)`——全部是 X 关闭按钮模板）。

5. **模板分数远低于阈值**
   maafw.log 第 37601-37607 行：四个 X 关闭按钮模板分数分别为 0.327 / 0.344 / 0.303 / 0.455，远低于默认阈值 0.7，`CancelButton` 不匹配 → `__SceneImageCheckAICPlanColorSuccess` FAILED。

6. **`__SceneImageCheckAICPlanColorFailedFinish` 触发 PostStop 中止整个任务**
   `__SceneImageCheckAICPlanColorFailedFinish.next = ["__SceneCheckAbortPipeline"]`，后者执行 `PostStop` 自定义动作，调用 `Tasker.post_stop()` 终止整个 VisitFriendsMain 任务。MaaFW 报告 `task end: [ret=true]`（Tasker.Task.Succeeded），但实际是中止——这是 MaaFW 的语义缺陷，无法区分真实成功与 PostStop 中止。

### 为什么 VisitFriends 受影响而其他任务可能不受影响
- VisitFriends 的入口 `VisitFriendsMain` 通过 `SubTask: ["SceneAnyEnterWorld", "SceneEnterMenuFriendsList"]` 进入好友列表
- `SceneEnterMenuFriendsList` → `__ScenePrivateWorldEnterMenuFriendsList`（InWorld）→ `__ScenePrivateMenuListEnterMenuFriends`（OCR "好友"）失败 → fallback 到 `[JumpBack]__ScenePrivateWorldEnterMenuList`（打开菜单列表）
- 进入菜单列表即触发 `__SceneImageCheck` → 整个失败链
- 任何需要进入菜单列表的任务（如 SceneEnterMenuOperator / SceneEnterMenuRegionalDevelopment 等）都可能受此影响，但 VisitFriends 是队列中第一个经过此路径的任务

## 2. 修改方案

### 修改：禁用 `__SceneImageCheck` 节点（IMGCHK-01）

为 `__SceneImageCheck` 节点添加 `"enabled": false`，禁用整个图像检查特性。MaaFW 遇到 `enabled: false` 的节点会跳过，直接尝试 `next` 列表中的下一个节点（`__ScenePrivateAnyEnterMenuListSuccess`，recognition: `And(AllOf: ["InMenuList"])`）。这样菜单列表打开后直接确认成功，不再点击退出按钮、不触发登出对话框、不中止任务。

### 为什么选择禁用而非修复 CancelButton 模板
1. **`__SceneImageCheck` 特性的本质是"通过登出对话框验证场景"**——这是一个反直觉的设计（通过退出再取消来检查画面），且依赖 `ImageCheckNotPassedRecognition` 自定义识别的基线配置。本项目未配置该基线，特性默认"未通过"，每次进菜单都会触发退出对话框。
2. **修复 CancelButton 模板**只能解决"模板不匹配"这一层，但特性本身仍会每次点击退出按钮、弹出登出对话框再取消，引入不必要的 UI 抖动和失败风险（如网络延迟导致取消按钮未及时出现）。
3. **禁用是更彻底的修复**——直接跳过整个图像检查流程，菜单列表入口回归"打开即成功"的简洁语义。

### 修改文件（两份保持同步）
1. `3rd-part/maaend/resource/pipeline/SceneManager/SceneImageCheck.json`（运行时副本）
2. `MaaEnd/assets/resource/pipeline/SceneManager/SceneImageCheck.json`（上游源文件）

### 修改内容
```json
"__SceneImageCheck": {
    "desc": "场景图像检查，检查完毕后回到菜单列表（已禁用：登出对话框无 X 关闭按钮，CancelButton 模板不匹配，导致 __SceneCheckAbortPipeline 中止整个任务，详见 IMGCHK-01）",
    "enabled": false,
    ...
}
```

### 未修改的引用点
`SceneMenu.json` 第 117 行 `__ScenePrivateWorldEnterMenuList.next` 中的 `"__SceneImageCheck"` 引用保留不动。`enabled: false` 使该引用变为 no-op，未来需要恢复时只需删除 `enabled: false` 即可，无需改动 SceneMenu.json。

## 3. 影响面

### 直接影响
- **VisitFriends**：进入菜单列表后不再触发退出对话框，`__ScenePrivateAnyEnterMenuListSuccess`（InMenuList）直接匹配成功，菜单列表入口回归正常。
- **所有经过 `__ScenePrivateWorldEnterMenuList` 的任务**：包括 SceneEnterMenuList / SceneEnterMenuOperator / SceneEnterMenuRegionalDevelopment / SceneEnterMenuFriendsList / SceneEnterMenuFriendsAdd 等，均不再触发图像检查流程。

### 间接影响
- **`ImageCheckNotPassedRecognition` / `ImageCheckSetResultAction` 等自定义组件**：不再被调用，但定义保留（未来恢复时可用）。
- **`__SceneImageCheckDialogIn` / `__SceneImageCheckAICPlanColor*` / `__SceneImageCheckFinishSave` / `__SceneImageCheckFinishExit`** 等子节点：定义保留，但因入口 `__SceneImageCheck` 被禁用，整条链路不再执行。
- **`__SceneCheckAbortPipeline`**：仍可被其他场景引用（如 `SceneLoading.json`），不受影响。
- **RECOVERY-01 恢复模块**：VisitFriends 失败时本会触发 CloseGame → AndroidOpenGame → 重试；修复后 VisitFriends 不再失败，恢复模块不再被错误触发。注意：之前恢复任务立即失败的现象（PostStop 将 Tasker 置于停止状态，后续任务无法启动）也会随之消失。

### 不影响
- 大世界进入、弹窗处理、登录页处理、加载画面处理等其他 SceneManager 功能。
- OpenGame / AndroidOpenGame / CloseGame 等游戏启动关闭流程。
- JumpBack 机制、SubTask 机制、Anchor 机制等 MaaFW 核心特性。

## 4. 非期待变化

### 已知的非期待变化
1. **图像检查功能完全失效**：`__SceneImageCheck` 特性的设计意图是"在进入菜单列表时通过登出对话框验证场景状态"，禁用后该验证不再执行。但本项目从未配置 `ImageCheckNotPassedRecognition` 的基线，特性从未真正生效，禁用不会引入新风险。

2. **`__SceneImageCheckDialogIn` 等子节点成为死代码**：这些节点定义保留但不再被执行。未来若需恢复图像检查功能，需同时：
   - 删除 `__SceneImageCheck` 的 `"enabled": false`
   - 配置 `ImageCheckNotPassedRecognition` 的基线
   - 修复 `CancelButton` 模板以匹配登出对话框的文本按钮（或改为识别文本按钮）

3. **MaaFW `ret=true` 语义混淆依旧**：`__SceneCheckAbortPipeline` 通过 PostStop 中止任务后 MaaFW 仍报告 `Tasker.Task.Succeeded`，这是 MaaFW 的语义缺陷。本次修复避免了进入该路径，但其他场景若触发 PostStop 仍会出现"成功"假象。这是 MaaFW 上游问题，本项目层面无法修复。

### 潜在风险
- **未见明显风险**：禁用一个从未真正生效的特性不会引入新行为。VisitFriends 之前的"成功"路径（`__ScenePrivateAnyEnterMenuListSuccess`）本就是 `next` 列表的第二项，禁用第一项后直接执行第二项，行为可预测。

### 验证点
- 连接设备执行 VisitFriends，应能正常进入菜单列表 → 好友列表，不再出现"是否退出至登录界面？"对话框。
- maafw.log 中不应再出现 `__SceneImageCheck` / `__SceneImageCheckDialogIn` / `__SceneImageCheckAICPlanColor*` / `__SceneCheckAbortPipeline` 的执行记录。
- `need_to_stop [node.name=VisitFriendsMain]` 不应再出现。
- 注意：MaaFW 不热重载 pipeline，修改后需在 GUI 中重新连接设备（`system connect`）使修改生效。
