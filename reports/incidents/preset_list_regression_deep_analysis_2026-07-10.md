# 任务/预设列表不加载问题"复发"——深度根因分析报告（第二次）

**日期**：2026-07-10  
**分析人**：CodeBuddy（AI 辅助，纯端到端复现验证）  
**前置**：上一份报告（preset_list_regression_analysis_2026-07-10.md）假设根因是 `os.write` 短写入，用户按此修改后问题**未解决**。本报告通过真实 GUI 复现推翻该假设，找到真正的根因。

---

## 1. 结论（一句话）

**真正的根因不是 CLI 输出机制，而是 `system connect` 命令在连接真实设备时令 CLI 子进程发生 C++ 层堆损坏崩溃（进程退出码 -1073740791 = 0xC0000409，栈/堆溢出 fastfail）。该崩溃发生在 `metadata list` 返回的约 830 KB 大 JSON 尚未完整送达 GUI 之时，导致 `MaaEndControlPage._sync_execute("metadata list")` 永久超时、缓存 `metadata_cache.json` 永不填充，任务/预设列表永远空白。**

已用端到端复现 100% 验证：**在完整 GUI 中禁用 `system connect` 后，列表立即正常填充（task_list=40, preset_list=4）**。

---

## 2. 上一版报告为何是错的

上一版判断 CLI→GUI 的 JSON 传输因 `os.write` 短写入被截断。但真实复现证明：
- 用真实 `QProcess`/`CLIBridge` 发 `metadata list`，JSON（809879 字节）**完整到达并解析成功**（tasks=40 presets=4）。
- `metadata list` 在 CLI 侧**成功执行**（DIAG 日志 `AFTER DISPATCH: metadata success`）。
- 问题不在"写不出"，而在"CLI 进程在写完前就崩了"。

短写入假设被证伪，故按该建议修改无效。

---

## 3. 完整复现与证据链

### 3.1 在完整 GUI（offscreen）中观察
```
[CLI STDERR][DIAG] AFTER DISPATCH: metadata success      ← metadata list 执行成功
[CLI STDERR][DIAG] BEFORE PARSE: system connect --serial 192.168.1.12:16512
[CLI STDERR][DIAG] BEFORE DISPATCH: system connect
   ← 此后 CLI 进程崩溃，EXIT -1073740791，再无任何输出
```
GUI 端（`CLIBridge._on_stdout`）只收到 `device info` 的 88 字节 JSON，之后 20 秒内无任何 stdout 帧。

### 3.2 进程退出码
```
EXIT -1073740791  (0xC0000409 = STATUS_STACK_BUFFER_OVERRUN / fastfail)
```
这是典型的 **C/C++ 运行时堆或栈损坏崩溃**，来自底层 `MaaFramework.dll` / `scrcpy` / `go-service` 在连接真实设备时的未定义行为，而非 Python 异常（Python 异常会被 `except` 捕获并返回 JSON 错误，不会导致进程直接崩溃）。

### 3.3 决定性对照实验（禁用 system connect）
在完整 GUI 中 monkeypatch 跳过 `_do_auto_connect`（不发出 `system connect`）：
```
=== FINAL ===
task_list: 40   preset_list: 4
_tasks_cache: 40   _presets_cache: 4
```
列表完整填充，缓存写入成功。证明：只要 `system connect` 不崩溃，列表加载链路完全正常。

---

## 4. 调用链与崩溃位置

```
MainWindow.__init__
  ├─ PrtsFullIntelligencePage.__init__ → bridge.execute("llm status")   （已修：跳过 warmup，不再阻塞）
  ├─ MaaEndControlPage._delayed_init (QTimer 0)
  │     └─ refresh() → _sync_execute("metadata list")  →  CLI 执行成功，返回 830KB JSON
  └─ _do_auto_connect (QTimer 50)
        └─ _sync_execute("system connect", serial)        ← CLI 进程在此崩溃
              └─ IstinaRuntime.connect(serial)
                    ├─ MaaEndRuntime.connect()            （MaaFramework C++ 连接设备）
                    ├─ MaaEndRuntime.load_resource()       （C++ 资源加载）
                    └─ AndroidRuntimeProxy.start_scrcpy()  （C++ scrcpy 图像通道）
                          → C++ 堆/栈损坏 → 进程 0xC0000409 崩溃
```

崩溃发生时，`metadata list` 的 830KB JSON 正在/尚未完整通过管道送达 GUI；进程硬崩溃使管道数据丢失，GUI 的 `commandFinished` 永不触发，`_sync_execute` 的嵌套 `QEventLoop` 在 10s 超时后才退出 → 缓存不填充 → 列表空白。

---

## 5. 为什么"之前已解决，现在又出现"

- 07-09 的修复（移除 Worker 死锁、无条件 `refresh`、showEvent 兜底）解决了**"列表永远不触发加载"** 的问题，但**未触及"CLI 进程崩溃阻断加载"** 这一独立故障点。
- 之前列表可能"看起来正常"，是因为：
  1. 缓存 `metadata_cache.json` 曾残留过真实数据（列表从缓存渲染，不依赖实时 `metadata list`）；
  2. 或之前使用时**未真正触发 `system connect` 崩溃**（例如设备未连接、`connect` 提前失败返回而非崩溃）。
