# 任务 callback 误报成功分析

## 时间
2026-07-12

## 现象
GUI 队列执行后，除 AndroidOpenGame（启动任务）外，其余任务（SellProduct、AutoStockStaple、AutoCollect 等）实际未执行任何游戏操作，但 callback 反馈 `status=success`，UI 标记为"成功"。

日志证据（logs/main.log L13273-13336，16:02-16:05）：
- SellProduct 16:03:31→16:03:32（1s）标记 success
- AutoStockStaple 16:03:55→16:03:56（1s）标记 success
- AutoCollect 16:05:04→16:05:05（1s）标记 success

对比 15:21 同预设 `preset run --timeout 90`：8 个任务全部超时失败（90s）。

## 根因分析

三层独立问题叠加导致误报：

### 第一层：MaaEnd 的 *Schedule 跳过设计（设计预期）

`SellProduct.json`、`AutoCollect.json`、`AutoStockStaple/Main.json` 的 entry 结构一致：

```
*Schedule (entry)
├── next: [*ScheduleEnabled, *End/Done]
    ├── *ScheduleEnabled (Custom: ScheduleRecognition, attach: 全 false)
    │   └── next: [*Main] → 真正业务
    └── *End/Done (无 recognition, 无 next) → 跳过分支
```

`ScheduleRecognition`（agent/go-service/common/schedule/recognition.go:43-97）读取节点的 `attach` weekday flags，按游戏日（4:00 分界）判断今天是否执行。三个任务的 `attach` 全 false（周一到周日都不启用），所以 `ScheduleRecognition` 永远返回 false，任务永远走 `*End` 跳过分支。

`*End` 节点无 recognition（永远命中）+ 无 next（命中即结束）→ MaaFW status=succeeded。

**attach 全 false 是上游模板默认值**（MaaEnd/assets/resource/pipeline/ 与 3rd-part/maaend/resource/pipeline/ 一致）。根据 sell-product-maintain.md 文档，`SellProductSchedule` 选项通过 `pipeline_override` 写入 `attach` 的星期布尔值——预期由用户在界面中选择执行星期后动态启用。本项目 GUI 未传递 weekday 选项，导致 attach 保持全 false。

### 第二层：MaaFW 缺少 skipped 语义

MaaStatusEnum（maa/define.py:39-44）：invalid=0, pending=1000, running=2000, succeeded=3000, failed=4000。

只有 succeeded/failed 两种终态，没有 skipped。pipeline 走到无 next 节点（如 `*End`）→ status=succeeded。`job.succeeded` 无法区分"真正执行业务"和"走了跳过分支"。

### 第三层：Python 包装层 job.wait() truthy bug + 未利用节点轨迹

`_wait_job`（runtime.py:654-676）原实现：
```python
return job.wait()  # job.wait() 返回 Job 对象自身（truthy），不是 bool
```

MaaFW Python 绑定（maa/job.py:31-41）`Job.wait()` 返回 `self`（支持链式调用），Job 类无 `__bool__`/`__len__`，Python 默认判定为 truthy。所以 `if succeeded:` 永远为 True，即使 status=failed 也误报成功。

此外，`TaskJob` 继承 `JobWithResult`，有 `get()` 方法返回 `TaskDetail`（含 `node_id_list` 节点轨迹），但 Python 端未使用。

### 为什么 15:21 那次能正确报失败

15:21 走 CLI `preset run --timeout 90`，`_wait_job` 进入 timeout 分支：`worker.join(90)` 后 worker 仍 alive → `return False`（硬编码超时）。这个超时兜底绕过了 Job truthy 问题。但"快速跳过"（1s 完成）的任务无法被超时捕获。

### GUI 未传 timeout 加剧问题

`_runtime_queue_runner`（maaend_control_page.py:963）原实现 `params={"options": merged_options}`，未传 timeout。CLI `args.timeout` 为 None → `_run_task` 的 `timeout=None` → `_wait_job` 走 `if timeout is None` 分支 → `return job.wait()`（truthy）。

