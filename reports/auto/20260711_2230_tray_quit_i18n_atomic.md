# 批次 75：托盘退出失效 / 默认页硬编码中文 / 非原子写入扩散 / i18n 硬编码 / recorder 路径错误 / 审计批次 7/8

> **生成时间**: 2026-07-11 22:30
> **审查范围**: `src/gui/pyqt6/main_window.py` (350+ 行), `src/gui/pyqt6/tray_icon.py` (87 行), `src/gui/pyqt6/pages/prts_full_intelligence_page.py` (272 行), `src/gui/pyqt6/scripting/recorder.py` (216 行), `src/gui/pyqt6/pages/device_settings_page.py` (321 行), `src/gui/pyqt6/pages/maaend_control_page.py` (174, 1575), `src/core/foundation/logger.py` (118), `src/core/foundation/paths.py` (22), `src/scripting/models.py` (53), `src/cli/istina.py` (14)
> **审计范围**: 批次 7（`001647_device_layer.md` D1）、批次 8（`0200_nav.md` NAV-01）
> **方法**: 静态代码逻辑分析 + 调用链推演
> **发现总计**: 9 新发现 + 2 审计验证
> **严重度分布**: 0 High / 0 Medium / 4 Low / 3 Info / 2 审计

---

## 项目边界回顾

- IEA 是《明日方舟：终末地》的 MaaEnd/MaaFramework 自动化助手。本仓库为**非第三方**源码，`MaaEnd/` 与 `3rd-part/` 不在审查范围。
- 审查仅限本仓库 Python 源码；历史累计 270+ 条发现，本批严格避免重复提交。
- 本批聚焦：主窗口导航默认项、托盘退出行为、PRTS 页面自动启动、录制器路径、配置写入原子性、i18n 硬编码、foundation 层路径绕过。

---

## §1 新发现

### [GUI-05 Low] `tray_icon.py:64` — 托盘"退出"菜单项点击后应用不退出

```python
# tray_icon.py:64
quit_action = QAction(locale.tr("tray_quit"), self._main_window)
quit_action.triggered.connect(QApplication.instance().quit)
menu.addAction(quit_action)
```

**根因分析**：`QApplication.instance().quit()` 调用 `closeAllWindows()`，遍历所有顶层窗口发送 `QCloseEvent`。`MainWindow.closeEvent`（`main_window.py:108-122`）在托盘可用时拦截事件：

```python
# main_window.py:108-122
def closeEvent(self, event: QCloseEvent) -> None:
    ...
    if self._tray_icon is not None and self._tray_icon.is_available():
        event.ignore()       # ← 拒绝关闭事件
        self.hide()
    else:
        ...                  # ← 只有托盘不可用时才真正关闭
```

**调用链推演**：

```
用户点击托盘"退出"
  │
  ├── quit_action.triggered
  ├── QApplication.instance().quit()
  │     └── QApplication.closeAllWindows()
  │           └── MainWindow.closeEvent(QCloseEvent)
  │                 ├── tray_icon.is_available() → True
  │                 ├── event.ignore()          ← 拒绝！
  │                 └── self.hide()
  │
  ├── closeAllWindows() 返回 False（未全部关闭）
  └── quit() 中止       ← 应用仍在运行！
```

**问题**：
1. **退出功能失效**：托盘"退出"菜单项点击后，窗口隐藏而非关闭。用户无法通过托盘菜单正常退出应用。
2. **状态未保存**：`_persist_state()` 仅在 `closeEvent` 的 `else` 分支（托盘不可用时）调用。托盘退出路径绕过状态持久化。
3. **与 UX 预期矛盾**：用户点击"退出"期望应用终止，实际仅隐藏到托盘。

**影响面**：
- **UX 缺陷**：用户被迫通过任务管理器强制结束进程。
- **数据丢失**：队列状态（`maaend_task_state.json`）在托盘退出路径中不保存。

**建议**：

方案 1（推荐）：在 `MainWindow` 添加 `_quitting` 标志位，托盘退出前设置该标志：

```python
# main_window.py
def __init__(self, ...):
    ...
    self._quitting = False

def closeEvent(self, event: QCloseEvent) -> None:
    if self._quitting:
        # 真正的退出——保存状态后关闭
        self._persist_state()
        super().closeEvent(event)
        return
    if self._tray_icon is not None and self._tray_icon.is_available():
        event.ignore()
        self.hide()
        ...

def quit_application(self) -> None:
    self._quitting = True
    QApplication.instance().quit()

# tray_icon.py
quit_action.triggered.connect(self._main_window.quit_application)
```

