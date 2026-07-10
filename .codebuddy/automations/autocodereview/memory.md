# AutoCodeReview 执行记忆

## 最近一次执行
- **时间**：2026-07-10 22:10
- **报告**：`reports/auto/20260710_2210.md`
- **方法**：静态代码逻辑分析（未执行测试）。以 `docs/` 既有审查为基线，只报新问题并标注已修复项，避免重复。

## 本轮新发现（6 项）
- **H1 (High)** scrcpy 首帧 8s 超时过紧 + 失败后不重试（`_scrcpy_session` 死引用阻止重试）+ `IstinaRuntime.connect()` 对 `start_scrcpy` 返回值不检查、误报成功。位置 `android_runtime.py:145/265`、`runtime.py:223`。
- **H2 (Medium)** `MaaEndRuntime.screenshot()` 只读截图失败即置 `_connected=False`，长会话触发误重连。`maa_end/runtime.py:811-829`。
- **M1 (Low)** `handlers.py:677` GPU 推荐 4GB 阈值被 2GB 分支吸收（运算符优先级）。
- **M2 (Low)** 启动期 `metadata list` 被 `_refresh_task_list`/`_refresh_preset_list`/`_do_metadata_load` 重复执行最多 3 次。
- **L1 (Low)** `maaend_control_page.py` 重复定义 `_refresh_queue_list`（294 与 1086），前者不可达。
- **L2 (Low)** `maaend_control_page.py:1380` `_add_task_to_queue` 从未被调用（死方法）。

## 已确认修复（不再重复）
- GUI `_sync_execute` 默认超时 1200ms → 300000（队列可正常执行）。
- `LlamaServerRuntime` atexit 硬编码端口 → 遍历 `_instances`。
- `subprocess.Popen` 死锁 → 改 `DEVNULL`。
- CLI `--timeout` 静默丢弃 → 现已实际下发到 `run_task`。
- 预览失败已引入连续 5 次阈值反写 `_connected`（部分缓解旧"单向闩锁"问题）。

## 注意
- `docs/` 已包含大量历史审查（GUI_CLI_AND_AUTOMATION、RUNTIME_DEVICE_AND_MAAEND、RECOGNITION_PIPELINE_AND_TASKS、LLM_AND_NAVIGATION 等），后续执行应先读 `docs/` 与 `reports/auto/` 避免重复。
- 第三方目录 `MaaEnd/`、`3rd-part/` 不被 git 追踪，审查仅基于本仓库 Python 源码。