## 修改方案

### 1. _wait_job 修复 truthy bug（runtime.py:654-681）
`job.wait()` 后用 `job.succeeded` 替代返回值。timeout 分支的 `result["ok"]` 同步改为 `job.succeeded`。

### 2. run_task 新增跳过检测（runtime.py:732-763）
在 `job.succeeded` 为 True 后，调用 `job.get()` 获取 `TaskDetail`，遍历 `task_detail.nodes` 收集节点名。检测逻辑：
- has_skip：节点名以 End/Done/Skip 结尾（如 SellProductScheduleEnd）
- has_biz：节点名包含 Main/Start/Loop（如 SellProductMain）
- has_skip and not has_biz → 判定跳过，返回 False

跳过的任务返回 False，CLI 返回 `{"status": "error"}`，GUI 标记"失败"。日志记录"任务被跳过"和节点轨迹。

### 3. _retry_task 同步跳过检测（runtime.py:908-915）
重试时也做跳过检测，避免重试后仍误报成功。

### 4. _runtime_queue_runner 传入 timeout（maaend_control_page.py:963-964）
`params` 增加 `"timeout": 90`，与 CLI `preset run` 默认一致。CLIBridge._build_args 将其转成 `--timeout 90` 命令行参数。

## 影响面

### 修改文件
- `src/core/service/maa_end/runtime.py`：_wait_job、run_task、_detect_task_skipped（新增）、_retry_task
- `src/gui/pyqt6/pages/maaend_control_page.py`：_runtime_queue_runner

### 行为变化
- **所有通过 GUI/CLI 执行的 task run**：truthy bug 修复后，`job.succeeded` 能正确反映 MaaFW status。之前即使 status=failed 也报成功，现在能正确报失败。
- **跳过检测**：*Schedule 类任务（SellProduct、AutoCollect、AutoStockStaple）在 attach 未启用时会被报为"失败"（日志标注"任务被跳过"），不再误报成功。
- **DijiangRewards 等 JumpBack 任务**：不触发跳过检测（无 End/Done/Skip 节点），行为不变。truthy bug 修复后，如果 JumpBack 走到无 next 节点（status=succeeded），仍会报成功——这是 MaaFW 语义限制，需后续优化。
- **timeout=90**：GUI 队列任务现在有 90s 超时兜底，避免 MaaFW 无限等待卡死 CLI 子进程。

### 不受影响
- run_pipeline：保持返回 bool，_wait_job truthy 修复对其是正向的（之前永远 True，现在能正确反映失败）。
- CLI preset run / queue run：走 run_queue，不经过 run_task，不受影响。

## 非期待变化

### 1. 跳过检测依赖命名约定
`_detect_task_skipped` 通过节点名后缀（End/Done/Skip）和关键词（Main/Start/Loop）判断。如果 MaaEnd 上游变更命名约定，检测可能失效。缓解：检测异常时 return False（不阻断），并记录节点轨迹到日志供诊断。

### 2. 跳过的任务报为"失败"而非"跳过"
当前 run_task 返回 bool，CLI 只能返回 `{"status": "success"/"error"}`。跳过的任务报为 error，UI 显示"失败"。用户可能困惑"为什么失败了"——日志会标注"任务被跳过（未满足执行条件）"。后续可扩展 status 为三态（success/skipped/error），UI 显示"跳过"。

### 3. attach 全 false 的根本原因未解决
本修复只让跳过不再误报成功，但任务仍然不会执行。要让 *Schedule 类任务真正执行，需 GUI 传递 weekday 选项（通过 pipeline_override 写入 attach）。这是配置层面的问题，需 GUI 增加 weekday 选择界面。

### 4. DijiangRewards 的 JumpBack 误报未解决
DijiangRewards 无跳过分支，走 JumpBack 场景跳转。如果跳转链走到无 next 节点，status=succeeded，跳过检测不触发（无 End/Done/Skip 节点），仍会报成功。需后续通过节点轨迹深度分析或 pipeline 结构检测解决。
