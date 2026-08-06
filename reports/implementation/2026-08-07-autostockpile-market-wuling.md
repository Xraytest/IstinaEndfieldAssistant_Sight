# AutoStockpile 物资调度市场关闭与武陵导航修复报告

- 日期：2026-08-07
- 请求：在本地模拟器使用云终末地循环执行每日全套；每次 input 后直接阅读 OCR/模板结果验证；持续修正阻碍运行的问题。
- 结果：定位并修复 AutoStockpile 遗留物资调度市场页导致任务间无法回到主世界的问题（恢复坐标已提交）；新增 pipeline 市场关闭节点（本地资源，实测可关闭市场）；**修复换区选择节点 ROI 重叠后武陵导航打通（子任务 29s 成功），AutoStockpile 首次端到端完成（含武陵腿，命中 AutoStockpileDone，587.8s，首次尝试失败经恢复重试成功）**。今日两区均买空（ValleyIV 0/960、武陵 skip），故决策走 Skip 属正常。EnvironmentMonitoring 另有独立阻塞（VLM 导航 300s 卡死 watchdog），不随 ROI 修复解决，记为已知阻塞。

## 1. 根因分析

### 1.1 物资调度市场页为不可 ESC 模态

AutoStockpile 在四号谷地购买后停留在"物资调度市场"页。该模态页 `__ScenePrivateAnyExit`（ESC，key 27）无法关闭，导致后续武陵导航回退到 `SceneAnyEnterWorld` 后陷入 ESC 空转（save_draw 标注帧证实画面始终停留在市场页，场景检测在市场页上误匹配 InWorld/InMenuList）。

实测（diag_wuling_nav.py，逐 tap 后全屏 OCR）：

- 市场页右上 X `(1187,36)` 点击后回到地区建设菜单（OCR 命中 事务总览/据点管理/物资调度/仓储节点）。
- 更换地区按钮 `(68,240)` 可打开换区对话框，且对话框提供"武陵"选项 → 武陵地区已解锁。

### 1.2 任务间恢复缺少市场页关闭坐标

`_recover_to_world` 的 close_candidates 原有 `(1200,30)/(1135,94)/(1192,94)/(1221,36)`，不含市场页 X `(1187,36)`，遗留市场页时恢复只能落到 force-stop 兜底。

### 1.3 换区选择节点 ROI 重叠（武陵腿受阻，已修复）

`__ScenePrivateMenuRegionalDevelopmentSelectRegionValleyIV` 与 `...SelectRegionWuling` 共用 ROI `[429,145,431,165]`。云端换区对话框为横排，四号谷地 `(517,273)` 与武陵 `(733,275)` 同时落在该 ROI 内，选择易错配；观测批次中换区流程点击了四号谷地并确认，未能进入武陵。

修复：将 `SelectRegionWuling` 的 ROI 收窄到右半 `[690,240,180,80]`（仅覆盖武陵选项），与四号谷地解耦。修复后 `SceneEnterMenuRegionalDevelopmentWulingStockRedistribution` 子任务 29s 成功，完整命中 换区→武陵地区建设→物资调度（ElasticGoodsButton `[448,96,30,32]`）。该修复同时惠及 EnvironmentMonitoring/DeliveryJobs 等武陵腿的导航入口（但 EnvironmentMonitoring 仍有其独立的 VLM 导航阻塞）。

## 2. 修改方案

### 2.1 任务间恢复（已提交，src/）

`runtime.py::_recover_to_world` 的 close_candidates 增加 `(1187,36)`（市场页 X）。实测从市场/购买页混乱状态 `_recover_to_world()` 返回 True 且主世界 OCR 确认。

### 2.2 pipeline 市场关闭节点（本地资源，3rd-part 不入版本控制）

`resource_cloud/pipeline/Interface/SceneMenu.json`：

- `SceneEnterMenuRegionalDevelopment.next` 在回退到 `SceneAnyEnterWorld` 前插入 `__ScenePrivateStockRedistributionMarketDetect`。
- `__ScenePrivateStockRedistributionMarketDetect`：OCR `剩余可购买数量`（roi `[90,165,220,40]`，max_hit 3）→ `__ScenePrivateStockRedistributionMarketClose`。
- `__ScenePrivateStockRedistributionMarketClose`：`DirectHit` roi `[1160,12,55,48]` + `Click`（固定点 X），关闭后回到 `SceneEnterMenuRegionalDevelopment` 复核。

实测该节点触发后点击 X，OCR 确认回到地区建设菜单，证明 `DirectHit+roi+Click` 在 MaaFW 下可作固定点点击。

### 2.3 换区选择 ROI 解耦（本地资源）

`resource_cloud/pipeline/SceneManager/SceneRegionalDevelopment.json`：`__ScenePrivateMenuRegionalDevelopmentSelectRegionWuling` 的 ROI 由 `[429,145,431,165]` 改为 `[690,240,180,80]`，仅覆盖横排对话框右侧的武陵选项，避免与四号谷地重叠错选。实测武陵导航 29s 成功，AutoStockpile 端到端完成。

## 3. 影响面

- 恢复坐标仅新增候选，逐次 OCR 验证、到主世界即停，保持幂等，不影响已可恢复的页面。
- 市场关闭节点仅在检测到市场页时触发（max_hit 3 防死循环），不改变 ValleyIV 正常购买链。
- 武陵腿未修复，AutoStockpile 在武陵仍可能失败；其失败经恢复后不串联后续任务。

## 4. 非期待变化

- 未把 MaaFramework 返回 true 作为完成依据；市场关闭与恢复均以实时 OCR 判定。
- 未启用本地渲染版；CloudCN 仍用 `com.hypergryph.cloud.endfield`。
- 未放宽 ruff/mypy 配置；runtime.py 单文件 ruff 通过。
- 3rd-part 资源改动仅本地生效，不入版本控制；仅 src/ 恢复坐标提交推送。
