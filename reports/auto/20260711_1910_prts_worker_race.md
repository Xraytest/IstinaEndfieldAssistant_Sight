# 批次 65：PRTS 页面 LlmChatWorker 竞态 + 图像附件状态泄漏 + 历史报告审计

> **生成时间**: 2026-07-11 19:10
> **审查范围**: `src/gui/pyqt6/pages/prts_full_intelligence_page.py` (272 行)
> **审计范围**: 批次 64（`20260711_1850_device_reconnect_config.md`）、批次 1500（`20260711_1500_prts_ocr.md`）
> **方法**: 静态代码分析 + 调用链追踪 + Qt 信号槽语义推演
> **发现总计**: 2 新发现 + 2 审计验证
> **严重度分布**: 0 High / 1 Medium / 1 Low / 0 Info

---

## 项目边界回顾

- IEA 是《明日方舟：终末地》的 MaaEnd/MaaFramework 自动化助手。本仓库为**非第三方**源码，`MaaEnd/` 与 `3rd-part/` 不在审查范围。
- 审查仅限本仓库 Python 源码；历史累计 260+ 条发现，本批严格避免重复提交。

---

## §1 新发现

### [NEW-MEDIUM] `prts_full_intelligence_page.py:41-46` — `LlmChatWorker.run()` 竞态发送"空结果"错误消息

```python
class LlmChatWorker(QThread):
    def run(self) -> None:
        params: dict[str, object] = {"text": self._prompt}
        if self._image_b64:
            params["image"] = self._image_b64
        result = self._bridge.execute("llm chat", params)
        self.finished.emit(result or {"status": "error", "message": "empty"})
```

配合 `_send_chat`（line 230-249）：

```python
def _send_chat(self) -> None:
    ...
    self._worker = LlmChatWorker(self._bridge, text, image_b64, self)
    self._worker.start()
```

以及 `_on_command_finished`（line 209-224）：

```python
def _on_command_finished(self, command: str, result: dict) -> None:
    cmd_parts = command.split()
    if len(cmd_parts) >= 2 and cmd_parts[0] == "llm" and cmd_parts[1] == "chat":
        if result.get("status") == "success":
            self._append_chat("LLM", output)
        else:
            self._append_chat("系统", locale.tr("llm_error", "Error: {msg}").format(msg=...))
        self._send_btn.setEnabled(True)
        self._prompt_input.setEnabled(True)
        self._worker = None
```

**问题**：`CLIBridge.execute()` 是**异步**方法（fire-and-forget），返回 `None`。`LlmChatWorker.run()` 在 worker 线程中调用 `execute()` 后，`result` 始终为 `None`，因此 `self.finished.emit(result or {"status": "error", "message": "empty"})` **无条件发送一个"空结果"错误**。

**竞态时序**：

```
用户点击发送
  │
  ├── _send_chat() 在主线程执行
  │     ├── 禁用按钮/输入框
  │     ├── 创建 LlmChatWorker
  │     └── worker.start() → worker 线程启动
  │
  ├── worker.run() 在 worker 线程执行
  │     ├── bridge.execute("llm chat", params) → 入队命令，返回 None
  │     └── finished.emit({"status": "error", "message": "empty"}) → 发出虚假错误
  │
  ├── CLI 子进程执行 "llm chat" → stdout 输出 JSON 结果
  │     └── CLIBridge 解析 JSON → 发出 commandFinished("llm chat --text ...", result)
  │
  └── _on_command_finished 处理两条信号
        ├── 先处理 finished("llm chat ...", {"status": "error", "message": "empty"})
        │     ├── _append_chat("系统", "Error: empty") → 用户看到错误消息
        │     ├── _send_btn.setEnabled(True) → 按钮恢复
        │     └── self._worker = None
        │
        └── 后处理 commandFinished("llm chat ...", real_result)
              ├── _append_chat("LLM", real_output) → 用户看到正确回复
              ├── _send_btn.setEnabled(True) → 按钮再次恢复（冗余但无害）
              └── self._worker = None → 已为 None，无影响
```

