# 审计批次 79 — 选项编辑器 falsy 处理 / 队列导出非原子写入 + 审计批次 78

**生成时间**: 2026-07-11 23:45+
**覆盖文件**: `maaend_control_page.py`, `player.py`, `scripting_page.py`, `color_backend.py`
**审计方法**: 静态代码逻辑分析，无测试执行

---

## 新增发现（2 项）

### MAEEND-01 — `_get_current_case` 与 `_collect_option_recursive` 对 select 控件 `currentData()` 使用 falsy 判断，`data=0` 时回退到 `currentText()` 导致 case 名称匹配错误

**等级**: BUG / 中
**位置**: `maaend_control_page.py:1168-1176` (`_get_current_case`), `maaend_control_page.py:1360-1362` (`_collect_option_recursive`)

**问题代码**:

```python
# _get_current_case (line 1168-1176)
def _get_current_case(self, name: str, opt_def: Dict[str, Any], widget: QWidget) -> Optional[str]:
    opt_type = opt_def.get("type", "switch")
    if opt_type == "switch":
        return widget.value()  # "Yes" or "No"
    if opt_type == "select":
        data = widget.currentData()           # ← 返回 QVariant，可能为 int(0)
        return str(data) if data else widget.currentText()  # ← int(0) 为 falsy！
    return None

# _collect_option_recursive (line 1360-1362)
elif opt_type == "select":
    data = widget.currentData()
    options[name] = data if data else widget.currentText()  # ← 同样 bug
```

**根因分析**:

`QComboBox.currentData()` 返回 `QVariant`。当 `addItem(label, case.get("name"))` 中 `case["name"]` 为整型 `0` 时，`currentData()` 返回 `QVariant(0)`，在 Python 中 `int(0)` 为 **falsy**。`if data` 判为 `False`，两处代码均回退到 `widget.currentText()`（显示文本）。

**子问题 A — `_get_current_case` 子选项匹配失败** (line 1174):

`_get_current_case` 用于 `_refresh_sub_options` 中查找当前选中 case 对应的子选项定义。当 `data=0` 时，方法返回 `currentText()`（如 "Disabled"），而 `_refresh_sub_options` 在 `cases` 列表中查找 `case["name"] == "Disabled"`，找不到匹配项——`case_def` 为 `None`，子选项面板被隐藏。

**后果**:
- 用户选中 case 后，对应的子选项（如额外参数）不显示
- 用户无法编辑子选项，以为该 case 没有配置项
- 无任何错误提示，纯静默失败

**子问题 B — `_collect_option_recursive` 管道覆盖选项被错误值污染** (line 1361):

`_collect_option_recursive` 用于收集选项值并传递给 `_apply_option` 生成管道覆盖。当 `data=0` 时，`options[name]` 被设为 `currentText()` 而非 `0`。后续 `_apply_option` 中 `case_name = str(value)` 将得到 `"Disabled"` 而非 `"0"`——case 匹配失败，管道覆盖选项静默丢失。

**后果**:
- 任务执行时管道覆盖选项不生效
- 用户看到选项已设置，但实际执行时未应用
- 无任何错误日志，调试困难

**修复建议**:

两处均改为 `data is not None` 精确判断：

```python
# _get_current_case
data = widget.currentData()
return str(data) if data is not None else widget.currentText()

# _collect_option_recursive
data = widget.currentData()
options[name] = data if data is not None else widget.currentText()
```

**触发条件**: 仅当 MaaEnd 任务定义的 select 类型选项的 case `name` 为整型 `0`（或任何 falsy 值如 `""`、`0.0`）且 display label 与 name 不同时触发。当前任务定义中尚未发现此模式，但 MaaEnd 框架本身允许 case name 为任意值，属于防御性修复。

---

### MAEEND-02 — `_export_queue` 使用非原子 `Path.write_text` 写入导出文件

**等级**: 代码质量 / 低
**位置**: `maaend_control_page.py:872`

```python
# _export_queue (line 866-876)
try:
    data = {
        "version": 1,
        "queue_items": self._queue_state.queue_items,
        "task_options": self._queue_state.saved_task_options,
    }
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # ...
except Exception as exc:
    QMessageBox.warning(self, locale.tr("export_failed", "Export Failed"), str(exc))
```