方案 2（最小）：托盘退出时直接调用 `QApplication.exit(0)` 绕过 `closeAllWindows`：

```python
quit_action.triggered.connect(lambda: QApplication.instance().exit(0))
```

但此方案不保存状态，不如方案 1。

---

### [GUI-04 Low] `main_window.py:221` — 默认页面选择使用硬编码中文

```python
# main_window.py:220-223
for i in range(self._navigation_list.count()):
    if self._navigation_list.item(i).text() == "标准推理":
        self._navigation_list.setCurrentRow(i)
        break
```

**根因分析**：页面列表（lines 195-201）使用 `locale.tr(...)` 动态本地化标签，但默认选中逻辑使用硬编码中文 `"标准推理"`。

**调用链推演**：

```
启动时
  │
  ├── pages 列表：locale.tr("maaend_title", "Standard Inference")
  │     → 中文环境: "标准推理"
  │     → 英文环境: "Standard Inference"
  │
  ├── 导航项标签 = locale.tr(...) 结果
  │     → 中文环境: "标准推理" ✓
  │     → 英文环境: "Standard Inference"
  │
  ├── 默认选中检查: item.text() == "标准推理"
  │     → 中文环境: "标准推理" == "标准推理" → 选中 ✓
  │     → 英文环境: "Standard Inference" == "标准推理" → 不匹配 ✗
  │
  └── 英文环境下默认不选中任何页面，或选中错误页面
```

**问题**：
1. **硬编码中文**：英文环境下 `"Standard Inference"` 永远不会匹配 `"标准推理"`，默认选中逻辑失效。
2. **非期待副作用**：`locale.tr("maaend_title", "Standard Inference")` 在不同 locale 下返回不同文本，但比较逻辑固定为中文，导致英文环境下默认选中第一项（PRTS 页面）而非"标准推理"页面。

**影响面**：
- **UX 缺陷**：英文环境下启动后默认选中 PRTS 页面（施工中横幅），而非用户最常用的"标准推理"页面。
- **频率**：每次英文/其他 locale 启动时触发。

**建议**：

```python
# 方案 1：使用 locale key 而非文本比较
for i in range(self._navigation_list.count()):
    accessible_text = self._navigation_list.item(i).data(Qt.ItemDataRole.AccessibleTextRole)
    if accessible_text == "nav_maaend":
        self._navigation_list.setCurrentRow(i)
        break

# 方案 2：直接按索引选中（页面顺序固定）
self._navigation_list.setCurrentRow(1)  # "标准推理"是第二项（索引1）
```

---

### [I18N-04 Low] `maaend_control_page.py:174` — 选项标签 locale 路径硬编码为中文

```python
# maaend_control_page.py:174
_OPTION_LOCALE_PATH = Path(__file__).resolve().parent.parent.parent.parent.parent / "3rd-part" / "maaend" / "locales" / "interface" / "zh_cn.json"
OPTION_LOCALE: Dict[str, str] = {}
try:
    if _OPTION_LOCALE_PATH.exists():
        OPTION_LOCALE = json.loads(_OPTION_LOCALE_PATH.read_text(encoding="utf-8"))
except Exception:
    OPTION_LOCALE = {}
```

**根因分析**：`_OPTION_LOCALE_PATH` 硬编码为 `zh_cn.json`，不随 `locale.current_locale()` 变化。无论用户选择哪种语言，选项标签始终从中文文件加载。

**调用链推演**：

```
用户切换语言为英文
  │
  ├── locale.set_locale("en")
  ├── settings_page.py 等页面通过 locale.tr() 刷新 → 英文 ✓
  ├── HeroHeader 等组件刷新 → 英文 ✓
  │
  ├── maaend_control_page.py 的 OPTION_LOCALE
  │     → 仍从 zh_cn.json 加载
  │     → 选项标签保持中文 ✗
  │
  └── 标准推理页选项标签中英文混合
```

**问题**：
1. **locale 不联动**：`OPTION_LOCALE` 在模块导入时（line 174）从 `zh_cn.json` 一次性加载，之后不再更新。
2. **与 i18n 体系脱节**：`locale.tr()` 支持多语言切换，但 `OPTION_LOCALE` 是独立的中文字典，不响应 `set_locale()`。

**影响面**：
- **UX 缺陷**：用户切换到英文后，标准推理页的任务选项标签仍显示中文，与页面其他部分语言不一致。
- **频率**：每次非中文 locale 启动时触发。

