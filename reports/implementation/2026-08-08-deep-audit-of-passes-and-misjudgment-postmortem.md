# 通过任务深度核验 + 当初误判原因复盘（2026-08-08）

## 一、完整检查轮 5 个"通过"任务的深度核验（21:22-22:29 轮）

| 任务 | 证据强度 | 证据链 |
|---|---|---|
| AndroidOpenGame | 🟢 强 | 轨迹 AndroidOpenGame→Cloud→OpenGame→EnterGame 全命中 + 后置主世界确认，启动即入游戏 |
| CreditShoppingN2 | 🟢 中强 | 商店页内真实点击（ScanItem/ScanItemAction 输入后 OCR 有点击记录）→ 终态节点 `CreditShippingCanNotToBuy` 命中（扫描后无 ✔可买项，合法完成态） |
| AutoStockpile | 🟡 中 | 真实页面交互（AutoStockpileGotoElasticGoods/AutoStockpileSelectMarket 点击记录）+ Go 决策识别（AutoStockpile.Recognition 真实识别商品）→ Skip→Done（无可囤时合法空态） |
| VisitFriends | 🟡 中 | **无任何进入好友船的拜访动作（25s）**，成功链 = 计数归零判定：实测当前好友列表页 `AssistCountIcon` 0.998 命中(1182,87) + `ClueExchangeCountIcon` 0.998 命中(1112,87)，图标真实存在于页面；样本下"线索交换=0"为真实识别。但 `VisitFriendsAssistFullInit`（DirectHit）会把助力计数判定直接置真，成功链路存在无条件分支 |
| SellProduct | 🔴 弱 | 注册链 `SellProductValleyIVRegisterPriorityItem1-6` 全 DirectHit（无条件）+ `PrepareOperatorCache` DirectHit；本轮售卖点页面（难民营/基建站/重建总部）识别零命中；"成功"仅由无条件注册链构成，**无任何真实售卖/挂售动作验证** |

结论：**5 个"通过"中仅 AndroidOpenGame 为强证据；CreditShoppingN2/AutoStockpile 为真实交互支撑；VisitFriends 为"识别到归零状态的幂等完成"（无动作）；SellProduct 存在结构性空转（无条件注册链）**。

## 二、当初误判"11/13"的根本原因（复盘）

1. **主因：Python 后备处理器的假阳性**——9 个任务挂盲坐标+OCR 启发式的 Python 处理器，返回"本次没抛异常/试过点击"即 True，未验证"动作真实发生且状态变化"。处理器认领了 8 个失败任务并"全部修复"→ 9/13 计入通过，实际为空转假象。
   - 实锤：处理器可实现违背管线识别验证，任务"通过"并不存在任何真实动作证据。
   - 已根治：`ISTINA_PY_FALLBACK` 门控（默认关闭）+ 注册表实例化。

2. **结构空转：DijiangRewards 的 Finish 无动作绑定**——控制中枢识别成功即 Finish"OK"，奖励已收完时零点击空转（20:50:32 实锤 33s 轨迹仅 ControlNexus→Finish）。
   - 已根治：`_COLLECTION_EVIDENCE_TASKS` 证据校验（无 FastCollect 点击→判未完成）。

3. **识别边界误判：主世界 OCR 判定在云画面稀疏时全线误杀调度**——"探索"字未被 OCR 识别 → 任务前确认链预算耗尽 → 任务未开始即判失败（此前多轮"失败"中的相当一部分为调度问题）。
   - 已根治：InWorld 模板回退（ProtosyncMenuButton 0.99）。

4. **统计口径缺陷**：把"管线自报成功"当真实完成统计通过，未区分"识别验证的完成"与"无条件分支的完成"；通过计数混入处理器假阳与管线空转。

5. **vendored 管线尾部节点校准天花板**（未修）：9 个失败任务里 7 个为页内深度链（会客室/仓储/行动手册/物资调度条目/拍照/委托循环），信号验证节点在云端 UI 不匹配 → 设备无法真完成。

## 三、下一步（把证据校验推广到全部"动作型"任务）

- 对 SellProduct/VisitFriends 增加"无动作证据判定"（类似 Dijiang 收集证据）：
  - SellProduct：要求至少一个售卖点页面识别命中（RefugeeCamp 等）或 Go 注册日志；
  - VisitFriends：要求至少一次"进入好友"动作（VisitFriendsMenuScanTargetFriendOpen 点击）或归零态截图留档。
- 全部动作型任务成功后强制"动作计数 ≥1 或 空态终节点说明"，而非仅管线 hit 判定。

## Files Modified

- 新增 `reports/implementation/2026-08-08-deep-audit-of-passes-and-misfjudgment-postmortem.md`（本条）；`docs/TASK_LOG.md` 追加