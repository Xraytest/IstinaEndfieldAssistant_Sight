# DailyFull 队列执行失败分析报告

**日期**: 2026-07-13 23:12 - 23:39
**队列**: DailyFull (13 个任务)
**设备**: 192.168.1.12:16512 (模拟器)
**超时**: 120s (per-task)

## 执行结果摘要

| 任务 | 结果 | 失败原因 | 状态 |
|------|------|----------|------|
| AndroidOpenGame | ✅ 成功 | - | - |
| VisitFriends | ❌ 失败 | 模板匹配超时 | 待修复 |
| DijiangRewards | ✅ 成功 | - | - |
| CreditShoppingN2 | ✅ 成功 | - | - |
| DeliveryJobs | ✅ 成功 | - | - |
| SellProduct | ✅ 成功 | - | - |
| AutoStockpile | ❌ 失败 | 模板匹配分数过低 | 待修复 |
| AutoStockStaple | ✅ 成功 | - | - |
| AutoSell | ❌ 失败 | 模板匹配分数过低 | 待修复 |
| EnvironmentMonitoring | ❌ 失败 | 触摸输入不支持多触点 | **已修复** |
| DailyRewards | ❌ 失败 | 导航超时 | 待修复 |
| SeizeDeliveryJobs | ❌ 失败 | Python 超时 (120s) | 待修复 |
| AutoCollect | ⏭ 未执行 | 队列中断 | - |

**成功率**: 6/12 (50%)

---

## TOUCH-01: EnvironmentMonitoring 触摸输入失败

### 根因分析
`src/core/service/maa_end/runtime.py:289` 中 `input_methods` 仅设置为 `AdbShell` (值=1)。
AdbShellInput 不支持 `touch_down/touch_move/touch_up` 的 `contact` 参数（多触点 ID），
导致虚拟摇杆操作全部失败：

```
AdbShellInput not supports [contact=0] [x=1226] [y=226] [pressure=1]
```

EnvironmentMonitoring 任务依赖虚拟摇杆移动角色到指定位置，触摸输入失败后
`__ScenePrivateMapWulingJingyuValleyEnterWorldWulingJingyuValley2` 节点
在 20s reco_timeout 内无法完成定位，触发 "PipelineTask bad next"。

### 修改方案
将 `input_methods` 从 `AdbShell` 改为 `AdbShell | Maatouch` (值=5)：

```python
# 修改前
input_methods = int(MaaAdbInputMethodEnum.AdbShell if MaaAdbInputMethodEnum else 1)

# 修改后
input_methods = int((MaaAdbInputMethodEnum.AdbShell | MaaAdbInputMethodEnum.Maatouch) if MaaAdbInputMethodEnum else 1)
```

Maatouch 是 MaaFW 内置的原生触摸注入方案，支持多触点和压力感应，
MaaFW 会在初始化时自动检测并优先使用 Maatouch。

### 影响面
- EnvironmentMonitoring：虚拟摇杆操作恢复正常
- 其他使用 touch_down/move/up 的自定义动作（如 BetterSliding）也将受益
- AdbShell 作为降级方案保留，不会影响原有单击/滑动操作

### 非期待变化
- Maatouch 需要推送 agent 二进制到设备 `/data/local/tmp/`，首次连接可能增加 1-2s
- 模拟器环境通常兼容 Maatouch，但极旧版本模拟器可能不支持

**提交**: commit 9b0d558

---

## TMPL-01: VisitFriends 模板匹配失败

### 根因分析
`__ScenePrivateMenuFriendsEnterMenuFriendsAnchor` 节点在 20s reco_timeout 内
未能识别好友列表锚点模板，两次尝试均超时：

```
Task timeout [pretask.name=__ScenePrivateMenuFriendsEnterMenuFriendsAnchor]
[duration_since(start_clock)=20501ms] [pretask.reco_timeout=20000ms]
```

从 on_error 截图 `2026.07.13-23.16.56.159_VisitFriendsNormal.png` 可见，
游戏画面确实停留在好友列表界面（显示 45/100 好友、搜索框、好友条目），
但锚点模板未能匹配。推测游戏 UI 更新导致模板图像过期。

### 修改方案
需捕获当前好友列表界面的新截图，更新 `__ScenePrivateMenuFriendsEnterMenuFriendsAnchor`
使用的模板图像。或改用 OCR 识别"好友列表"文字作为锚点。

### 影响面
仅影响 VisitFriends 任务的初始锚点识别。

### 非期待变化
无

---

## TMPL-02: AutoStockpile 模板匹配分数过低

### 根因分析
`AutoStockpileTask` 的 next 列表 `[AutoStockpileGotoElasticGoods, AutoStockpileCheckInStore]`
均识别失败：

- `AutoStockpileGotoElasticGoods`（ROI [340,55,60,70]，模板 ElasticGoodsButton.png）：分数 0.37
- `AutoStockpileCheckInStore`（ROI [50,55,60,70]，模板 StableGoodsButtonSelected.png）：分数 0.47