**问题**: 直接使用 `Path.write_text` 写入目标文件，非原子操作。若写入过程中进程崩溃、断电或磁盘满，导出文件可能处于半写入状态（JSON 截断），后续 `_import_queue` 中的 `json.loads` 将抛出 `JSONDecodeError`。

**对比**:

| 文件 | 方法 | 原子性 |
|------|------|--------|
| `settings_page.py:196-211` | `tempfile.mkstemp` + `os.replace` | ✓ 原子 |
| `queue_state.py:122-124` | `.with_suffix(".tmp")` + `os.replace` | ✓ 原子 |
| `maaend_control_page.py:872` | `Path.write_text` | ✗ 非原子 |

**影响面**: 低——导出文件由用户通过 `QFileDialog` 选择路径，非项目内部配置。但写入中断导致文件损坏时，用户重新导入会看到 `JSONDecodeError` 的原始错误信息，体验不佳。

**建议**: 使用 `tempfile.mkstemp` + `os.replace` 原子写入：

```python
import tempfile
fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=Path(path).parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)
finally:
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
```

---

## 审计结论（批次 78）

| 批次 | 审计对象 | 结论 |
|------|---------|------|
| 批次 78 | GUI78-01 (`playback_finished` / `playback_stopped` 信号混淆) | **结论正确**。`player.py:113-138` 中 `_execute_action` 末尾无条件调用 `_schedule_next` (line 138)。当用户在 `_execute_action` 执行期间调用 `stop()`，`_stopped` 被设为 `True` 后 `_schedule_next` 检测到标志并调用 `_on_finished()` 发射 `playback_finished`。与 `stop()` 中已发射的 `playback_stopped` (line 87) 形成信号双发——`ScriptingPage._on_playback_finished` 和 `_on_playback_stopped` 被同时调用，双重恢复按钮状态。 |
| 批次 78 | GUI78-02 (队列执行中冗余解析内联任务名) | **结论正确**。`maaend_control_page.py:923` 的 `_normalize_runtime_entry` 已调用 `_parse_inline_task_name` 提取 `inline_options` 并合并到 `options`。第 929 行对同一 `name` 再次调用 `_parse_inline_task_name`，提取完全相同的 `inline_options` 并重新创建 `merged_options`。第 930-931 行的 `merged_options` 覆盖了已正确合并的 `options`，语义等价但路径冗余。 |
| 批次 78 | GUI78-03 (`scripting_page.py:155` 死代码) | **结论正确**。第 155 行的 `script_name = f"script_{Path(__file__).resolve().name}"` 使用文件名生成赋值，但第 157 行立即用时间戳覆盖：`script_name = f"script_{datetime.now().strftime('%Y%m%d_%H%M%S')}"`。第 155 行赋值是死代码——其值永远不会被使用。 |
| 批次 78 | GUI78-04 (`color_backend.py` 使用标准 logging) | **结论正确**。`color_backend.py:8-16` 使用 `import logging` + `logging.getLogger(__name__)`。项目中其他所有模块均通过 `from core.foundation.logger import get_logger` 获取 logger（提供 `LogCategory` 分类和结构化日志功能）。`color_backend.py` 的日志不携带 `LogCategory` 分类标签，与项目日志系统格式不一致。 |

**批次 78 全部 4 项结论经本批次逐项源码复核确认准确，无需修正。**

---

## 风险摘要

| 级别 | 数量 | 涉及项 |
|------|------|--------|
| BUG（中） | 1 | MAEEND-01 (select 控件 falsy 0 导致子选项/管道覆盖匹配错误) |
| 代码质量（低） | 1 | MAEEND-02 (导出文件非原子写入) |

**无新发现高风险项。**

本轮审计聚焦 `maaend_control_page.py` 的选项编辑器（子选项渲染、值收集）和队列导入/导出流程。发现 `_get_current_case` 和 `_collect_option_recursive` 两处对 `QComboBox.currentData()` 的 falsy 判断存在同一根因缺陷（`int(0)` 被判为 `False` 回退到 `currentText()`），分别影响子选项 UI 显示和管道覆盖选项正确性。`_export_queue` 的非原子写入与项目内其他配置持久化路径不一致。批次 78 的 4 项结论均经源码逐行复核确认准确。

---

*批次 79 报告 | 仅分析，无文件修改*