**建议**：

```python
def _get_option_locale() -> Dict[str, str]:
    current = locale.current_locale()
    locale_path = (
        Path(__file__).resolve().parent.parent.parent.parent.parent
        / "3rd-part" / "maaend" / "locales" / "interface"
        / f"{current}.json"
    )
    if locale_path.exists():
        try:
            return json.loads(locale_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    # 回退到中文
    fallback = locale_path.with_name("zh_cn.json")
    if fallback.exists():
        return json.loads(fallback.read_text(encoding="utf-8"))
    return {}

# 在需要时动态加载，而非模块级一次性加载
OPTION_LOCALE = _get_option_locale()
```

---

### [SEC-03 Low] `device_settings_page.py:311` — 配置写入非原子操作

```python
# device_settings_page.py:311
self._config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
```

**根因分析**：`_write_config` 使用 `Path.write_text` 直接写入目标文件。若进程在写入中途被中断（崩溃、断电、强制终止），配置文件将处于半写状态——JSON 截断或不完整，导致后续 `json.loads` 抛出 `JSONDecodeError`。

**与 `settings_page.py` 对比**：

`settings_page.py:196-211` 使用原子写入：

```python
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

但 `device_settings_page.py:311`、`maaend_control_page.py:872/1575`、`models.py:53` 均使用直接 `write_text`，无原子保护。

**影响面**：
- **数据完整性**：配置/脚本/元数据文件可能在中断后损坏。
- **不一致性**：项目内同一类操作（JSON 文件写入）有两种实现，维护者易遗漏新文件使用原子写入。

**建议**：

统一使用原子写入辅助函数：

```python
# core/foundation/io.py
def atomic_write_json(path: Path, data: dict) -> None:
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False, indent=2))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
```

---

### [SEC-04 Info] `models.py:53` — 脚本保存非原子写入

```python
# models.py:53
path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
```

**根因分析**：与 SEC-03 同一模式——直接 `write_text` 无原子保护。录制脚本在保存时若被中断，脚本文件损坏，回放功能失效。

**影响面**：
- **低**：脚本录制/回放是辅助功能，中断写入场景罕见。
- **与 SEC-03 关联**：同一修复方案可同时覆盖。

---

### [REC-02 Info] `recorder.py:56` — 录制器保存目录路径错误（同 GUI-03 模式）

```python
# recorder.py:56
self._save_directory = save_directory or Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "recorded"
```

**根因分析**：与批次 74 GUI-03 同一模式——4 级 parent 链到达 `src/` 而非项目根，然后拼接 `"scripts/recorded"` 得到 `src/scripts/recorded`（错误位置）。

```
__file__ = src/gui/pyqt6/scripting/recorder.py
parent.parent.parent.parent → src/
→ src/scripts/recorded (错误)
```

**影响面**：
- **与 GUI-03 相同**：脚本录制功能将脚本保存到 `src/scripts/recorded/` 而非项目根下的 `scripts/recorded/`。
- **双重错误位置**：`scripting_page.py:39` 和 `recorder.py:56` 均使用错误路径，两个入口写入同一错误目录，造成混乱。

**建议**：

```python
from core.foundation.paths import get_project_root
self._save_directory = save_directory or get_project_root() / "scripts" / "recorded"
```

---

### [GUI-06 Info] `prts_full_intelligence_page.py:62-66` — 页面首次显示自动启动 LLM

```python
# prts_full_intelligence_page.py:62-66
def showEvent(self, event) -> None:
    super().showEvent(event)
    if not self._auto_started:
        self._auto_started = True
        self._start_llm()
```

**根因分析**：`showEvent` 在页面首次显示时自动调用 `_start_llm()`，启动 LLM 子进程。用户仅浏览页面（点击导航标签查看）就会触发 LLM 启动。

**调用链推演**：

```
用户导航到"PRTS 全智能"页面（仅浏览）
  │
  ├── PrtsFullIntelligencePage.showEvent()
  ├── self._auto_started = True
  ├── self._start_llm() → "llm start" 命令
  ├── LLM 子进程启动（占用 ~1-2 GB VRAM）
  │
  └── 用户仅想查看页面，实际启动了重量级 LLM
