# 云端 ClientVersion 静默降级修复报告（AutoCollect 云端链路）

- 日期：2026-08-07
- 请求：持续循环每日全套；修正阻碍运行的问题；可接入 VLM 增强任务成功率。
- 结果：定位并修复"CLI 直跑任务时 CloudCN runtime 被静默降级为 CN 资源"的系统性反模式；AutoCollect 云端链路实测 Route1 安全跳过、Route2 传送链成功进入 VLM 导航（提交 e8cb26c）。

## 1. 根因分析

### 1.1 ClientVersion 缺省默认 "CN" 静默降级云端 runtime（service/runtime.py 各任务入口）

`_auto_collect_run`/`_daily_run` 等入口使用 `options.get("ClientVersion", "CN")` 并把该值注入 `_set_client_version(runtime, {"ClientVersion": client_version})`。CLI `task run AutoCollect --options {"AutoCollectRoutes": [...]}` 不携带 ClientVersion，于是：

1. `maaend()` 依据 `config/client_config.json` 的 `device.package=com.hypergryph.cloud.endfield` 创建 CloudCN runtime（此时**未连接**）；
2. `_set_client_version` 收到显式 "CN"；`MaaEndRuntime.set_client_version` 仅在**已连接**且 profile 变化时抛 RuntimeError，未连接时**静默**把 `_resource_profile` 改为 default；
3. 随后连接加载 CN 资源 → `_vlm_teleport_to_area` 的 `is_cloud=False` → 云端执行 `SceneEnterWorld*/SceneEnterMap*/EnterTeleport` 等 pipeline 节点，模板与云 UI 失配，30-90s 超时后 `post_stop` 把 Tasker 打入 stopping，后续截屏全 None，VLM/OCR 全链路崩溃（实测日志：`VLM 传送点坐标超出范围 x_raw=605 y_raw=770` 即截屏 None 时 VLM 幻觉坐标）。

GUI/预设路径（DailyFull.json 显式 ClientVersion=CloudCN）不受影响，故此前 AutoStockpile 等任务能成功，而 CLI 直跑 AutoCollect 必败——表现为"同一设备诊断脚本成功、CLI 任务失败"。

### 1.2 AutoCollect Step1a 直接节点与无 waypoints 回退在云端不可用

- Step1a 直接执行路线指定的 `SceneEnterWorld*数字后缀` 节点：云端模板失配，每轮白耗 30s+ 并污染 Tasker。
- Route1/3/6 无 waypoints，回退执行 `AutoCollectRouteNStart`（CN `MapNavigateAction`/模板）：云端永不成功，且实测 CN pipeline 在云 UI 上误点进入"武陵工业计划"覆盖层，破坏后续状态。其 path 坐标为 map02_lv002 世界坐标空间（如 [942,1779]），与 VLM waypoints 的总览图像素空间无可用标定，不可转换。

### 1.3 传送失败清理对云端无效

路线级清理用 3×`KEYCODE_BACK`，云端地图视图/标记模式/工业计划等覆盖层不响应 BACK，重试轮从脏状态开始连环失败。

### 1.4 VLM 传送点像素坐标不稳定

提示词要求绝对像素坐标，小型免费 VLM 持续返回 y≈770-788（超出 720 屏高 7-9%），被判越界丢弃。

### 1.5 VLM 导航 UnboundLocalError（navigation/vlm_walk_navigator.py）

`walk_to_collect` 循环内 `dist_to_end` 仅在循环体赋值；首帧截屏失败 `break` 后循环外汇总（`final_distance_to_target`）触发 `cannot access local variable 'dist_to_end'`，异常上抛使整轮导航记为异常而非 partial。

## 2. 修改方案

### 2.1 ClientVersion 继承（service/runtime.py）

全部 8 处任务入口（_daily_run/_material_farm_run/_material_collect_run/_auto_collect_run/readtask 系 4 处）改为：

```python
runtime = self.maaend(serial)
client_version = self._set_client_version(runtime, options)
```

`_set_client_version` 对缺省 ClientVersion 本就继承 `runtime.client_version`（创建时由 config 包名推导），显式传参仍优先生效，GUI/预设行为不变。

### 2.2 AutoCollect 云端门控

- `is_cloud_route` 时跳过 Step1a 直接节点（记日志），直接走 1b `_vlm_teleport_to_area` 云端链路。
- 云端且无 waypoints 的路线记 `status="skipped"`、reason=`cloud_pipeline_fallback_unsupported` 并 `continue`；汇总新增 `skipped_routes`，不计入 failed、不翻转 overall_ok。

### 2.3 `_cloud_cleanup_to_world`（新增）

传送失败后云端清理：OCR 判定 → 标记模式点"取消"（元素中心，`_norm_to_screen`）/ 地图视图·总览点 X (1220,35) / 通用覆盖层 X+BACK；以 `_is_in_big_world` 收尾，最多 3 轮。实测"武陵工业计划"页一轮清理回主世界。

### 2.4 VLM 传送点提示改百分比

提示词请求 0-100 百分比坐标（解析端已有百分比/像素自动识别双分支，docstring 本就声明百分比），降低小模型像素幻觉。

### 2.5 dist_to_end 初始化（vlm_walk_navigator.py）

循环前 `dist_to_end = float("inf")`，截屏失败提前 break 不再抛 UnboundLocalError。

## 3. 影响面

- 所有经 CLI/队列直跑的任务入口恢复 CloudCN 资源；显式 ClientVersion 调用方行为不变。
- AutoCollect 云端：Route1/3/6 记 skipped（每日全套汇总不再因云端不可行路线判整体失败）；Route2/4/5 等带 waypoints 路线走"云端传送链 + VLM 步行导航"。
- `_cloud_cleanup_to_world` 仅用于云端传送失败清理；非云路线保持 3×BACK。
- CN 本地版本路径（Step1a 直接节点、pipeline 回退、BACK 清理）完全保留。

## 4. 非期待变化

- 云端无 waypoints 路线不再尝试采集（映火荞花/荞花等 Route1/3/6 目标在云端暂不可得），以 skipped 明示；若后续标定世界坐标→总览坐标换算可恢复。
- 免费 VLM 端点（open.cherryin.ai qwen3.5-35b-a3b free）当前读超时率高（"read operation timed out"/"Remote end closed connection"），VLM 步行导航成功率受外部 API 稳定性限制；导航已有单步跳过与连续 3 次中止保护，不会无限空转。
- ruff/mypy 维持存量 FAIL（runtime.py 17 项 ruff 均为存量位移，未新增；配置未放宽）；pytest 收集 PASS。
- scripts/ 诊断脚本（diag_cloud_cleanup.py 等）不入版本控制；.tmp/ 产物不入库。
