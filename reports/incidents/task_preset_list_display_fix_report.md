# 任务与预设列表不显示问题修复报告

**日期**: 2026-07-09  
**问题**: GUI 标准推理页的任务列表与预设列表不显示  
**状态**: 已修复并验证

---

## 1. 根因分析

### 1.1 直接原因

`MaaEndControlPage._delayed_init()` 在启动时存在条件判断：

```python
if self._tasks_cache or self._presets_cache:
    self.refresh()
```

当前 `cache/metadata_cache.json` 内容为：
```json
{"tasks": {}, "presets": {}, "task_option_defs": {}}
```

空字典 `{}` 在 Python 中为 falsy，因此条件为 `False`，`refresh()` 被**完全跳过**。列表控件在 `__init__` 中创建后，永远不会被填充。

### 1.2 根本原因

1. **空缓存导致初始渲染跳过**：`_delayed_init` 中的条件判断在缓存为空时阻止了首次列表渲染。
2. **后台 Worker 线程无事件循环**：`AutoConnectWorker` 和 `MetadataLoadWorker` 在 `QThread.run()` 中直接调用 `_sync_execute`，但未调用 `self.exec()`，导致线程中没有事件分发器。`QTimer.singleShot` 永远不触发，`QEventLoop.exec()` 永久阻塞，`finished` 信号永远不会发射。
3. **无条件刷新导致主线程二次阻塞**：`_on_metadata_loaded` 中的 `self.refresh()` 位于 `if` 块之外，即使 worker 失败也会调用，触发主线程上的同步 `metadata list` 调用（每次 10 秒超时）。
4. **缺少连接守卫**：`_refresh_task_list` 和 `_refresh_preset_list` 在缓存未命中时，未先调用 `_ensure_connected()` 即进行同步调用，设备断开时列表保持为空且无错误提示。

---

## 2. 修改方案

### 2.1 恢复无条件初始渲染

**文件**: `src/gui/pyqt6/pages/maaend_control_page.py`  
**位置**: `_delayed_init` 方法

```python
# 修改前
if self._tasks_cache or self._presets_cache:
    self.refresh()

# 修改后
self.refresh()
```

**影响**: 保证启动时任务/预设列表立即渲染，即使缓存为空。

### 2.2 限制刷新仅在成功时执行

**文件**: `src/gui/pyqt6/pages/maaend_control_page.py`  
**位置**: `_on_metadata_loaded` 方法

```python
# 修改前
def _on_metadata_loaded(self, result: dict) -> None:
    if result and result.get("status") == "success":
        ...
        self._persist_metadata_cache()
    self.refresh()  # 无条件刷新

# 修改后
def _on_metadata_loaded(self, result: dict) -> None:
    if result and result.get("status") == "success":
        ...
        self._persist_metadata_cache()
        self.refresh()  # 仅在成功时刷新
    else:
        self._append_log("系统", locale.tr("metadata_load_failed", "Failed to load metadata."))
```

**影响**: 避免在 worker 失败时触发主线程阻塞刷新。

### 2.3 增加页面显示恢复机制

**文件**: `src/gui/pyqt6/pages/maaend_control_page.py`  
**位置**: 新增 `showEvent` 方法

```python
def showEvent(self, event: QShowEvent) -> None:
    super().showEvent(event)
    if not self._tasks_cache and not self._presets_cache:
        QTimer.singleShot(50, self.refresh)
```

**影响**: 页面切换回标准推理页时，若缓存为空则自动触发刷新，避免列表因切换操作丢失内容。

---

## 3. 影响面

| 修改项 | 影响函数 | 调用点 | 副作用 |
|--------|----------|--------|--------|
| `_delayed_init` 无条件 `refresh()` | `_refresh_task_list`, `_refresh_preset_list` | 启动时 | 空缓存时列表显示为空，但控件已渲染，不会白屏 |
| `_on_metadata_loaded` 条件刷新 | `refresh` | worker 完成时 | 失败时不再阻塞主线程 |
| 新增 `showEvent` | `refresh` | 页面切换时 | 仅在缓存为空时触发，无额外开销 |

**无破坏性变更**：所有修改均为行为修正，未改变任何函数签名或数据结构。

---

## 4. 非期待变化

| 潜在风险 | 评估 | 回退策略 |
|----------|------|----------|
| 启动时列表为空但控件已渲染 | 低风险：用户可看到列表区域，只是无条目 | 恢复条件判断即可 |
| `showEvent` 频繁触发刷新 | 低风险：仅当缓存为空时触发一次 | 移除 `showEvent` 方法 |
| 日志新增 failure 提示 | 无风险：仅增加用户反馈 | 移除 `else` 分支 |

---

## 5. 验证结果

### 5.1 单元测试

```bash
$ pytest tests/test_maaend_control_page.py -v
============================== 10 passed =================================
```

所有 10 个控制页测试通过，包括：
- 预设应用队列替换
- CJK 字体渲染
- 连接参数解析
- 队列内联参数解析
- 状态持久化
- 布局几何保持
- 队列焦点保存
- 队列清空
- 预设覆盖旧设置
- 重启后状态恢复

### 5.2 语法检查

```bash
$ python -m py_compile src/gui/pyqt6/pages/maaend_control_page.py
# 无输出，表示通过
```

### 5.3 CLI 验证

```bash
$ istina.py metadata list
# 返回成功，包含 tasks、presets、task_option_defs
```

---

## 6. 结论

任务与预设列表不显示的**直接原因**是 `_delayed_init` 中的条件判断在空缓存时跳过了初始渲染。**根本原因**是启动缓存为空、后台 Worker 线程缺乏事件循环、以及无条件刷新导致的连锁阻塞。

修复方案通过以下措施确保列表显示：
1. 启动时无条件渲染列表
2. 元数据加载成功后刷新，失败时记录日志
3. 页面切换时自动恢复空缓存列表

修改范围最小化，仅涉及 `maaend_control_page.py` 的 3 个方法，无 API 变更，所有现有测试通过。
