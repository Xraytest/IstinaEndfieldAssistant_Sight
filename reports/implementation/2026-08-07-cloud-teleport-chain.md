# 云终末地传送链打通报告（空闲弹窗/开图/总览导航/锚点模板/VLM 兜底）

- 日期：2026-08-07
- 请求：持续循环每日全套；修正阻碍运行的问题；可接入 VLM 增强任务成功率。
- 结果：云终末地传送链端到端打通——空闲断连弹窗可正确关闭；小地图实测坐标开图；新增总览确定性导航（跨地区/跨子区域）；新增金色锚点模板匹配（VLM 兜底）；清波寨跨地区传送实测 `ok=true (vlm_visual_teleported)`。

## 1. 根因分析

### 1.1 空闲断连弹窗点击目标错误（maa_end/runtime.py `_dismiss_cloud_idle_popup`）

旧实现取 OCR 首个命中节点作为点击目标，常命中对话框正文（"由于您长时间未操作…"，不可点击），点击无效后被误判为"MaaTouch 被忽略"并触发 force-stop。云会话在服务端持久，本地 force-stop 重启后重连仍是同一弹窗，启动链预算耗尽。实测正文中心 (637,337) 与"知道了"按钮 (638,433) 的差异即根因。

### 1.2 云端 pipeline 场景节点超时污染 Tasker（service/runtime.py `_vlm_teleport_to_area`）

`SceneEnterMap*`/`EnterTeleport`/`SceneEnterWorld*` 模板与云终末地 UI 不匹配，每次 30-90s 超时后 `post_stop` 把 Tasker 打入 stopping 状态，后续 `_screenshot`（MaaEndRuntime 与 daemon scrcpy 两路）全部返回 None，手动开图验证与 VLM 截图随之全部失效（表现为"手动打开地图失败 + VLM found=false + max_steps"）。

### 1.3 手动开图坐标偏移

旧 `map_button_taps` 首项 (141,125) 偏出小地图圆心，云端开图不稳定。实测小地图圆形中心 (110,125) 一次命中。

### 1.4 总览判定与导航缺失

- `_cloud_overview_navigate` 首版用 "O.M.V.帝江号" 作总览特征，但该标签在地图视图同样出现 → 地图视图被误判为总览，跳过进总览步骤，在地图视图上点字典坐标误入标记管理模式。
- 武陵子区域旧坐标（清波寨 (600,400)）与实测 OCR 标签中心 (619,412) 偏移约 20px，点击落空白触发标记创建。
- 标记管理模式在云端不响应 BACK，旧恢复逻辑（keyevent BACK）空转 3 次。

### 1.5 到达验证假阴

`_verify_in_target_area` 要求大世界 OCR 含子区域名关键词，但大世界 HUD 从不显示子区域名（如清波寨），传送实际成功后验证仍 False，流程误入重试/OCR 兜底并破坏状态。探针实测：锚点 (528,343) → 信息面板"传送"按钮 (1136,631) → 点击后立即回主世界，证明传送本身成功。

## 2. 修改方案

### 2.1 空闲弹窗（maa_end/runtime.py）

`_dismiss_cloud_idle_popup` 收集全部 OCR 命中后按优先级选目标："知道了" > "开始游戏" > "点击任意位置继续"；均未命中但弹窗正文存在时用实测固定按钮坐标 (638,433) 兜底。移除点击后 BACK（避免退出云客户端大厅）。

### 2.2 云端跳过 pipeline 节点（service/runtime.py）

`_vlm_teleport_to_area` 内 `is_cloud`（`runtime.client_version == CloudCN`）时跳过 Step1/2/2.5/3 的 pipeline 调用，直接走手动开图 + 总览导航 + 锚点路径，避免 Tasker 污染与 180s+ 空耗。

### 2.3 手动开图

`map_button_taps = [(110,125), (120,140), (141,125)]`（实测圆心优先）。

### 2.4 总览确定性导航 `_cloud_overview_navigate`

进总览（"地区总览"按钮 (1110,645)，特征仅用"地区建设等级"）→ 地区判定（标题 `//武陵`/`//四号谷地` 优先，子区域标签兜底）→ 地区不同或未知时点底部 tab（武陵 (1012,644)/四号谷地 (1182,643)，幂等）→ 子区域选择优先 OCR 标签中心，坐标字典兜底（清波寨更新为 (619,412)）→ 误入标记模式时点"取消"退出并重试一次 → 以地图标题含目标名验证。

### 2.5 锚点模板匹配 `_cloud_find_teleport_anchor`

金色圆形徽记锚点模板（34x35，实测截图裁剪）内嵌 base64（仓库 `*.png` 被 gitignore，本地文件仅缓存），TM_CCOEFF_NORMED ≥ 0.7 命中返回中心；云端传送识别首轮优先模板，其余轮次 VLM 兜底（VLM 提示中锚点颜色描述由"蓝色/青色"修正为"金色/琥珀色"）。

### 2.6 到达判定 `_arrived`

云端链路由总览导航 + 子区域锚点保证区域，到达判定放宽为 `_is_in_big_world`；非云版本保持原关键词验证。OCR 兜底到达分支同样对云端放宽。

### 2.7 标记模式恢复

OCR 兜底标记模式恢复在云端优先点"取消"按钮（元素中心），非云保持 BACK。

## 3. 影响面

- `_dismiss_cloud_idle_popup`：所有任务间空闲弹窗检测路径（`_lightweight_recover_ui`、`_ensure_game_in_world` 等）受益；非弹窗画面行为不变（无命中即返回 False）。
- `_vlm_teleport_to_area`：仅 CloudCN 改变路径顺序；CN 版本逻辑不变。调用方（AutoCollect、VLM 交互传送拦截、EnvironmentMonitoring 导航）无需改动。
- 新增常量/方法均为类内私有，无外部引用。
- 模板 base64 内嵌于 `src/core/service/runtime.py`，随代码提交；`assets/templates/cloud_map_teleport_anchor.png` 仅本地缓存（被 gitignore）。

## 4. 非期待变化

- 云端到达判定放宽后，理论上"传送到错误子区域但到达大世界"不再被拦截；由总览导航+锚点保证区域，风险可控；非云版本不受影响。
- 跳过 pipeline 节点后，若未来云端 UI 与模板重新匹配，CloudCN 也不会使用 pipeline 快捷路径（需手动恢复 is_cloud 分支）。
- 锚点模板依赖当前金色徽记样式；游戏若改图标需重新裁剪模板（VLM 兜底仍可用）。
- ruff/mypy 维持既有 FAIL（17 项 ruff 为存量，均不在本次改动行），未放宽配置；pytest 收集 PASS。
- 3rd-part 资源未改动；scripts/ 诊断脚本不入版本控制。
