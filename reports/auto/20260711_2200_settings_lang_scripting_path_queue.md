# 批次 74：设置页语言切换不刷新 UI / 脚本录制路径绕过 get_project_root / 队列状态空值语义 + 历史报告审计

> **生成时间**: 2026-07-11 22:00
> **审查范围**: `src/gui/pyqt6/pages/settings_page.py` (236 行), `src/gui/pyqt6/scripting/scripting_page.py` (271 行), `src/gui/pyqt6/queue_state.py` (169 行)
> **审计范围**: 批次 73（`20260711_2145_llm_zombie_daemon_json.md`）、批次 71（`20260711_2100_qtlog_widget_parent_audit.md`）
> **方法**: 静态代码逻辑分析 + 调用链推演
> **发现总计**: 3 新发现 + 2 审计验证
> **严重度分布**: 0 High / 0 Medium / 1 Low / 1 Low / 1 Info

---

## 项目边界回顾

- IEA 是《明日方舟：终末地》的 MaaEnd/MaaFramework 自动化助手。本仓库为**非第三方**源码，`MaaEnd/` 与 `3rd-part/` 不在审查范围。
- 审查仅限本仓库 Python 源码；历史累计 260+ 条发现，本批严格避免重复提交。
- 本批聚焦设置页（`settings_page.py`）、脚本录制页（`scripting_page.py`）、队列状态管理（`queue_state.py`）。

---

## §1 新发现

### [GUI-02 Low] `settings_page.py:136-149` — `_on_language_changed` 切换语言后不刷新设置页自身 UI

```python
# settings_page.py:136-149
def _on_language_changed(self, index: int) -> None:
    new_locale = self._language_combo.currentData()
    if not new_locale:
        return
    locale.set_locale(new_locale)
    main_window = self.window()
    if isinstance(main_window, QMainWindow):
        main_window.setWindowTitle(locale.tr("app_title", "IstinaEndfieldAssistant Sight"))
        main_window.statusBar().showMessage(locale.tr("status_ready", "Ready"), 2000)
    QMessageBox.information(
        self,
        locale.tr("language_changed", "Language changed"),
        locale.tr("restart_for_changes", "Some changes will take effect after restart."),
    )
```

**根因分析**：`_on_language_changed` 调用 `locale.set_locale(new_locale)` 切换语言后，仅更新了主窗口标题和状态栏，并弹出一个提示框。但**设置页自身的所有可翻译 UI 元素**——`QGroupBox` 标题（Language、Preview、LLM Parameters）、`QPushButton` 文本（Reload）、`QLabel` 文本（Preview Interval 等 form label）——均保持切换前的语言。

**调用链推演**：

```
用户: 在设置页将语言从中文切换到英文
  │
  ├── _on_language_changed(index)
  ├── locale.set_locale("en")           ← 全局语言切换成功
  ├── main_window.setWindowTitle(...)   ← 主窗口标题刷新 ✓
  ├── statusBar.showMessage(...)        ← 状态栏刷新 ✓
  ├── QMessageBox.information(...)      ← 弹窗使用新语言 ✓
  │
  ├── "语言" group box                 ← 仍显示中文 ✗
  ├── "预览" group box                 ← 仍显示中文 ✗
  ├── "LLM 参数" group box             ← 仍显示中文 ✗
  ├── "重新加载" button                 ← 仍显示中文 ✗
  └── "预览间隔" form label             ← 仍显示中文 ✗
```

**问题**：
1. **半刷新**：语言切换后，设置页标题 (HeroHeader) 在 `_setup_ui` 时通过 `locale.tr()` 获取，切换后不再自动更新。其他页面的标题（如 MaaEnd 控制页、设备页）同样在构造时固化，但设置页是用户主动切换语言的页面，其 UI 不刷新体验最差。
2. **误导性提示**：弹窗提示"部分更改需重启后生效"，暗示所有 UI 文本需要重启，实际上主窗口标题和状态栏已经实时生效，造成用户困惑。
3. **与 `_setup_ui` 的对比**：`_setup_ui` (line 55-134) 中所有 UI 文本通过 `locale.tr()` 在构造时固定。切换语言后没有机制触发重建或更新。

**影响面**：
- **UX 缺陷**：用户在设置页切换语言后，看到的是中英文混合界面——弹窗是英文，但所有设置项标题仍是中文。需关闭设置页再打开（或重启）才能看到完整新语言。
- **频率**：用户切换语言通常只操作一次，但切换后的混合语言状态影响第一印象。

**建议**：

方案 1（刷新 UI 文本）：在 `_on_language_changed` 末尾调用 `_retranslate_ui()`，该方法更新所有可翻译控件的文本：

