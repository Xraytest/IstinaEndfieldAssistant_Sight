# 云终末地 DailyFull 输入后 OCR 与资源边界修复报告

- 日期：2026-08-06
- 请求：在本地模拟器使用云终末地循环执行每日全套；每次 input 后直接查看 OCR/模板结果，只有确认状态正确才继续。
- 结果：完成 CloudCN 资源、共享 OCR 模型、云标题页输入验证和任务边界保护；单独验证 `AutoStockpile` 时仍在地区建设入口后失败，因此按要求停止，未继续后续 DailyFull。

## 1. 根因分析

### 1.1 CloudCN 资源 profile 未同步

直接任务调用会先 `connect()`，再将 `ClientVersion=CloudCN` 放入任务 options。旧路径只修改 `_client_version`，没有更新资源 profile，导致运行时仍可能加载默认 `resource`。云端 pipeline、模板和横屏坐标因此不能可靠生效。

### 1.2 CloudCN OCR 模型未自动发现

`resource_cloud` 只包含云端 pipeline 和图像资产，没有 `model/ocr/det.onnx`、`rec.onnx`、`keys.txt`。MaaFW 资源 bundle 加载成功并不代表 OCR 引擎已注册，直接 OCR 会出现 `ocrer_ is null`。

### 1.3 云端标题页的输入返回值不代表状态转换

云端空闲恢复后可能直接停在“点击任意位置继续”。该页面此前出现 MaaTouch `post_click` 返回成功但画面不变的情况；若只检查 job 返回值，会把标题页串联为后续任务的起点。

### 1.4 输入观测回调存在可审计性缺口

原观测只依赖 typed `on_controller_action`，不同 MaaFW Python binding 对动作字段的包装可能导致动作被过滤；同时 OCR worker 为 daemon 线程，CLI 任务返回后进程可能在队列排空前退出，造成尾部输入没有 OCR 记录。

### 1.5 AutoStockpile 的实际阻塞点

2026-08-06 22:11:58 任务前 OCR 严格通过：`UID:1439188325`、`探索`，且无阻塞覆盖层。该次连接明确加载：

- `3rd-part/maaend/resource_cloud`
- `3rd-part/maaend/resource_adb`
- 共享 OCR：`3rd-part/maaend/resource/model/ocr`

`AutoStockpile` 两次执行的节点轨迹均为：

```text
nodes=['AutoStockpileMain', 'AutoStockpileEnterRegionalDevelopment']
hit_nodes=['AutoStockpileMain', 'AutoStockpileEnterRegionalDevelopment']
```

没有命中 `AutoStockpileGetUid`，任务最终在 78.5 秒左右失败。任务后实时 OCR 未确认主世界，因此没有执行 `AutoStockStaple` 及之后任务。

## 2. 修改方案

### 2.1 资源与客户端版本

- `MaaEndRuntime` 增加 CloudCN profile：`CloudCN -> resource_cloud`，其他版本使用 `resource`。
- `load_resource()` 按 profile 加载主 bundle，并保留 `resource_adb` 补充资源。
- 加载 bundle 后显式调用 `Resource.post_ocr_model()`，CloudCN 无模型时回退到共享 `resource/model/ocr`，缺少三个必需文件则拒绝连接。
- `run_task()` 统一调用 `set_client_version()`。
- `IstinaRuntime._set_client_version()` 在已连接 runtime 发生版本切换时执行断开、设置版本、重连和重新加载资源；CloudCN 同时强制使用 `com.hypergryph.cloud.endfield`。

### 2.2 云标题页输入验证

- 新增 `_tap_cloud_advance()`，标题页优先使用现有 `AndroidRuntime.tap()`；Android 通道失败时才回退 MaaTouch。
- `_dismiss_cloud_idle_popup()` 的首次 OCR 同时识别“知道了”“自动结束”和“点击任意位置继续/开始游戏”。
- 每次标题页点击后继续 OCR；只有后续严格主世界判定包含 `探索` 与 UID 且没有阻塞关键词时，才允许任务继续。

### 2.3 输入后 OCR 观测

- Controller sink 同时支持 typed callback 和 raw `Controller.Action.*` 通知。
- 动作名统一去除 namespace，按 UUID 去重，成功输入动作才进入异步 OCR 队列。
- worker 每次输入后截图并全屏 OCR，记录 action、param、info、OCR 文本和元素数量。
- `run_task()` 返回前等待输入观测队列排空；队列清理时正确调用 `task_done()`。

### 2.4 回归测试

新增/扩展 `tests/test_istina_runtime.py`，覆盖：

- 已连接 runtime 切换 CloudCN 时的重建顺序。
- CloudCN 共享 OCR 模型回退与模型缺失拒绝。
- typed/raw 输入动作过滤和 UUID 去重。
- 输入观测队列排空。

## 3. 影响面

- `MaaEndRuntime` 的所有 CloudCN 任务都会加载 `resource_cloud`，OCR 模型注册变成连接资源成功的必要条件。
- 已连接 runtime 的 `ClientVersion` 变化会产生一次显式重连，避免旧资源 profile 残留。
- 云端空闲恢复、标题页点击和任务前后主世界 guard 影响 OpenGame、队列任务和所有依赖 `SceneAnyEnterWorld` 的流程。
- Controller 输入观测只增加异步截图/OCR和有限排空等待，不改变 MaaFW pipeline 的触控实现。
- AutoStockpile 的地区建设 pipeline 尚未修复；其失败会阻止本次 DailyFull 继续串联，符合用户要求的停止条件。

## 4. 非期待变化

- 未启动本地渲染版，也未使用 `com.hypergryph.endfield` 执行云任务；CloudCN 使用 `com.hypergryph.cloud.endfield`。
- 未把 MaaFramework 的 `true` 作为任务完成的唯一依据；任务前后仍需 OCR guard。
- 未继续运行 `AutoStockStaple`、`AutoSell`、`EnvironmentMonitoring`、`DailyRewards`、`SeizeDeliveryJobs` 或 `AutoCollect`，因此不能报告 DailyFull 完成。
- 未回滚工作区已有的 preset、SceneWorld、地图审计删除和诊断脚本修改。
- 全量质量检查仍受既有环境问题影响：质量脚本以系统 GBK 读取 ruff 输出导致解码异常，bundled Python 未安装 mypy；未放宽 ruff/mypy 配置。