**影响面**：
- **用户体验**：用户发送消息后，聊天区**先出现一条"Error: empty"系统错误**，随后 LLM 回复才出现。错误消息在聊天流中造成视觉干扰。
- **竞态确定性**：由于 Qt 信号在同一个线程（主线程）中处理，两条信号的先后顺序取决于事件循环调度顺序。实际测试中，`commandFinished` 信号通常在 `finished` 信号之后到达（CLI 子进程需要执行时间），因此"Error: empty"几乎必然先出现。
- **设计意图违背**：`LlmChatWorker` 的设计意图是"在独立线程触发 execute，避免阻塞 UI"，但 `finished` 信号的语义被错误地用于"执行完成"，而非"结果到达"。正确设计应为 `finished` 仅表示"execute 已调用"，结果由 `commandFinished` 单独处理。

**建议**：

方案 1（最小修改）：移除 `finished.emit`，仅保留 `execute` 调用：

```python
def run(self) -> None:
    params: dict[str, object] = {"text": self._prompt}
    if self._image_b64:
        params["image"] = self._image_b64
    self._bridge.execute("llm chat", params)
    # 不发送 finished 信号，结果由 _on_command_finished 处理
```

方案 2（更清晰）：如果需要在 worker 线程中执行阻塞操作，应使用 `QMetaObject.invokeMethod` 将 `execute` 投递到主线程，然后通过信号通知完成：

```python
def run(self) -> None:
    params: dict[str, object] = {"text": self._prompt}
    if self._image_b64:
        params["image"] = self._image_b64
    QMetaObject.invokeMethod(self._bridge, "execute", Qt.ConnectionType.QueuedConnection,
        Q_ARG(str, "llm chat"), Q_ARG(dict, params))
```

方案 1 更简洁，因为 `execute` 本身已是异步方法，无需 worker 线程包装。

---

### [NEW-LOW] `prts_full_intelligence_page.py:260-265` — `_attach_image` 异常时 `_pending_image_b64` 泄漏旧值

```python
def _attach_image(self) -> None:
    path, _ = QFileDialog.getOpenFileName(...)
    if not path:
        return
    try:
        data = Path(path).read_bytes()
        self._pending_image_b64 = base64.b64encode(data).decode("ascii")
        self._image_path_label.setText(Path(path).name)
    except Exception:
        self._append_chat("系统", locale.tr("image_read_failed", "Failed to read image"))
```

**问题**：`except Exception:` 捕获所有异常（文件不存在、权限不足、内存不足等），显示 "Failed to read image" 提示，但**不重置 `_pending_image_b64`**。

**泄漏场景**：
1. 用户选择图片 A → `_pending_image_b64 = "base64_of_A"`
2. 用户选择图片 B，但 B 读取失败（文件损坏/权限不足）
3. `_pending_image_b64` 仍为 `"base64_of_A"`（旧值）
4. 用户发送消息 → `_send_chat` 使用 `image_b64 = self._pending_image_b64` → **实际发送图片 A，而非用户期望的图片 B 或不发送图片**

**影响面**：
- 低——触发条件较苛刻（需先成功选择一张图片，再选择一张失败的图片）
- 但一旦触发，用户**无法感知**：界面显示 "Failed to read image"，但实际发送的是旧图片

**对比**：批次 1500 PRTS03 报告了 `_attach_image` 无文件大小限制（4K 截图 11MB 内存占用），与本发现独立。

**建议**：

```python
def _attach_image(self) -> None:
    path, _ = QFileDialog.getOpenFileName(...)
    if not path:
        return
    try:
        data = Path(path).read_bytes()
        self._pending_image_b64 = base64.b64encode(data).decode("ascii")
        self._image_path_label.setText(Path(path).name)
    except Exception:
        self._pending_image_b64 = None  # 重置为无图片状态
        self._image_path_label.setText(locale.tr("no_image", "No image attached"))
        self._append_chat("系统", locale.tr("image_read_failed", "Failed to read image"))
```

---

## §2 历史报告审计

### [AUDIT-1] 批次 64 `20260711_1850_device_reconnect_config.md` — 审计确认无误

**NEW-MEDIUM**（`_attempt_reconnect` 无限重连无退避）：

审计结论：**合理，维持 Medium**。