```

**问题**：
1. **副作用不可预期**：浏览页面触发 LLM 启动，消耗大量 GPU 显存和系统资源。
2. **无明确提示**：启动过程在后台进行，页面标题仅显示"Starting..."，用户可能不知道 LLM 正在加载。
3. **施工中横幅矛盾**：页面顶部有"⚠ 此页面正在施工中，功能尚未完全实现"横幅，但页面显示时自动启动 LLM，与"施工中"状态矛盾。

**影响面**：
- **UX 缺陷**：无意中启动 LLM 导致系统变慢、显存占用。
- **频率**：每次首次导航到 PRTS 页面时触发。

**建议**：

移除自动启动，改为用户显式点击"Start LLM"按钮：

```python
def showEvent(self, event) -> None:
    super().showEvent(event)
    # 不自动启动——仅更新状态
    self._update_llm_status()
```

---

### [GUI-07 Low] `prts_full_intelligence_page.py:194-200` — LLM 启动超时后 UI 状态不一致

```python
# prts_full_intelligence_page.py:193-200
def _poll_startup_status(self) -> None:
    self._startup_poll_count += 1
    if self._startup_poll_count > 30:
        if self._startup_timer is not None:
            self._startup_timer.stop()
        self._status_label.setText(locale.tr("llm_timeout", "Timeout"))
        self._status_label.setStyleSheet(RED_STYLE)
        return
    self._bridge.execute("llm status", {})
```

**根因分析**：超时后（30 次 × 2s = 60s），`_startup_timer.stop()` 停止轮询，UI 显示红色 "Timeout"。但 LLM 进程可能仍在启动中（`_start_llm` 发送了 `"llm start"` 命令后未跟踪子进程状态）。

**调用链推演**：

```
_start_llm() 被调用
  │
  ├── self._bridge.execute("llm start", {})
  ├── self._startup_timer.start(2000)
  │
  │   60 秒后（30 次轮询）
  │   ├── _startup_timer.stop()
  │   ├── status_label → "Timeout" (红色)
  │   └── 但 LLM 子进程仍在启动...
  │
  ├── 用户看到"Timeout"，以为 LLM 失败
  ├── 用户点击"Start LLM"再试
  └── 两次 LLM 启动冲突（旧进程仍在）
```

**问题**：
1. **进程泄漏**：超时后 LLM 子进程未被终止，后台继续运行。
2. **UI 误导**："Timeout" 状态暗示 LLM 启动失败，但实际可能仍在加载中。
3. **重试冲突**：用户再次点击"Start LLM"时，旧 LLM 进程与新进程可能冲突。

**影响面**：
- **资源泄漏**：LLM 子进程在超时后继续占用显存。
- **UX 困惑**：用户看到"Timeout"但不确定 LLM 是否实际运行。

**建议**：

超时后发送 `"llm stop"` 终止 LLM：

```python
def _poll_startup_status(self) -> None:
    self._startup_poll_count += 1
    if self._startup_poll_count > 30:
        if self._startup_timer is not None:
            self._startup_timer.stop()
        self._status_label.setText(locale.tr("llm_timeout", "Timeout"))
        self._status_label.setStyleSheet(RED_STYLE)
        # 超时后终止 LLM，避免进程泄漏
        self._bridge.execute("llm stop", {})
        self._worker = None  # 重置 worker 引用
        return
    self._bridge.execute("llm status", {})
```

---

### [I18N-05 Info] `logger.py:118` — 绕过 `get_project_root()` 函数

```python
# logger.py:118
project_root = Path(__file__).resolve().parent.parent.parent.parent
```

**根因分析**：`init_logger()` 使用 `Path(__file__).resolve().parent.parent.parent.parent` 自行推断项目根目录，而非调用 `get_project_root()`。两者当前计算到同一路径（`src/core/foundation/` → 4 级 parent → 项目根），但违反了项目规范。

**CLAUDE.md 规定**：

> Always use `core.foundation.paths` for path resolution. Never hardcode paths or use `__file__`/`dirname()` chains.

**影响面**：
- **维护风险**：若 `paths.py` 的 `get_project_root()` 逻辑变更（如目录结构调整），`logger.py:118` 不会同步更新，路径推断失效。
- **一致性**：项目内 5 处使用 parent 链推断根目录（`paths.py`, `logger.py`, `queue_state.py`, `qt_log_filter.py`, `istina.py`），仅 `paths.py` 是正确实现，其余 4 处应统一调用 `get_project_root()`。

**建议**：

```python
from core.foundation.paths import get_project_root
project_root = get_project_root()
```

---

## §2 审计：历史报告验证

### [AUDIT-1] 批次 7 D1 — 已修复，确认原报告准确

**审计范围**：批次 7 `001647_device_layer.md` D1 — `recovery.py:72` `_force_stop` 参数传递

**当前代码**：

```python
self._run(["shell", "am", "force-stop", self._package], serial)  # D1: 防御性拆分 argv，等价于 am force-stop <pkg>
```

**验证结论**：**原报告准确，已修复**。

- 原报告指出 `"am force-stop"` 作为单个参数传递导致 mksh 误解析。
- 当前代码已修复为 `"am"` 和 `"force-stop"` 作为两个独立参数，注释 `# D1: 防御性拆分 argv` 确认修复来源于原报告。
- 修复后的命令 `adb shell am force-stop <package>` 是正确的 ADB 调用方式。

