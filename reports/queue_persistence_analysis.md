# 队列未能持久化的原因分析报告

> 分析时间：2026-07-08
> 分析范围：`src/gui/pyqt6/queue_state.py`、`src/gui/pyqt6/pages/maaend_control_page.py`、`src/gui/pyqt6/main_window.py`
> 约束：只读调查，未修改任何源码。

---

## 一、当前持久化机制

`QueueState` 类实现了 `persist()` 和 `load()`，将队列与选项写入 `config/maaend_task_state.json`。

### 1.1 已持久化的内容

| 字段 | 类型 | 说明 |
|------|------|------|
| `selected_task` | `str \| None` | 当前选中的任务名 |
| `selected_preset` | `str \| None` | 当前选中的预设名 |
| `queue_items` | `list[dict]` | 队列条目（name / display_name / type / options） |
| `task_options` | `dict[str, dict]` | 每个任务最新编辑过的选项快照 |

### 1.2 `persist()` 被调用的 8 个入口

| 方法 | 触发时机 | 是否同时保存 selected_* |
|------|----------|------------------------|
| `_add_to_queue()` | 添加任务/预设到队列 | ❌ |
| `_add_task_to_queue()` | 添加任务到队列 | ❌ |
| `_queue_move_up()` | 队列上移 | ❌ |
| `_queue_move_down()` | 队列下移 | ❌ |
| `_queue_clear()` | 清空队列 | ❌ |
| `_import_queue()` | 导入队列文件 | ❌ |
| `_save_options()` | 选项 widget 变化 | ✅（走 `_persist_state`） |
| `_apply_preset_to_queue()` | 应用预设到队列 | ✅（走 `_persist_state`） |

---

## 二、根因分析

### 根因 1：主窗口关闭时不持久化队列状态（P0）

**位置**：`src/gui/pyqt6/main_window.py:109-117`

```python
def closeEvent(self, event: QCloseEvent) -> None:
    settings = QSettings("ArkStudio", "IstinaEndfieldAssistant")
    settings.setValue("mainWindow/geometry", self.saveGeometry())
    if self._tray_icon is not None and self._tray_icon.is_available():
        event.ignore()  # ← 托盘最小化，完全不持久化
        self.hide()
    else:
        super().closeEvent(event)  # ← 真正退出，也无队列持久化
```

**影响**：
- 用户通过托盘最小化后直接退出程序，内存中最后编辑的选项/队列不会写入磁盘。
- 下次启动时，队列恢复到**上次显式触发 `_save_options` 或 `_apply_preset_to_queue`** 时的状态，而非关闭时的最新状态。

---

### 根因 2：`QueueState.persist()` 静默吞掉所有异常（P0）

**位置**：`src/gui/pyqt6/queue_state.py:86-97`

```python
def persist(self) -> None:
    try:
        state = {...}
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass  # ← 静默忽略所有异常
```

**影响**：
- 磁盘满、文件被锁定、权限不足、目录创建失败等情况都会导致写入失败，但调用方完全无感知。
- 内存中的队列与磁盘文件产生漂移：UI 显示的队列与下次启动加载的队列不一致，用户会认为"保存了但重启后丢失"。

---

### 根因 3：`selected_task` / `selected_preset` 未被可靠持久化（P1）

**位置**：`src/gui/pyqt6/pages/maaend_control_page.py:1094-1101`

```python
def _persist_state(self) -> None:
    try:
        self._queue_state.set_state_path(self._state_path)
        self._queue_state.set_selected_task(self._selected_task)     # ← 仅在这里设置
        self._queue_state.set_selected_preset(self._selected_preset) # ← 仅在这里设置
        self._queue_state.persist()
    except Exception as e:
        ...
```

`_persist_state()` 仅被两处调用：
- `_save_options()` — 修改选项 widget 时
- `_apply_preset_to_queue()` — 应用预设时

**不被调用的场景**：
- 用户在任务列表中选择了一个任务，但未修改任何选项 → `selected_task` 不会更新
- 用户在预设列表中选择了一个预设，但未点击"应用预设" → `selected_preset` 不会更新
- 用户直接关闭程序 → 不会触发任何持久化

**影响**：应用程序重启后，任务/预设选中态恢复到上次 `_save_options` 或 `_apply_preset_to_queue` 时的值。

---

### 根因 4：`_save_options` 与 `_apply_saved_option_values` 之间的信号竞争（P2）

**位置**：`src/gui/pyqt6/pages/maaend_control_page.py:841-846`

```python
def _build_option_editor(self):
    ...
    self._option_form.setEnabled(False)
    self._apply_saved_option_values(self._selected_task)  # 设置 widget 值
    self._option_form.setEnabled(True)
```

`_apply_saved_option_values` 内部使用 `blockSignals(True/False)` 防止信号，但存在边界情况：
- 如果 `blockSignals` 在嵌套 widget 上未正确生效，可能触发 `_save_options` 并用默认值覆盖已保存的选项。
- 如果 `_selected_task` 在构建与填充之间被外部修改，可能应用错误的选项值。

