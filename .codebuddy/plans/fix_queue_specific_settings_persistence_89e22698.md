---
name: fix_queue_specific_settings_persistence
overview: 修复"队列任务特有（per-instance）设置"持久化失败：分离共享快照 task_options[任务名] 与每队列条目独立的 queue_items[i].options，消除重复任务间的选项串味与运行时泄漏；并补齐之前报告中未实施的 P1-1（选中即持久化 selected_*）与 P2-1（_build_option_editor 加 blockSignals）。
todos:
  - id: fix-save-options-isolation
    content: 重构 _save_options：聚焦队列条目时仅写实例 options，不污染共享 task_options 快照
    status: completed
  - id: fix-focus-flush
    content: 在 _on_queue_focus_changed 切换前 flush 前一条目并透传 queue_index
    status: completed
    dependencies:
      - fix-save-options-isolation
  - id: fix-apply-values
    content: 改造 _apply_saved_option_values 支持 queue_index，队列条目只认自身实例 options
    status: completed
    dependencies:
      - fix-save-options-isolation
      - fix-focus-flush
  - id: fix-runtime-merge
    content: 修正 _runtime_queue_runner 仅用 entry.options，移除共享快照泄漏
    status: completed
  - id: fix-add-queue
    content: 修正 _add_to_queue 任务分支不再合并共享快照，按编辑器值生成实例
    status: completed
    dependencies:
      - fix-save-options-isolation
  - id: apply-p1p2-fixes
    content: 实施 P1-1 选中即持久化与 P2-1 blockSignals 防信号竞争
    status: completed
  - id: add-per-instance-tests
    content: 在 test_queue_state 与 test_gui_maaend_control 新增 per-instance 隔离与泄漏回归测试
    status: completed
    dependencies:
      - fix-save-options-isolation
      - fix-focus-flush
      - fix-apply-values
      - fix-runtime-merge
      - fix-add-queue
      - apply-p1p2-fixes
---

## 用户需求

继续完成"队列任务特有（per-instance）设置持久化失败"的分析与修复。此前报告（2026-07-08）已确认 P0-1（closeEvent 持久化）与 P0-2（persist 返回 bool）已实施并通过测试；本次聚焦更深层的"同一任务在队列中多次出现时，各自选项应独立、持久、互不干扰"的子问题，并补齐未实施的 P1-1、P2-1。

## 产品概述

MaaEnd 控制页的队列中，每个队列条目可携带专属选项（options）。修复后，无论同一任务在队列中出现多少次，每条目的选项必须独立保存、独立加载、独立运行，不向共享快照 `task_options[name]` 串味，重启后仍能精确还原。

## 核心特性

- 选中某个队列条目并修改选项时，仅写入该条目的实例 options，不再覆盖共享 `task_options[name]` 快照。
- 切换队列条目前，自动 flush 当前条目已编辑但未落盘的选项。
- 队列条目加载选项时只认自身实例 options（必要时才回退共享默认）。
- 运行时执行队列条目只使用该条目的 options，不再合并其他实例/共享快照。
- 新增任务到队列时以当前编辑器值为准，不再继承被污染的共享快照。
- 补齐 P1-1（选择任务/预设即持久化 selected_*）与 P2-1（构建选项编辑器时 blockSignals 防信号竞争）。
- 新增 per-instance 隔离与泄漏回归测试。

## 技术栈

- 语言/框架：Python 3 + PyQt6（沿用现有 `src/gui/pyqt6` 体系，不引入新依赖）。
- 持久化：`config/maaend_task_state.json`（原子写：临时文件 + `os.replace`），已由 `QueueState` 管理。
- 测试：pytest + pytest-qt（沿用 `tests/test_queue_state.py`、`tests/gui/pyqt6/test_gui_maaend_control.py` 现有结构）。

## 实现方案

### 核心数据模型修正

当前 `QueueState` 已同时支持"共享默认"（`_saved_task_options[name]`）与"每实例"（`_queue_items[i]["options"]`），`update_queue_item_options(index, options)` 与 `get_queue_item(index)` 均可用，**`queue_state.py` 无需改动**。问题全在 `maaend_control_page.py` 的读写逻辑混淆了两者。

确立唯一原则：**队列条目的 `options` 是该实例的权威配置；`task_options[name]` 仅作为"任务默认/新建条目种子"，在任何队列实例编辑路径中都不允许被写入或回写。**

### 关键改动点（均复用现有 `QueueState` API）