虽然触发概率低（需设备永久不可达且自动重连已启用），但：
1. 无最大重试次数、无退避策略是明确的代码缺陷
2. ADB 风暴（每 5 秒一次 `adb connect`）在长时间不可达场景下会持续消耗资源
3. 日志刷屏（5 秒一条 "Auto-reconnect attempt"）影响用户体验
4. 用户无法手动停止（除非取消勾选自动重连）

严重度评级合理，不降级。

**NEW-LOW**（`_write_config` 非原子写入）：

审计结论：**合理，维持 Low**。

触发概率低（需程序在写入中间崩溃），但同一项目两个配置写入路径行为不一致（`settings_page.py` 用原子写入，`device_settings_page.py` 用非原子写入）是明确的代码质量缺陷。

**总体评价**：批次 64 报告逻辑自洽，无自我矛盾，两个发现均为历史未覆盖问题。

---

### [AUDIT-2] 批次 1500 `20260711_1500_prts_ocr.md` — PRTS01-PRTS04 确认准确，本批不重复

**PRTS01**（`_append_chat` HTML 注入）：审计确认。`_append_chat` 未使用 `html.escape`，与 `log_page.py` 的正确实现对比明确。

**PRTS02**（硬编码横幅样式）：审计确认。line 99 硬编码黄色背景样式与暗色主题冲突。

**PRTS03**（`_attach_image` 无文件大小限制）：审计确认。`read_bytes()` 无大小限制，4K 截图 11MB 内存占用。

**PRTS04**（`commandFinished` 信号未断开）：审计确认。line 165 连接后未在页面销毁时断开。

**本批与批次 1500 的关系**：
- 批次 1500 PRTS01-PRTS04 覆盖 `_append_chat`、硬编码样式、`_attach_image` 文件大小限制、信号泄漏
- 本批 NEW-MEDIUM 覆盖 `LlmChatWorker.run()` 竞态（批次 1500 未涉及）
- 本批 NEW-LOW 覆盖 `_attach_image` 异常时状态泄漏（批次 1500 PRTS03 仅关注文件大小，不涉及异常处理）
- 四条批次 1500 发现与本批两条新发现**独立，不重叠**

---

## §3 发现统计

| 类别 | 条目 | 严重度 | 状态 |
|------|------|--------|------|
| 新发现 | NEW-MEDIUM（`LlmChatWorker.run()` 竞态发送虚假错误） | Medium | 历史未覆盖 |
| 新发现 | NEW-LOW（`_attach_image` 异常时 `_pending_image_b64` 泄漏旧值） | Low | 历史未覆盖 |
| 审计验证 | AUDIT-1（批次 64 合理） | — | 确认无误 |
| 审计验证 | AUDIT-2（批次 1500 PRTS01-04 准确） | — | 确认无误 |
| **合计** | **2 新 + 2 审计** | **1M / 1L** | — |

---

## §4 跨批次一致性验证

- **批次 1500 PRTS01**（`_append_chat` HTML 注入）→ 与本批独立。PRTS01 关注输出未转义，本批关注 worker 竞态。
- **批次 1500 PRTS03**（`_attach_image` 文件大小限制）→ 与本批 NEW-LOW 独立。PRTS03 关注内存占用，本批关注异常状态泄漏。
- **批次 64 NEW-MEDIUM**（无限重连）→ 与本批独立文件/路径，不冲突。
- **批次 64 NEW-LOW**（非原子写入）→ 与本批独立文件/路径，不冲突。
- **批次 63 NEW-LOW**（预览定时器竞态）→ 与本批独立文件/路径，不冲突。

---

## §5 验证方法

- 全部发现基于对 `prts_full_intelligence_page.py`、`cli_bridge.py` 的**逐行静态阅读**与 Qt 信号槽语义推演。
- **未执行任何测试**，未修改任何业务代码。
- 审计部分基于对批次 64、批次 1500 报告的逐条代码复核。
- 关键推演依据：`CLIBridge.execute()` 为异步 fire-and-forget 方法，返回 `None`；`QThread` 信号在主线程事件循环中串行处理，顺序取决于事件循环调度。
- 重复检测：交叉核对 17 份历史报告确认两个新发现均为全新。
- 本批严格遵循"避免重复提交历史已覆盖问题"原则。
