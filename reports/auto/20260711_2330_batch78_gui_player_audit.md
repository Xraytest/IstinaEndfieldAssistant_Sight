# 审计批次 78 — GUI 控制页 / 脚本引擎 / 深拷贝验证 + 历史报告审计

**生成时间**: 2026-07-11 23:30+
**覆盖文件**: `maaend_control_page.py`, `player.py`, `scripting_page.py`, `color_backend.py`, `pipeline_node.py`, `pipeline_loader.py`, `map_data_loader.py`, `entity_db.py`, `client.py`
**审计方法**: 静态代码逻辑分析，无测试执行

---

## 新增发现（4 项）

### GUI78-01 — `_execute_action` 末尾冗余调度 + 停止路径下 `playback_finished` 与 `playback_stopped` 信号混淆

**等级**: BUG / 中
**位置**: `player.py:113-138, 175-180`

```python
def _execute_action(self) -> None:
    # ...
    action = self._script.actions[self._current_index]
    self._current_index += 1
    # ... 执行动作 ...
    self._schedule_next(self._default_delay_ms)  # ← 末尾无条件调度
```

**问题分析**:

**子问题 A — 完成路径冗余调度**: 当执行最后一条动作后，`_current_index` 已递增到 `len(actions)`。末尾仍调用 `_schedule_next`，该方法检测到索引越界后调用 `_on_finished()` → 发射 `playback_finished`。这个间接调用路径是完成回放的标准路径，本身不构成 bug。

**子问题 B — 停止路径信号混淆**: 当用户在 timer 回调触发 `_execute_action` 后、`_schedule_next` 前调用 `stop()`：

```python
def stop(self) -> None:
    self._stopped = True       # 设置停止标志
    if self._action_timer is not None:
        self._action_timer.stop()   # 停止当前 timer
    # ...
    if self.playback_stopped:
        self.playback_stopped.emit()  # ← 发射 "stopped"
```

但 `_execute_action` 正在执行中（不被 timer 中断），其末尾仍会调用 `_schedule_next` → 创建新 timer → 新 timer 触发 → `_execute_action` → `_current_index >= len` → `_on_finished()` → 发射 `playback_finished`。

**后果**:
- 手动停止时同时发射 `playback_stopped` 和 `playback_finished`
- `ScriptingPage._on_playback_finished`（line 258-263）被调用，恢复按钮状态
- `ScriptingPage._on_playback_stopped`（line 265-270）也被调用，同样恢复按钮状态
- 双重恢复是幂等的，但信号语义被污染：监听者无法区分"正常完成"和"手动停止"

**建议**:

```python
def _execute_action(self) -> None:
    # ...
    # 仅在还有后续动作时调度，否则直接完成
    if not self._stopped and self._current_index < len(self._script.actions):
        self._schedule_next(self._default_delay_ms)
    elif not self._stopped:
        self._on_finished(natural=True)
    # stopped 信号已在 stop() 中发射，此处不再重复

def _on_finished(self, natural: bool = True) -> None:
    self._current_index = 0
    if natural:
        logger.info("Playback finished")
        if self.playback_finished:
            self.playback_finished.emit()
```

---

### GUI78-02 — 队列执行中重复解析内联任务名，inline_options 被冗余合并

**等级**: 代码质量 / 低
**位置**: `maaend_control_page.py:929-931`

```python
# _runtime_queue_runner (line 922-933)
name, inline_options = self._normalize_runtime_entry(entry)  # ← 已解析 inline_options
options = dict(entry.get("options") or {})
if inline_options:
    options = {**options, **inline_options}                     # ← 第一次合并
# ...
clean_name, inline_options = self._parse_inline_task_name(name)  # ← 再次解析同一 name
merged_options = dict(inline_options)                             # ← 重新创建
merged_options.update(options)                                    # ← 第二次合并（覆盖）
```

**问题**: `_normalize_runtime_entry` 在第 923 行已经调用 `_parse_inline_task_name` 提取了 `inline_options` 并合并到 `options`。第 929-931 行对同一 `name` 再次调用 `_parse_inline_task_name`，提取完全相同的 `inline_options` 并创建新的 `merged_options`。

**后果**:
- 冗余的函数调用和字典操作
- 若 `_parse_inline_task_name` 解析逻辑未来变更，两处可能产生不一致
- `merged_options` 覆盖了已正确合并的 `options`，语义等价但路径冗余

**建议**: 使用第 923 行已解析的 `name` 和 `options`，删除第 929-931 行的重复解析：

```python
# 替换:
# clean_name, inline_options = self._parse_inline_task_name(name)
# merged_options = dict(inline_options)
# merged_options.update(options)
# result = self._sync_execute(f"task run {clean_name}", {"options": merged_options}, ...)
# 为:
result = self._sync_execute(f"task run {name}", {"options": options}, ...)
```

---

### GUI78-03 — `scripting_page.py:155` 死代码：变量赋值后立即被覆盖

**等级**: 代码质量 / 低
**位置**: `scripting_page.py:155-157`