1. **`_save_options`（1053）隔离写入**：通过 `self._queue_list.currentRow()` 判断是否聚焦队列条目。若聚焦且 `entry["name"] == self._selected_task`，调用 `update_queue_item_options(row, options)` 仅写实例；若不聚焦（仅任务列表选中），才 `save_options(name, options)` 写共享默认。彻底消除实例编辑污染共享快照。
2. **`_on_queue_focus_changed`（1217）切换前 flush**：新增 `self._focused_queue_index`。进入新行前，用仍显示旧条目的 `_collect_options()` 把当前编辑值写入旧实例（`update_queue_item_options`），再切换 `self._selected_task` 并重建编辑器；并把行号作为 `queue_index` 透传给 `_apply_saved_option_values`。
3. **`_apply_saved_option_values`（1086）支持 `queue_index`**：签名改为 `(task_name, queue_index=None)`。当 `queue_index is not None` 时只读取 `queue_items[queue_index]["options"]`（实例权威），不再回退共享（避免被污染值）；无实例时沿用共享默认。
4. **`_runtime_queue_runner`（794）移除共享泄漏**：删除 `saved=load_options(name); options=dict(saved); options.update(...)` 的合并，直接使用 `options = entry.get("options") or {}`（实例 options 在保存时由 `_collect_options` 全量收集，已完整），仅保留 `inline_options` 合并。
5. **`_add_to_queue`（668）任务分支去共享**：`options = self._collect_options()`（当前编辑器值），直接以该值生成新实例，不再 `load_options(name)` 合并共享快照；预设分支维持"应用即作为默认"的既有语义（可继续写共享，因预设下所有同任务实例值一致，不会串味）。
6. **P1-1**：`_on_task_selected` / `_on_preset_selected` 在设定 `self._selected_task/_selected_preset` 后调用 `self._persist_state()`。
7. **P2-1**：`_build_option_editor` 在 `_apply_saved_option_values` 前后用 `_option_form.blockSignals(True/False)` 包裹，防止重建期信号触发 `_save_options` 用默认值覆盖。

### 性能与可靠性

- `persist()` 写入 < 5KB JSON，临时文件 + `os.replace` 原子替换，开销可忽略；聚焦切换 flush 为 O(1) 内存操作。
- 不引入额外 I/O；沿用现有 `persist()` 返回 `bool` + warning 日志，便于排查写盘失败。
- 向后兼容：共享 `task_options` 仍保留用于种子与任务列表编辑器；`queue_items` 既有字段不变，旧 JSON 加载不受影响。

## 实现注意（防回归）

- `_save_options` 的 `entry["name"] == self._selected_task` 守卫保留，确保写入正确行。
- 切换条目 flush 时务必在重建编辑器"之前"完成（此时控件仍属旧条目）。
- `_apply_saved_option_values` 空 `options={}` 视为"全部默认"，允许回退共享默认，不影响新实例展示。
- 勿在 `main_window.py:108` 重复添加 closeEvent 持久化（P0-1 已实施）。

## 架构设计

```mermaid
flowchart TD
    A[选项控件变更/自动保存] --> B[_save_options]
    B -->|聚焦队列条目| C[update_queue_item_options 仅写实例]
    B -->|仅任务列表选中| D[save_options 写共享默认]
    E[_on_queue_focus_changed] -->|切换前 flush| C
    E --> F[_apply_saved_option_values queue_index]
    F -->|有实例| G[读 queue_items[i].options 权威]
    F -->|无实例| H[读 task_options[name] 默认]
    I[_runtime_queue_runner] --> J[仅用 entry.options 执行]
    K[_add_to_queue] -->|任务分支| L[以编辑器值生成实例]
```

数据流向：编辑器值 → 仅落该实例 / 或落共享默认（仅任务列表）→ persist 统一写盘；加载时实例优先、默认兜底。

## 目录结构

```
src/gui/pyqt6/
└── pages/
    └── maaend_control_page.py   # [MODIFY] 重写 _save_options（实例隔离）、_on_queue_focus_changed（flush+传 queue_index）、
                                 #           _apply_saved_option_values（支持 queue_index）、_runtime_queue_runner（去共享合并）、
                                 #           _add_to_queue（任务分支去共享）、_build_option_editor（blockSignals）、
                                 #           _on_task_selected/_on_preset_selected（P1-1 _persist_state）。
src/gui/pyqt6/
└── queue_state.py               # [无需改动] 已具备 update_queue_item_options / get_queue_item，满足 per-instance 存储。
tests/
├── test_queue_state.py                          # [MODIFY] 新增重复任务 per-instance 隔离与 persist/load 还原测试。
└── gui/pyqt6/
    └── test_gui_maaend_control.py               # [MODIFY] 新增 _save_options 不污染共享、运行时不泄漏、聚焦 flush 等 GUI 测试。
```

## 关键代码结构

```python
# maaend_control_page.py 关键签名（仅接口级，便于对齐实现）
def _save_options(self) -> None:
    """聚焦队列条目 -> 仅 update_queue_item_options(row, options)；
       仅任务列表选中 -> 仅 save_options(name, options)。"""

def _apply_saved_option_values(self, task_name: str, queue_index: Optional[int] = None) -> None:
    """queue_index 非空时只加载 queue_items[queue_index]['options']（实例权威）；
       否则加载 task_options[task_name]（共享默认）。"""

def _on_queue_focus_changed(self, row: int) -> None:
    """切换前 flush 旧条目实例 options；更新 self._focused_queue_index；重建编辑器并传 queue_index。"""

```