**影响**：特定操作序列下，已保存的选项可能被意外覆盖为默认值。

---

## 三、证据

### 3.1 持久化文件当前状态

`config/maaend_task_state.json` 当前内容：

```json
{
  "selected_task": "TaskA",
  "selected_preset": "DailyFull",
  "queue_items": [],
  "task_options": {
    "VisitFriends": { ... },
    "DijiangRewards": { ... },
    ...  // 16 个任务有选项数据
  }
}
```

- `queue_items` 为空数组 — 说明队列在最近一次操作中被清空或从未被添加到队列。
- `task_options` 有大量数据 — 说明选项保存机制本身是有效的。
- `selected_preset` 为 `DailyFull` 但 `queue_items` 为空 — 两者状态不一致，暗示预设被选中但队列被清空后未同步 `selected_preset`。

### 3.2 最近提交 `0447387` 的影响

该提交（"去除全部手动保存设置，改为修改后立即自动保存"）做了以下修改：
1. 删除了"保存设置"按钮和"应用队列设置"按钮
2. 将选项 widget 的 `toggled`、`currentIndexChanged`、`textChanged` 信号连接到 `_save_options`
3. 在 `_add_to_queue` / `_add_task_to_queue` / `_apply_preset_to_queue` 中新增 `self._queue_state.save_options(name, options)`

**正面影响**：选项修改后立即保存，减少了用户忘记手动保存导致的丢失。

**遗留问题**：
- 没有新增 `closeEvent` 持久化 — 关闭窗口时的最后状态仍可能丢失
- `persist()` 的静默异常处理未改进 — 自动保存失败时用户无感知
- `_persist_state()` 仅在选项变化和应用预设时调用 — `selected_*` 的更新仍然不完整

---

## 四、修改方案与影响面分析

### P0-1：`MainWindow.closeEvent` 增加持久化

**修改位置**：`src/gui/pyqt6/main_window.py:109-117`

```python
def closeEvent(self, event: QCloseEvent) -> None:
    settings = QSettings("ArkStudio", "IstinaEndfieldAssistant")
    settings.setValue("mainWindow/geometry", self.saveGeometry())
    if self._tray_icon is not None and self._tray_icon.is_available():
        event.ignore()
        self.hide()
        self._tray_icon.show_message(...)
    else:
        # 新增：在真正退出前持久化队列状态
        maaend_page = getattr(self, "_maaend_page", None)
        if maaend_page is not None:
            maaend_page._persist_state()
        super().closeEvent(event)
```

**影响函数**：
- `MainWindow.closeEvent` — 新增持久化调用
- `MaaEndControlPage._persist_state` — 写入 selected_* + persist
- `QueueState.persist` — 写入磁盘

**可能造成的非期待变化**：
1. **磁盘写入时机**：关闭窗口时额外写入一次，若用户频繁关闭/打开，增加磁盘 I/O（JSON 极小，可忽略）。
2. **空值写入风险**：若 `MaaEndControlPage` 尚未初始化完成（极端启动失败场景），`_persist_state` 可能写入空 `selected_task` / `selected_preset`。建议增加 `hasattr(self, "_maaend_page")` 与 `_queue_state` 存在性检查。
3. **托盘最小化场景**：`event.ignore()` 路径不触发持久化，与之前行为一致，无副作用。
4. **退出阻塞**：`persist()` 是同步写入，若磁盘 I/O 极慢，可能轻微延长退出时间（JSON 通常 < 10ms）。

---

### P0-2：`QueueState.persist()` 不再静默吞异常

**修改位置**：`src/gui/pyqt6/queue_state.py:86-97`

```python
def persist(self) -> bool:
    try:
        state = {
            "selected_task": self._selected_task,
            "selected_preset": self._selected_preset,
            "queue_items": self._queue_items,
            "task_options": self._saved_task_options,
        }
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as exc:
        # 记录 warning 而非静默忽略
        import logging
        logging.getLogger(__name__).warning("QueueState persist failed: %s", exc)
        return False
```

**影响函数**：
- 所有调用 `persist()` 的 8 个入口（`_add_to_queue`、`_save_options` 等）
- `_persist_state()` — 当前不检查返回值

**可能造成的非期待变化**：
1. **异常上抛风险**：若调用方改为检查返回值并在 `False` 时提示用户，可能打断用户操作流程。建议保持 `persist()` 返回 `bool`，由调用方决定是否提示。
2. **日志噪声**：若磁盘偶尔抖动，可能产生 warning 日志，但这是期望行为，便于排查。
3. **兼容性**：现有调用方未检查返回值，改为返回 `bool` 不会破坏兼容性。

---

### P1-1：`selected_task/preset` 在选择列表项时持久化

**修改位置**：`src/gui/pyqt6/pages/maaend_control_page.py:614-622`

当前选择回调：

```python
def _on_task_selected(self, item: QListWidgetItem) -> None:
    self._selected_task = item.data(Qt.ItemDataRole.UserRole)
    self._build_option_editor()

def _on_preset_selected(self, item: QListWidgetItem) -> None:
    self._selected_preset = item.data(Qt.ItemDataRole.UserRole)
```