```python
def _on_record_clicked(self) -> None:
    if self._recorder.is_recording():
        return
    script_name = f"script_{Path(__file__).resolve().name}"  # ← 赋值（使用 file name）
    from datetime import datetime                               # ← 导入
    script_name = f"script_{datetime.now().strftime('%Y%m%d_%H%M%S')}"  # ← 立即覆盖
```

**问题**: 第 155 行的 `script_name` 赋值使用 `Path(__file__).resolve().name`（结果是 `"script_scripting_page.py"`），但第 157 行立即用时间戳覆盖。第 155 行的赋值是死代码。

**后果**:
- 误导维护者认为录制脚本名基于文件路径
- 如果误删第 157 行，会生成以文件名命名的脚本

**建议**: 删除第 155 行。

---

### GUI78-04 — `color_backend.py` 使用标准 logging 而非项目 logger 框架

**等级**: 代码质量 / 低
**位置**: `color_backend.py:8-16`

```python
import logging
# ...
logger = logging.getLogger(__name__)
```

**问题**: 项目中其他所有模块均通过 `from core.foundation.logger import get_logger` 获取 logger，该框架提供 `LogCategory` 分类和结构化日志功能。`color_backend.py` 直接使用标准 `logging.getLogger`，导致其日志：
1. 不携带 `LogCategory` 分类标签
2. 无法享受项目日志系统的统一配置

**后果**: 颜色匹配失败时的 debug 日志（line 190, 284）在日志流中缺少分类标记，与项目其他模块格式不一致。

**建议**: 改为使用项目 logger：

```python
from core.foundation.logger import get_logger
logger = get_logger(__name__)
```

---

## 审计结论（批次 77）

| 批次 | 审计对象 | 结论 |
|------|---------|------|
| 批次 77 | PIPELINE-01 (`_loaded_modules` 写入无读取) | **结论正确**。`pipeline_loader.py:38-41` 中 `_loaded_modules.add(module_name)` 确实无读取检查，每次调用 `load_module` 都会重新解析文件。 |
| 批次 77 | PIPELINE-02 (无效 recognition 类型静默回退 DirectHit) | **结论正确**。`pipeline_node.py:55` 的 else 分支确实无 warning 日志，畸形 JSON 配置被静默转换。 |
| 批次 77 | MDL-02 (MapDataLoader 层级条目键缺失导致级联失败) | **结论正确**。`map_data_loader.py:121` 的 `lv["x"]` 等直接键访问无防御，单个畸形条目导致整个地图加载失败。 |
| 批次 77 | PL-03 (死代码 + 日志级别过低) | **结论正确**。`pipeline_loader.py:103` 的 `pass` 为死代码，line 106 的 `logger.debug` 确实过低导致畸形节点被静默跳过。 |
| 批次 77 | NAV-05 (`find_by_name` 正则无缓存) | **结论正确**。`entity_db.py:150` 每次调用 `re.compile` 存在性能开销，且空字符串未做检查。 |
| 批次 77 | LLM-01 (health_check URL 尾部斜杠) | **结论正确**。`client.py:74` 的 `split('/v1', 1)` 在尾部斜杠场景下可能产生双斜杠 URL。 |

**批次 77 全部 6 项结论经本批次逐项源码复核确认准确，无需修正。**

---

## 补充审计：队列移动按钮浅拷贝假阳性排除

**审查对象**: `maaend_control_page.py:833-843` (`_queue_move_up` / `_queue_move_down`)

**初步疑虑**: 两方法通过 `self._queue_state.queue_items` 获取列表（返回浅拷贝），在拷贝上交换元素，怀疑操作不持久化。

**完整调用链验证**:

```
_queue_move_up():
  1. items = self._queue_state.queue_items  → QueueState.property 返回 list(self._queue_items) [浅拷贝]
  2. items[row], items[row-1] = items[row-1], items[row]  → 修改拷贝
  3. self._queue_state.set_queue_items(items)  → [k: dict(v) for v in items] 写回内部缓存
  4. self._restore_queue_ui()  → 从 self._queue_state.queue_items 读取新顺序刷新 UI
  5. self._queue_list.setCurrentCell(row-1, 0)  → 更新选中行
  6. self._queue_state.persist()  → 原子写入磁盘
```

**结论**: 持久化链完整（步骤 3-6），队列移动操作**完全生效**。浅拷贝在此场景下是正确设计（防止调用方直接修改内部缓存）。此疑虑为假阳性。

---

## 风险摘要

| 级别 | 数量 | 涉及项 |
|------|------|--------|
| BUG（中） | 1 | GUI78-01 (playback_finished / playback_stopped 信号混淆) |
| 代码质量（低） | 3 | GUI78-02 (冗余解析), GUI78-03 (死代码), GUI78-04 (logging 不一致) |

**无新发现高风险项。**

本轮审计重点覆盖了 GUI 控制页队列操作、脚本回放引擎、脚本录制页面、颜色匹配后端。队列移动按钮的浅拷贝问题经完整调用链推演后确认为假阳性（持久化链完整）。player.py 的信号语义混淆为功能性 bug（停止时错误发射完成信号）。其余为代码质量改进项。

---

*批次 78 报告 | 仅分析，无文件修改*
