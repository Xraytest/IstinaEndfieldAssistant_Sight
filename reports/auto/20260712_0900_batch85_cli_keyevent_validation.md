# 审计批次 85 — CLI keyevent 校验粒度不一致 / O-10 范围延伸 + 审计批次 84

**生成时间**: 2026-07-12 09:00
**覆盖文件**: `handlers.py`, `vlm_walk_navigator.py`, `runtime.py`, `cli_bridge.py`
**审计方法**: 静态代码逻辑分析，无测试执行
**前置去重**: 已读取 `reports/CODE_REVIEW_WARNS.md`，新发现跳过 FP-01~08、FX-01~10、DUP-A~J、O-01~O-24

---

## 新增发现（1 项）

### CLI-03 — `_handle_device_keyevent` 校验粒度与 daemon 层 `KNOWN_KEYEVENT_NAMES` 不一致

**等级**: 代码质量 / 低
**位置**: `handlers.py:471-483`

**问题代码**:

```python
# handlers.py:471-483
def _handle_device_keyevent(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    android = runtime.android()
    key = str(getattr(args, "key", "")).strip()
    if not key:
        return {"status": "error", "message": "empty keyevent"}
    if not (key.isdigit() or key.startswith("KEYCODE_")):
        return {"status": "error", "message": f"invalid keyevent: {key!r} (must be digits or KEYCODE_* constant)"}
    try:
        android.shell(f"input keyevent {key}")
        return {"status": "success", "key": key}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
```

**根因分析**:

handler 层的校验规则为：`key.isdigit() or key.startswith("KEYCODE_")`。这意味着任何以 `KEYCODE_` 开头的字符串都会被放行，包括 `KEYCODE_INVALID_KEY`、`KEYCODE_NONEXISTENT` 等不在 `KNOWN_KEYEVENT_NAMES` 白名单内的值。

daemon 层（`android_runtime.py:103-112`）的 `_is_valid_keyevent` 校验更严格：

```python
def is_valid_keyevent(key: Any) -> bool:
    if key is None:
        return False
    s = str(key).strip()
    if not s:
        return False
    if s.isdigit():
        return True
    return s in KNOWN_KEYEVENT_NAMES
```

**调用链对比**:

| 层级 | 校验规则 | 放行 `KEYCODE_INVALID`? |
|------|---------|------------------------|
| CLI handler (line 477) | `startswith("KEYCODE_")` | ✓ 放行 |
| daemon `_is_valid_keyevent` | `in KNOWN_KEYEVENT_NAMES` | ✗ 拒绝 |

当 handler 放行一个无效 keyevent 后，daemon 层的 `_is_allowed_shell_cmd` 允许 `input ` 前缀（不检查 keyevent 值本身），命令到达 Android 设备执行。Android 的 `input keyevent KEYCODE_INVALID` 返回错误码，daemon 记录为 shell 执行失败。最终用户看到的错误信息是：

```json
{"status": "error", "message": "input keyevent KEYCODE_INVALID failed: ..."}
```

而非更明确的：

```json
{"status": "error", "message": "invalid keyevent: 'KEYCODE_INVALID' (not in known keyevent list)"}
```

**影响面**:
- **低**：无效 keyevent 最终被 daemon 拒绝，不会执行危险操作。但错误信息不明确，用户难以区分是"keyevent 名称拼写错误"还是"ADB 连接问题"。

**修复建议**:

handler 层校验与 daemon 层对齐：

```python
from core.foundation.shell_security import is_valid_keyevent

def _handle_device_keyevent(runtime: IstinaRuntime, args: argparse.Namespace) -> Dict[str, Any]:
    android = runtime.android()
    key = str(getattr(args, "key", "")).strip()
    if not key:
        return {"status": "error", "message": "empty keyevent"}
    if not is_valid_keyevent(key):
        return {"status": "error", "message": f"invalid keyevent: {key!r} (must be digits or known KEYCODE_* constant)"}
    try:
        android.shell(f"input keyevent {key}")
        return {"status": "success", "key": key}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
```

---

## O-10 范围延伸说明

`_handle_device_keyevent`（line 471）和 `_handle_device_monitor`（line 486）同样未检查 `android.default_client is None`。与 O-10 覆盖的 screenshot/tap 同属一个根因（device handler 间异常处理不一致）。O-10 的修复方案应覆盖全部 6 个 device handler。

---

## 审计结论（批次 84）

| 批次 | 审计对象 | 结论 |
|------|---------|------|
| 批次 84 | RUNTIME-03 (`save_config` 非原子写入) | **结论正确**。当前代码仍为 `open(path, "w").write()`（未修复）。`settings_page.py` 和 `queue_state.py` 已采用原子写入，`runtime.py` 未跟进。 |
| 批次 84 | VLM-03 (`_frame_to_base64` O-22 未修复) | **结论正确**。当前代码仍为 `_, buf = cv2.imencode(".png", frame)` 丢弃返回值（未修复）。 |
| 批次 84 | CLI-02 (交互模式 `_crash_count` 不重置) | **结论正确**。当前代码在交互模式正常退出路径（line 229-231）不重置 `_crash_count`，仅非交互模式（line 255）重置。 |

**批次 84 全部 3 项结论经本批次逐项源码复核确认准确，无需修正。**

---

## 风险摘要

| 级别 | 数量 | 涉及项 |
|------|------|--------|
| 代码质量（低） | 1 | CLI-03 (keyevent 校验粒度不一致) |
| 高风险 | 0 | — |
| 中风险 | 0 | — |

**本轮无中高风险发现。**

---

*批次 85 报告 | 仅分析，无文件修改*