阈值均为 0.8，匹配分数远低于阈值。从 on_error 截图
`2026.07.13-23.20.27.75_AutoStockpileTask.png` 可见，画面停留在
"地区建设/四号谷物资调度"界面，但模板未能匹配。

### 修改方案
1. 捕获当前游戏 UI 的弹性物资按钮和稳定物资按钮（选中态）截图
2. 更新 `AutoStockpile/ElasticGoodsButton.png` 和 `AutoStockpile/StableGoodsButtonSelected.png`
3. 或降低 threshold 从 0.8 到 0.5（不推荐，可能误匹配）

### 影响面
仅影响 AutoStockpile 任务的按钮识别。

### 非期待变化
无

---

## TMPL-03: AutoSell 模板匹配未达阈值

### 根因分析
`AutoSellScanValleyIVSwitchTab` 节点（ROI [0,0,650,180]，模板 TabSwitchElasticGoods.png，
threshold=0.9）模板匹配最高分 0.714952，未达 0.9 阈值，20s reco_timeout 后触发
"PipelineTask bad next"。

从 on_error 截图 `2026.07.13-23.26.08.834_AutoSellScanValleyIVMain.png` 可见，
画面与 AutoStockpile 截图一致（地区建设界面），但标签切换按钮模板未能高分配中。

### 修改方案
1. 捕获当前标签切换按钮截图，更新 `AutoSell/TabSwitchElasticGoods.png`
2. 或降低 threshold 从 0.9 到 0.7

### 影响面
仅影响 AutoSell 任务的标签切换。

### 非期待变化
无

---

## NAV-01: DailyRewards 协议通行证导航失败

### 根因分析
`__ScenePrivateMenuListEnterMenuProtocolPass` 节点在 20s reco_timeout 内
未能完成导航到协议通行证菜单，两次尝试均超时：

```
Task timeout [pretask.name=__ScenePrivateMenuListEnterMenuProtocolPass]
[duration_since(start_clock)=20392ms] [pretask.reco_timeout=20000ms]
```

该节点是 DailyProtocolPassRewardSub 子任务的导航步骤。
可能是协议通行证菜单的入口位置或 UI 已更新，导致导航链中某个模板匹配失败。

### 修改方案
需检查 `__ScenePrivateMenuListEnterMenuProtocolPass` 的 next 列表中各节点的
模板匹配情况，定位具体是哪个导航步骤失败。

### 影响面
仅影响 DailyRewards 中的协议通行证奖励领取。其他子任务（邮件、每日任务等）不受影响。

### 非期待变化
无

---

## TIMEOUT-01: SeizeDeliveryJobs Python 超时

### 根因分析
SeizeDeliveryJobs 任务在 MaaFW 端正常运行（日志显示正在导航到
RegionalDevelopmentWulingDepotNode），但 Python 端 120s 超时先触发：

```
[WARNING] [root] [MAIN] 任务执行超时 timeout=120.0
```

`_wait_job` 方法在超时后返回 False，但 MaaFW 任务仍在后台继续运行。
后续的恢复流程（CloseGame → AndroidOpenGame）因 MaaFW 忙碌而全部超时：

```
[WARNING] [root] [MAIN] 任务执行超时 timeout=60
[WARNING] [root] [MAIN] 任务执行失败 task=CloseGame
[WARNING] [root] [MAIN] 恢复任务失败，不递归 task=CloseGame
```

### 修改方案
1. **短期**: 将 SeizeDeliveryJobs 的超时从 120s 提高到 180s
2. **长期**: 在 `_wait_job` 超时后主动取消 MaaFW 任务（如支持），或重连控制器以中止当前任务

### 影响面
- SeizeDeliveryJobs 任务可能正常完成
- 恢复流程不再因 MaaFW 忙碌而卡死

### 非期待变化
- 提高超时后，单个任务失败的总耗时增加（120s → 180s + 恢复时间）

---

## 总结

### 已修复
- **TOUCH-01**: EnvironmentMonitoring 触摸输入（commit 9b0d558，input_methods 启用 Maatouch）

### 待修复
- **TMPL-01**: VisitFriends 锚点模板过期（需更新模板图像）
- **TMPL-02**: AutoStockpile 按钮模板过期（需更新模板图像）
- **TMPL-03**: AutoSell 标签模板过期（需更新模板图像或降低阈值）
- **NAV-01**: DailyRewards 协议通行证导航（需定位失败步骤）
- **TIMEOUT-01**: SeizeDeliveryJobs 超时（需提高超时或实现任务取消）

### 共同根因
3 个任务（VisitFriends、AutoStockpile、AutoSell）的失败根因都是**模板图像过期**——
游戏 UI 更新后，原有模板图像不再匹配当前画面。建议系统性更新所有模板图像。
