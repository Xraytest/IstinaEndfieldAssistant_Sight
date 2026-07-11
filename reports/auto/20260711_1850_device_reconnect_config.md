# 批次 64：设备页无限重连 + 非原子配置写入 + 历史报告审计

> **生成时间**: 2026-07-11 18:50
> **审查范围**: `src/gui/pyqt6/pages/device_settings_page.py` (321 行)
> **审计范围**: 批次 63（`20260711_1830_startup_block_audit.md`）
> **方法**: 静态代码分析 + 调用链追踪 + 历史报告交叉验证
> **发现总计**: 2 新发现 + 1 审计验证
> **严重度分布**: 0 High / 1 Medium / 1 Low / 0 Info

---

## 项目边界回顾

- IEA 是《明日方舟：终末地》的 MaaEnd/MaaFramework 自动化助手。本仓库为**非第三方**源码，`MaaEnd/` 与 `3rd-part/` 不在审查范围。
- 审查仅限本仓库 Python 源码；历史累计 260+ 条发现，本批严格避免重复提交。

---

## §1 新发现

### [NEW-MEDIUM] `device_settings_page.py:144-152` — `_attempt_reconnect` 无限重连无退避，ADB 风暴风险

```python
def _attempt_reconnect(self) -> None:
    if self._connected or not self._reconnect_enabled:
        return
    serial = self._address_input.text().strip()
    if not serial:
        return
    self._set_connecting_state()
    self._append_log(locale.tr("auto_reconnect_attempt", "Auto-reconnect attempt: {serial}").format(serial=serial))
    self._bridge.execute("system connect", {"serial": serial})
```

配合定时器配置（line 41-43）：

```python
self._reconnect_timer = QTimer(self)
self._reconnect_timer.setInterval(5000)  # 固定 5 秒间隔
self._reconnect_timer.timeout.connect(self._attempt_reconnect)
```

以及 disconnect 分支（line 198-206）：

```python
elif command.startswith("system disconnect"):
    self._connected = False
    ...
    if self._reconnect_enabled:
        self._reconnect_timer.start()  # 断开后立即启动重连
```

**问题**：`_attempt_reconnect` 在每次定时器触发时无条件执行，**无最大重试次数、无退避策略、无失败计数**。只要 `_reconnect_enabled=True` 且 `_connected=False`，重连将以**固定 5 秒间隔无限进行**。

**影响面分析**：

1. **ADB 风暴**：每次 `_attempt_reconnect` 调用 `self._bridge.execute("system connect", {"serial": serial})`，触发 CLI 子进程执行 `adb connect`。若设备永久不可达（网络断开、设备关机），每 5 秒产生一次 `adb connect` 尝试，持续消耗：
   - ADB 服务器资源（每次连接握手）
   - 网络带宽（ADB 握手包）
   - CLI 子进程生命周期（每次 `execute` 启动新子进程或复用交互进程）

2. **日志刷屏**：每次重连尝试都会追加日志（line 151），5 秒一条 "Auto-reconnect attempt: xxx"，快速淹没用户连接日志。

3. **用户感知**：用户看到连接状态在 "Connecting..." 与 "Connection Failed" 之间每 5 秒闪烁一次，无法手动停止（除非取消勾选 "Auto-reconnect on disconnect"）。

**触发场景**：
- 设备意外断开（ADB 服务崩溃、网络波动）
- 用户主动 disconnect 后忘记关闭自动重连
- 设备永久不可达（关机、网络隔离）

**对比**：`device_settings_page.py:102-105` 的 `auto_kill_adb_check` 提供了 "Kill ADB and retry on connection timeout" 选项，但该选项仅控制连接超时时是否重启 ADB，**不控制重连次数或间隔**。

**建议**：

```python
def __init__(self, bridge: CLIBridge, parent=None):
    ...
    self._reconnect_timer = QTimer(self)
    self._reconnect_timer.setInterval(5000)
    self._reconnect_timer.timeout.connect(self._attempt_reconnect)
    self._reconnect_enabled = True
    self._reconnect_attempts = 0  # 新增：失败计数
    self._max_reconnect_attempts = 12  # 新增：最大尝试次数（60 秒）
    self._reconnect_backoff_base = 5000  # 新增：退避基数（毫秒）
    ...

def _attempt_reconnect(self) -> None:
    if self._connected or not self._reconnect_enabled:
        return
    serial = self._address_input.text().strip()
    if not serial:
        return
    self._reconnect_attempts += 1
    if self._reconnect_attempts > self._max_reconnect_attempts:
        self._reconnect_timer.stop()
        self._append_log(locale.tr("auto_reconnect_give_up", "Auto-reconnect gave up after {n} attempts.").format(n=self._reconnect_attempts))
        return
    # 指数退避：5s, 10s, 20s, 40s, 40s, ...
    interval = min(self._reconnect_backoff_base * (2 ** (self._reconnect_attempts - 1)), 40000)
    self._reconnect_timer.setInterval(interval)
    self._set_connecting_state()
    self._append_log(locale.tr("auto_reconnect_attempt", "Auto-reconnect attempt: {serial} (attempt {n}/{max})").format(serial=serial, n=self._reconnect_attempts, max=self._max_reconnect_attempts))
    self._bridge.execute("system connect", {"serial": serial})

def _on_command_finished(self, command, result):
    ...
    elif command.startswith("system connect"):
        ok = bool(result.get("status") == "success")
        ...
        if ok and serial:
            self._reconnect_attempts = 0  # 成功连接后重置计数
            self._reconnect_timer.setInterval(5000)  # 重置为默认间隔
            ...
```