---

### [AUDIT-2] 批次 8 NAV-01 — 确认准确

**审计范围**：批次 8 `0200_nav.md` NAV-01 — `entity_db.py:129-133` `find_by_name("")` 正则空串匹配全部实体

**当前代码**：

```python
def find_by_name(self, name: str, exact: bool = False, limit: int = 50) -> List[Entity]:
    self._ensure_loaded()
    if exact:
        return list(self._by_name.get(name, []))[:limit]
    pattern = re.compile(re.escape(name), re.IGNORECASE)
    ...
```

**验证结论**：**准确无误**。

- `re.escape("")` 返回空串 `""`。
- `re.compile("", re.IGNORECASE).search(key)` 对任意字符串在位置 0 即匹配。
- `find_by_name("")` 返回 `_by_name` 中全部实体（截断至 limit=50）。
- 原报告的修改建议（入口校验非空）仍然有效。

---

## §3 发现统计

| 类别 | 条目 | 严重度 | 状态 |
|------|------|--------|------|
| 新发现 | GUI-05（托盘退出失效） | Low | 历史未覆盖 |
| 新发现 | GUI-04（默认页硬编码中文） | Low | 历史未覆盖 |
| 新发现 | SEC-03（device_settings_page 非原子写入） | Low | 历史未覆盖 |
| 新发现 | GUI-07（LLM 超时后进程泄漏） | Low | 历史未覆盖 |
| 新发现 | I18N-04（选项 locale 硬编码中文） | Low | 历史未覆盖 |
| 新发现 | I18N-05（logger.py 绕过 get_project_root） | Info | 历史未覆盖 |
| 新发现 | SEC-04（Script.save 非原子写入） | Info | 历史未覆盖 |
| 新发现 | REC-02（recorder.py 路径错误，同 GUI-03） | Info | 历史未覆盖 |
| 新发现 | GUI-06（PRTS 页面自动启动 LLM） | Info | 历史未覆盖 |
| 审计验证 | AUDIT-1（批次 7 D1 已修复，原报告准确） | — | 确认无误 |
| 审计验证 | AUDIT-2（批次 8 NAV-01 确认准确） | — | 确认无误 |
| **合计** | **9 新 + 2 审计** | **5L + 4I** | — |

---

## §4 跨批次一致性验证

- **批次 74 GUI-02/03 + QS-01** → 与本批独立文件/模块，不冲突。REC-02 与 GUI-03 为同模式不同文件，已标注关联。
- **批次 73 LLM-01/D-06/D-07/LLM-02** → 与本批独立文件/模块，不冲突
- **批次 71 MAA71-01/02/03** → 与本批独立文件/模块，不冲突
- **批次 8 NAV-01** → AUDIT-2 验证，不重复提交
- **批次 7 D1** → AUDIT-1 验证，已修复，不重复提交
- **批次 28 D02** → `_is_stuck` 阈值已修复（max(2.0, target_dist * 0.05)），本批未重复报告
- **批次 28 D04** → `_try_recover` 不验证 `_reconnect()` 结果，已修复（`vlm_walk_navigator.py` 当前使用 `_locator.locate()` 直接调用，无 `_try_recover` 方法）

---

## §5 验证方法

- 全部发现基于对 `main_window.py`、`tray_icon.py`、`prts_full_intelligence_page.py`、`recorder.py`、`device_settings_page.py`、`maaend_control_page.py`、`logger.py`、`models.py`、`istina.py` 的**逐行静态阅读**与调用链推演。
- **未执行任何测试**，未修改任何业务代码。
- 重复检测：交叉核对 35+ 份历史报告确认本批 9 项新发现无重复。NAV-01（批次 8）和 D1（批次 7）已在审计部分验证，未作为新发现重复提交。
- 审计部分基于对 `recovery.py`、`entity_db.py` 的逐行复核。
- 本批严格遵循"避免重复提交历史已覆盖问题"原则。