**修改后**：

```python
def _on_task_selected(self, item: QListWidgetItem) -> None:
    self._selected_task = item.data(Qt.ItemDataRole.UserRole)
    self._build_option_editor()
    self._persist_state()  # 新增：选中任务后立即持久化

def _on_preset_selected(self, item: QListWidgetItem) -> None:
    self._selected_preset = item.data(Qt.ItemDataRole.UserRole)
    self._persist_state()  # 新增：选中预设后立即持久化
```

**影响函数**：
- `_on_task_selected` — 新增 `_persist_state()` 调用
- `_on_preset_selected` — 新增 `_persist_state()` 调用
- `_persist_state` — 写入 selected_* + persist

**可能造成的非期待变化**：
1. **频繁磁盘写入**：每次点击任务/预设都会触发一次 `persist()`。JSON 文件通常 < 5KB，写入耗时 < 10ms，可忽略。但若用户快速点击多个任务，可能产生竞争写入，最终一致性由最后写入决定（`write_text` 是原子操作）。
2. **选项未修改时也写入**：即使用户只是切换选中态而未修改选项，也会触发一次磁盘写入。这是期望行为，确保选中态不丢失。
3. **`_build_option_editor` 依赖 `_selected_task`**：在 `_on_task_selected` 中先设置 `_selected_task` 再调用 `_build_option_editor()`，若 `_persist_state()` 插入在中间，可能持久化旧值。正确顺序是：设置选中态 → 构建编辑器 → 持久化。

---

### P2-1：`_build_option_editor` 信号竞争防护

**修改位置**：`src/gui/pyqt6/pages/maaend_control_page.py:841-846`

当前代码：

```python
def _build_option_editor(self):
    ...
    self._option_form.setEnabled(False)
    self._apply_saved_option_values(self._selected_task)
    self._option_form.setEnabled(True)
```

`_apply_saved_option_values` 内部已使用 `blockSignals(True/False)`，但建议在入口处统一 block：

```python
def _build_option_editor(self):
    ...
    self._option_form.setEnabled(False)
    self._option_form.blockSignals(True)  # 新增：统一阻断信号
    self._apply_saved_option_values(self._selected_task)
    self._option_form.blockSignals(False) # 恢复
    self._option_form.setEnabled(True)
```

**影响函数**：
- `_build_option_editor` — 新增 `blockSignals` 保护
- `_apply_saved_option_values` — 内部仍有 `blockSignals`，双重保护无副作用
- `_save_options` — 可能被意外触发的信号现在被阻断

**可能造成的非期待变化**：
1. **信号阻断过度**：若 `_option_form` 包含需要在构建期间响应的信号（当前无此场景），会被临时阻断。`blockSignals` 在构建完成后立即恢复，影响范围仅限于构建过程。
2. **嵌套 widget 信号**：`blockSignals` 仅作用于 `_option_form` 本身，不递归作用于子 widget。但 `_apply_saved_option_values` 内部已对每个子 widget 单独 `blockSignals`，双重保护下风险极低。

---

## 五、修复优先级与建议

| 优先级 | 根因 | 修复方案 | 风险 | 建议 |
|--------|------|----------|------|------|
| P0 | `closeEvent` 不持久化 | 退出前调用 `_persist_state()` | 低 | 立即修复，防止关闭时丢失 |
| P0 | `persist()` 静默吞异常 | 改为返回 `bool` + warning 日志 | 低 | 立即修复，提升可观测性 |
| P1 | `selected_*` 更新不完整 | 选择列表项时调用 `_persist_state()` | 低 | 短期修复，确保选中态持久化 |
| P2 | 信号竞争 | `_build_option_editor` 入口 `blockSignals` | 极低 | 后续清理，防御性编程 |

---

## 六、验证建议

1. **关闭窗口验证**：修改队列/选项后直接关闭程序，重启后检查 `config/maaend_task_state.json` 是否包含最新状态。
2. **异常注入验证**：将 `maaend_task_state.json` 设为只读，触发 `persist()`，确认 warning 日志输出且不崩溃。
3. **选中态验证**：选择任务/预设后直接关闭，重启后检查 `selected_task` / `selected_preset` 是否恢复。
4. **信号竞争验证**：快速切换任务/预设，确认 `task_options` 未被覆盖为默认值。

---

## 七、结论

队列未能持久化的**直接原因**是应用程序生命周期中没有在关闭/退出时强制持久化队列状态。用户依赖"修改后自动保存"机制，但该机制只覆盖了选项 widget 变化和队列操作，**没有覆盖窗口关闭事件**。

**次要原因**是 `QueueState.persist()` 静默吞掉所有异常，导致即使触发了持久化，也可能因为环境问题（磁盘满、权限不足、文件锁定）写入失败，而用户完全不知情。

这两个原因共同导致了"队列看起来保存了，但重启后丢失"的现象。