```python
def _on_language_changed(self, index: int) -> None:
    ...
    locale.set_locale(new_locale)
    self._retranslate_ui()  # 刷新设置页所有 UI 文本
    ...

def _retranslate_ui(self) -> None:
    self._language_card.setTitle(locale.tr("settings_language", "Language"))
    self._preview_card.setTitle(locale.tr("settings_preview", "Preview"))
    self._llm_card.setTitle(locale.tr("settings_llm", "LLM Parameters"))
    self._reload_btn.setText(locale.tr("btn_reload", "Reload"))
    # ... 其他控件
```

方案 2（最小）：至少更新 group box 标题和 button 文本——这些是用户最直观感知的元素。

---

### [GUI-03 Info] `scripting_page.py:39` — `_RECORDINGS_DIR` 使用 4 级 parent 链绕过 `get_project_root()`

```python
# scripting_page.py:39
_RECORDINGS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "recorded"
```

**根因分析**：与批次 71 MAA71-01 同一模式——使用 `parent` 链推断项目根目录而非调用 `get_project_root()`。

```
__file__ = src/gui/pyqt6/scripting/scripting_page.py
parent      → src/gui/pyqt6/scripting/
parent.parent → src/gui/pyqt6/
parent.parent.parent → src/gui/
parent.parent.parent.parent → src/
```

4 级 `parent` 链到的是 `src/`，不是项目根。然后拼接 `"scripts" / "recorded"` 得到 `src/scripts/recorded`。

但项目根下的 `scripts/recorded/` 应该在项目根目录。正确路径应该是：
```
get_project_root() / "scripts" / "recorded"
```

而当前代码得到的是 `src/scripts/recorded`——**路径错误**！

**验证**：`Path(__file__).resolve()` 返回 `.../src/gui/pyqt6/scripting/scripting_page.py`。4 级 parent 链到 `.../src/`。拼接 `"scripts/recorded"` 得到 `.../src/scripts/recorded`。

但项目实际的 `scripts/recorded/` 目录在项目根下（`scripts/recorded/`），不在 `src/scripts/recorded/`。

**影响面**：
- **功能影响**：脚本录制功能将脚本保存到 `src/scripts/recorded/`（如果存在）而非项目根下的 `scripts/recorded/`。如果 `src/scripts/recorded/` 不存在，`_refresh_script_list` 中的 `mkdir(parents=True, exist_ok=True)` 会创建它——但这是一个错误的位置。
- **与批次 71 MAA71-01 对比**：MAA71-01 的 5 级 parent 链正确到达项目根（5 级到 `.../`）。本处的 4 级 parent 链只到 `src/`，少了一层。

**建议**：

```python
from core.foundation.paths import get_project_root
_RECORDINGS_DIR = get_project_root() / "scripts" / "recorded"
```

---

### [QS-01 Low] `queue_state.py:79-83` — `load()` 用 `or` 运算符处理 `null` 值，静默保留旧状态

```python
# queue_state.py:79-83
self._selected_task = state.get("selected_task") or self._selected_task
self._selected_preset = state.get("selected_preset") or self._selected_preset
```

**根因分析**：`state.get("selected_task")` 在 JSON 值为 `null` 时返回 `None`。`None or self._selected_task` → Python 的 `or` 返回右操作数 `self._selected_task`——即**保留当前内存中的值**，而非设置为 `None`。

**调用链推演**：

```
场景 1：用户清空选中任务，保存状态
  persist() → {"selected_task": null, ...}

  下次 load():
    state.get("selected_task") → None
    None or self._selected_task → self._selected_task  ← 恢复旧值！
    （应为 None，但保留了上次的 "Daily"）

场景 2：JSON 中 selected_task 为 ""（空字符串）
  state.get("selected_task") → ""
  "" or self._selected_task → self._selected_task  ← 同样保留旧值
```

**问题**：
1. **JSON null 语义被忽略**：如果用户在 GUI 中清空了选中任务，`persist()` 写入 `null`。下次 `load()` 时，`null` 被 `or` 运算符当作"缺失"处理，恢复旧值。状态持久化失效。
2. **空字符串同理**：`"" or self._selected_task` 同样恢复旧值。
3. **与 `_saved_task_options` 的处理不一致**：同一文件的 `load_options()` (line 138-143) 正确处理了缺失/空值：

```python
def load_options(self, task_name: str) -> Dict[str, Any]:
    with self._lock:
        saved = self._saved_task_options.get(task_name)
        if isinstance(saved, dict):
            return dict(saved)
        return {}  # 返回空 dict，不保留旧值
```

`load()` 和 `load_options()` 对"缺失值"的处理策略不一致。

**影响面**：
- **低**：影响"清空选中任务"的场景。用户清空后重启，任务重新出现。但队列项 (`queue_items`) 的加载不受影响（lines 84-98 正确使用了 `isinstance` 检查）。
- **数据一致性**：`persist()` → `load()` 的往返不保证值不变（round-trip 不安全）。