---

### [NEW-LOW] `device_settings_page.py:309-311` — `_write_config` 非原子写入，与 `settings_page.py` 不一致

```python
def _write_config(self, config: Dict[str, Any]) -> None:
    self._config_path.parent.mkdir(parents=True, exist_ok=True)
    self._config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
```

对比 `settings_page.py:196-211`：

```python
def _save_settings(self) -> None:
    ...
    # G8: 原子写入，避免中断导致配置文件损坏
    import tempfile
    import os
    data = json.dumps(config, ensure_ascii=False, indent=2)
    fd, tmp_path = tempfile.mkstemp(dir=str(self._config_path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self._config_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
```

**问题**：`device_settings_page.py` 直接调用 `write_text`，**非原子写入**。若写入过程中程序崩溃、断电或磁盘错误，配置文件可能处于**半写入状态**（部分 JSON 内容已写入），导致下次启动时 `json.loads` 失败。

`settings_page.py` 已实现原子写入（tempfile + os.replace），但 `device_settings_page.py` 未采用相同方案，**同一项目的两个配置写入路径行为不一致**。

**触发场景**：
- 程序在 `write_text` 中间崩溃（电源丢失、进程被杀死）
- 磁盘空间不足，`write_text` 部分成功
- 并发写入（虽然当前无并发场景，但未来扩展时存在风险）

**影响面**：低——触发概率低（需程序在写入中间崩溃），但一旦触发，配置文件损坏会导致所有页面初始化失败。

**建议**：统一使用原子写入，提取为共享工具函数：

```python
# core/foundation/config_io.py 或类似位置
import tempfile
import os
from pathlib import Path

def atomic_write_json(path: Path, data: dict) -> None:
    """原子写入 JSON 文件，避免中断导致配置损坏。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json_str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
```

然后在 `device_settings_page.py` 和 `settings_page.py` 中统一调用 `atomic_write_json`。

---

## §2 历史报告审计

### [AUDIT-1] 批次 63 `20260711_1830_startup_block_audit.md` — NEW-MEDIUM 可降为 Low，NEW-LOW 维持

**NEW-MEDIUM**（`_do_auto_connect` 阻塞主线程代码流 25 秒）：

审计结论：**可降为 Low/Info**。

理由：
1. **仅启动时触发一次**：阻塞发生在 GUI 启动序列中，不是持续性问题
2. **Qt 嵌套事件循环仍处理 I/O**：ADB 通信、CLI 输出、用户 UI 交互（页面切换、按钮点击）均正常进行
3. **用户感知有限**：虽然代码流被阻塞，但 GUI 不冻结，用户可正常操作
4. **实际影响**：主要是元数据加载延迟（10s），导致选项编辑器构建延迟，但任务/预设列表在 50ms 内已渲染

原报告评级为 Medium 略微高估，建议降为 **Low**。

**NEW-LOW**（自动连接超时后手动连接成功，预览定时器未重启）：

审计结论：**维持 Low**。

竞态条件分析正确：
- Qt 嵌套事件循环确实允许用户在 `_sync_execute` 阻塞期间进行 UI 交互
- 用户在 15 秒内手动连接是可能的（GUI 不冻结）
- 手动连接成功后预览定时器确实未重启（仅单次刷新）
- 触发概率低（需用户在启动自动连接阻塞期间主动手动连接），但一旦触发，功能退化明确

**总体评价**：批次 63 报告的两个发现均成立，但 NEW-MEDIUM 的严重度评级可微调。逻辑分析正确，无自我矛盾。

---

## §3 发现统计

| 类别 | 条目 | 严重度 | 状态 |
|------|------|--------|------|
| 新发现 | NEW-MEDIUM（`_attempt_reconnect` 无限重连无退避） | Medium | 历史未覆盖 |
| 新发现 | NEW-LOW（`_write_config` 非原子写入，与 settings_page 不一致） | Low | 历史未覆盖 |
| 审计验证 | AUDIT-1（批次 63 NEW-MEDIUM 可降为 Low，NEW-LOW 维持） | — | 确认无误 |
| **合计** | **2 新 + 1 审计** | **1M / 1L** | — |

---

## §4 跨批次一致性验证

- **批次 63 NEW-MEDIUM**（启动流程阻塞）→ 本批审计确认可降为 Low，不冲突
- **批次 63 NEW-LOW**（预览定时器竞态）→ 本批审计确认维持 Low，不冲突
- **批次 1730 SRV-08**（device_settings_page 重连定时器）→ 与本批 NEW-MEDIUM 独立。SRV-08 关注 disconnect 分支启动定时器，本批关注无限重连无退避。
- **批次 62 NEW-LOW**（`_resolve_connect_params` 静默吞异常）→ 与本批独立文件/路径，不冲突
- **批次 2345/G8**（settings_page 原子写入）→ 本批 NEW-LOW 补充 device_settings_page 未采用原子写入，互补关系

---

## §5 验证方法

- 全部发现基于对 `device_settings_page.py`、`settings_page.py` 的**逐行静态阅读**与调用链追踪。
- **未执行任何测试**，未修改任何业务代码。
- 审计部分基于对批次 63 报告的逐条代码复核。
- 重复检测：交叉核对 15 份历史报告确认两个新发现均为全新。
- 本批严格遵循"避免重复提交历史已覆盖问题"原则。