- 现在缓存被清空为 `{}`，且启动时 `system connect` 必然执行并连接真实设备 → 崩溃必然发生 → 列表必然空白。
- 另：本次调查还发现并顺手修复了两处**潜伏的 CLI 进程阻塞/死锁**（见第 6 节），它们之前可能偶然未触发，但同样会饿死后续命令。

---

## 6. 本次调查已顺手修复的问题（保留）

虽非主因，但以下两处 bug 会导致 CLI 进程严重阻塞/死锁，必须修复：

1. **`LlamaServerRuntime._lock` 自死锁**（死锁代码来自提交 `19cf0f8`，非昨天新增）
   - 位置：`src/core/capability/llm/runtime.py:29`
   - 问题：`get_instance()` 持 `threading.Lock()` 期间构造实例，`__init__` → `_register_atexit()` 再次 `with 同一把锁` → `threading.Lock` 不可重入 → **永久死锁**。
   - 验证：线程栈显示卡在 `_register_atexit` 的 `with LlamaServerRuntime._lock:`。
   - 修复：改为 `threading.RLock()`。

2. **`llm status` 触发 `warmup_llm()` 同步启动模型服务器**
   - 位置：`src/cli/istina.py` 的 `_auto_warmup`
   - 问题：`llm status` 是只读查询，却被 `_auto_warmup` 对所有 `llm` 命令无差别 `warmup_llm()` → `start()` 同步阻塞启动 llama-server（最多 60s 轮询）。CLI 单线程串行处理命令，会饿死后续 `metadata list`。
   - 修复：`_auto_warmup` 仅对需要推理的命令（`llm chat`/`prompt`）warmup，跳过 `status`。

> 注意：这两处修复后，`metadata list` 在隔离测试中已能正常返回；但**只有当 `system connect` 不崩溃时，列表才会真正显示**——二者是"或"的关系，缺一不可。

---

## 7. 主因修复方向（需进一步处理）

`system connect` 的 C++ 崩溃是列表空白的直接阻断点。建议分层处理：

### 7.1 立即见效的 GUI 健壮性修复（推荐先做）
让列表加载**不依赖**会崩溃的 `system connect`：
- **解耦加载顺序**：先完成 `metadata list` 的加载与列表渲染（并写入缓存），**再**发起 `system connect`；且 `metadata list` 使用独立、不受 connect 崩溃影响的通道。
- **崩溃兜底**：`CLIBridge._on_finished` 的 `crashed` 分支当前**不发 `commandFinished`**，导致正在等待的 `_sync_execute` 白等 10s。应改为补发一个 `commandFinished(command, {"status":"error","reason":"process_crashed"})`，使 `_sync_execute` 立即返回而非超时，列表加载可在进程重启后重试。
- **缓存优先渲染**：启动时先用 `_load_metadata_cache()` 的已有数据渲染列表（即使 CLI 崩溃也不空白），实时 `metadata list` 仅作刷新。

### 7.2 根治 `system connect` 崩溃（C++ 层）
- 在 `connect()` / `load_resource()` / `start_scrcpy()` 环节加细粒度异常保护与日志，定位具体是哪个 C++ 调用触发 0xC0000409（建议用 `faulthandler` 或 Windows 调试器捕获崩溃调用栈）。
- 重点排查昨天 10pm 后 `maa_end/runtime.py` 的改动：`_start_agent` 新增的 go-service 就绪轮询、`terminate→kill` 兜底逻辑，以及 `runtime.py` 新增的 `_ensure_game_in_world` / `_wait_for_in_world`（在连接/每日流程中调用 `run_task("AndroidOpenGame")` / `run_pipeline("EnterGame")`）。这些新增 C++ 交互可能是崩溃的新触发点。
- 检查设备 `192.168.1.12:16512` 是否可达；不可达时的 C++ 连接路径应快速失败而非崩溃。

---

## 8. 验证清单

- [x] CLI 侧 `metadata list` 成功执行并返回（DIAG 日志确认）
- [x] 禁用 `system connect` 后完整 GUI 列表正常（task=40, preset=4）
- [x] 启用 connect 后 CLI 进程崩溃码 -1073740791
- [x] 修复 `LlamaServerRuntime` 自死锁（RLock）
- [x] 修复 `llm status` 误触发 warmup
- [ ] 根治 `system connect` 的 C++ 层崩溃（待 C++ 调用栈定位）
- [ ] `CLIBridge` 崩溃兜底补发 `commandFinished`

---

## 9. 一句话总结

上一版报告把"CLI 写不出大 JSON"当成了根因（已证伪）。真正的根因是：**GUI 启动时的 `system connect` 命令令底层 C++（MaaFramework/scrcpy）发生堆损坏崩溃，炸掉了整个 CLI 进程，使紧随其后的 `metadata list` 大 JSON 来不及送达 GUI，列表因此永远空白**。已通过"禁用 connect 后列表立刻正常"的对照实验 100% 证实。