**建议**：

```python
self._selected_task = state.get("selected_task", None)  # 不 fallback
self._selected_preset = state.get("selected_preset", None)
```

或更明确：

```python
self._selected_task = state.get("selected_task")
if self._selected_task is None:
    self._selected_task = None  # 显式保留 None（JSON null）
self._selected_preset = state.get("selected_preset")
if self._selected_preset is None:
    self._selected_preset = None
```

---

## §2 历史报告审计

### [AUDIT-1] 批次 73 `20260711_2145_llm_zombie_daemon_json.md` — 确认准确

**审计范围**：LLM-01（`_try_start` 僵尸进程）、D-06（`_call` json.loads 掩埋）、D-07（`_handle_client` 静默丢弃）、LLM-02（双 `[MAIN]` 标签）。

**验证结论**：**准确无误**。

验证要点：
- **LLM-01**：`llm/runtime.py:374` 的 `return False` 在 60 秒超时后不终止子进程。审计确认 `_kill_tracked_process` 方法存在但未在超时路径调用。论断准确。
- **D-06**：`android_runtime.py:641` 的 `except Exception` 捕获 `JSONDecodeError` 并记录"连接失败"。审计确认连接实际成功，是响应格式错误。论断准确。
- **D-07**：`android_runtime.py:478` 的 `except JSONDecodeError: continue` 静默丢弃请求。审计确认客户端 30 秒超时。论断准确。
- **LLM-02**：`client.py:97-98` 的 `self._logger.error("[%s] ...", LogCategory.MAIN, ...)` 产生双 `[MAIN]` 标签。审计确认 `ProjectLogger._format` 自动添加分类前缀。论断准确。

---

### [AUDIT-2] 批次 71 `20260711_2100_qtlog_widget_parent_audit.md` — 确认准确

**审计范围**：MAA71-01（5 级 parent 链）、MAA71-02（`_INSTALLED` 非原子检查）、MAA71-03（`BLUE_STYLE` 重复定义）。

**验证结论**：**准确无误**。

验证要点：
- **MAA71-01**：`maaend_control_page.py:174` 的 5 级 parent 链确为项目最深硬编码路径。审计确认 `get_project_root()` 使用 4 级 parent（从 `paths.py` 推断）。论断准确。
- **MAA71-02**：`qt_log_filter.py:55-57` 的 `_INSTALLED` 标志非原子检查。审计确认无 `threading.Lock` 保护。论断准确。
- **MAA71-03**：`widget_styles.py:49-52` 和 57-60 的 `BLUE_STYLE` 重复定义。审计确认第二处覆盖第一处。论断准确。

本批 GUI-02/03 + QS-01 与批次 73/71 独立，不重叠。

---

## §3 发现统计

| 类别 | 条目 | 严重度 | 状态 |
|------|------|--------|------|
| 新发现 | GUI-02（`_on_language_changed` 不刷新设置页 UI） | Low | 历史未覆盖 |
| 新发现 | GUI-03（`_RECORDINGS_DIR` 4 级 parent 链路径错误） | Info | 历史未覆盖 |
| 新发现 | QS-01（`load()` `or` 运算符保留旧状态当 JSON 为 null） | Low | 历史未覆盖 |
| 审计验证 | AUDIT-1（批次 73 LLM-01/D-06/D-07/LLM-02 确认准确） | — | 确认无误 |
| 审计验证 | AUDIT-2（批次 71 MAA71-01/02/03 确认准确） | — | 确认无误 |
| **合计** | **3 新 + 2 审计** | **2L + 1I** | — |

---

## §4 跨批次一致性验证

- **批次 73 LLM-01/D-06/D-07/LLM-02** → 与本批独立文件/模块，不冲突
- **批次 71 MAA71-01/02/03** → 与本批独立文件/模块，不冲突
- **批次 69 I18N-01/02/03** → 本批 GUI-02 涉及语言切换 UX，与批次 69 的 i18n 加载问题不同维度，互补
- **批次 7 设备层审查** → 与本批 GUI/状态管理独立，不冲突

---

## §5 验证方法

- 全部发现基于对 `settings_page.py`、`scripting_page.py`、`queue_state.py` 的**逐行静态阅读**与调用链推演。
- **未执行任何测试**，未修改任何业务代码。
- 重复检测：交叉核对 30 份历史报告确认 GUI-02/03 和 QS-01 为全新发现。
- 审计部分基于对 `llm/runtime.py`、`android_runtime.py`、`widget_styles.py`、`qt_log_filter.py` 的逐行复核。
- 本批严格遵循"避免重复提交历史已覆盖问题"原则。
