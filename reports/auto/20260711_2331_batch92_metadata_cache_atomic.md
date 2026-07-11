# 审计批次 92 — CACHE-01 metadata_cache 非原子写入 + 审计批次 91

**生成时间**: 2026-07-11 23:31
**覆盖文件**: `maaend_control_page.py`, `vlm_walk_navigator.py`, `maa_end/runtime.py`
**审计方法**: 静态代码逻辑分析，无测试执行
**前置去重**: 已读取 `reports/CODE_REVIEW_WARNS.md`，新发现跳过 FP-01~08、FX-01~10、DUP-A~J、O-01~O-24

---

## 审计结论（批次 91）

| 批次 | 审计对象 | 结论 |
|------|---------|------|
| 批次 91 | AGENT-01 (`_start_agent` 就绪检查循环在进程存活时误设 ready) | **结论正确**。`maa_end/runtime.py:466-474` 的逻辑确实存在时序缺陷——进程在 sleep 后 poll 检查后立即崩溃时，`ready = True` 不会被重置。 |
| 批次 91 | 批次 90 全部 2 项 | **结论正确**。SHELL-01 和 PRTS-05 经源码复核确认准确。 |

**补充观察**：AGENT-01 报告指出了就绪检查循环的时序问题，但未覆盖其后的另一个缺陷：`_start_agent` 的 `except` 块（line 483-495）仅清理 `_agent_client` 和 `_agent_process`，**未重置 `_connected`**。结合 `_connect_once` (line 330) 在 Agent 初始化成功后设置 `self._connected = True`，若 `AgentClient.bind()` 或 `AgentClient.connect()` 抛出异常（如 go-service 在 bind 前崩溃），异常被捕获后 `_connected` 仍保持 True——后续 `run_task`/`run_pipeline` 检查 `self._connected` 通过，但 `_tasker` 可能未完成 bind，导致任务执行失败。这属于 AGENT-01 修复范围的延伸，建议在修复 AGENT-01 时一并处理：

```python
# 在 _connect_once 的 try/except 中增加：
except Exception as e:
    self.logger.warning(LogCategory.MAIN, "AgentClient 初始化异常", error=str(e))
    self._connected = False  # 补充：异常时重置连接态
```

---

## 新增发现（1 项）

### CACHE-01 — `_persist_metadata_cache` 非原子写入，异常时缓存文件损坏

**等级**: 代码质量 / 低
**位置**: `gui/pyqt6/pages/maaend_control_page.py:1575-1584`

**问题代码**:

```python
# gui/pyqt6/pages/maaend_control_page.py:1575-1584
def _persist_metadata_cache(self) -> None:
    try:
        data = {
            "tasks": self._tasks_cache,
            "presets": self._presets_cache,
            "task_option_defs": self._task_option_defs,
        }
        self._metadata_cache_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass
```

**根因分析**:

`_persist_metadata_cache` 直接调用 `write_text` 覆盖写入缓存文件。若写入过程中发生异常（磁盘满、进程被终止、权限变更），文件内容会被截断为半写状态——部分 JSON 内容已写入但未完成。下次启动时 `_load_metadata_cache` 读取该文件会触发 `json.JSONDecodeError`，被 `except Exception: pass` 静默忽略，导致任务列表和预设列表为空，用户需手动刷新或重启。

**与同类代码的对比**:

| 写入位置 | 写入方式 | 防护 |
|---------|---------|------|
| `settings_page.py:196-211` | 原子写入 (tempfile + os.replace) | ✓ |
| `queue_state.py:122-124` | 原子写入 (tmp + os.replace) | ✓ |
| **`maaend_control_page.py:1582`** | **直接 write_text** | **✗** |
| `maaend_control_page.py:879` (_export_queue) | 直接 write_text | ✗ |
| `maaend_control_page.py:311` (device_settings) | 直接 write_text | ✗ |

同一文件内至少 3 处非原子写入。`_export_queue` 在用户主动导出时风险较低（用户可重试），但 `_persist_metadata_cache` 在后台自动触发（每次 metadata 加载后），用户无感知。

**调用链**:

```
_do_metadata_load (line 1702)
  └── _sync_execute("metadata list")
       └── _on_metadata_loaded (line 1706)
            └── _persist_metadata_cache()  ← 非原子写入
```

**影响面**:
- **低**：仅影响缓存文件。缓存损坏后 `_load_metadata_cache` 静默返回空，下次 `_do_metadata_load` 会重新从 CLI 获取，功能可恢复。但用户会看到空白的任务/预设列表，直到手动刷新。

**修复建议**:

```python
def _persist_metadata_cache(self) -> None:
    try:
        data = {
            "tasks": self._tasks_cache,
            "presets": self._presets_cache,
            "task_option_defs": self._task_option_defs,
        }
        self._metadata_cache_path.parent.mkdir(parents=True, exist_ok=True)
        import tempfile, os
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._metadata_cache_path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False, indent=2))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self._metadata_cache_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except Exception as exc:
        self._logger.warning("metadata cache persist failed: %s", exc)
```

---

## 风险摘要

| 级别 | 数量 | 涉及项 |
|------|------|--------|
| 代码质量（低） | 1 | CACHE-01 (metadata_cache 非原子写入) |
| 高风险 | 0 | — |
| 中风险 | 0 | — |

**本轮无中高风险发现。**

---

*批次 92 报告 | 仅分析，无文件修改*
