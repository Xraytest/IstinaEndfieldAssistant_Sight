# 批次 72：CLI 处理器边界校验 / 重复代码 / 桩函数 + 历史报告审计

> **生成时间**: 2026-07-11 21:30
> **审查范围**: `src/cli/handlers.py` (970 行), `src/cli/istina.py` (399 行), `src/gui/pyqt6/main_window.py` (391 行)
> **审计范围**: 批次 71（`20260711_2100_qtlog_widget_parent_audit.md`）、批次 65（`20260711_1910_prts_worker_race.md`）
> **方法**: 静态代码逻辑分析
> **发现总计**: 4 新发现 + 2 审计验证
> **严重度分布**: 0 High / 0 Medium / 1 Low / 2 Low / 1 Info

---

## 项目边界回顾

- IEA 是《明日方舟：终末地》的 MaaEnd/MaaFramework 自动化助手。本仓库为**非第三方**源码，`MaaEnd/` 与 `3rd-part/` 不在审查范围。
- 审查仅限本仓库 Python 源码；历史累计 260+ 条发现，本批严格避免重复提交。
- 本批聚焦 CLI handler 层（`handlers.py`）及 `istina.py` 的重复/缺失逻辑。

---

## §1 新发现

### [CLI-01 Low] `handlers.py:708-747` — `_handle_gpu_monitor` 在 GPUtil 安装但无 GPU 时返回误导性消息

```python
# handlers.py:708-747
def _handle_gpu_monitor(runtime, args):
    try:
        import pynvml
        pynvml.nvmlInit()
        # ... pynvml path ...
    except Exception:
        try:
            import GPUtil
            gpu = GPUtil.getGPUs()[0]         # ← 若 getGPUs() 返回空列表则 IndexError
            return {
                "utilization": {
                    "gpu_percent": gpu.load * 100,
                    "memory_percent": (gpu.memoryUsed / gpu.memoryTotal) * 100 if gpu.memoryTotal else None,
                },
                ...
            }
        except Exception:
            return {"status": "success", "message": "no gpu libs", "utilization": None, "memory": None}
```

**根因分析**：`GPUtil.getGPUs()` 在 NVIDIA GPU 不存在时返回空列表 `[]`。`[0]` 触发 `IndexError`，被内层 `except Exception` 捕获，返回 `"no gpu libs"` 消息。

**调用链推演**：

```
_handle_gpu_monitor()
  │
  ├── import pynvml → ImportError (未安装 nvidia-ml-py)
  ├── import GPUtil → 成功（已安装 GPUtil）
  ├── GPUtil.getGPUs() → []（无 NVIDIA GPU，或仅 AMD/Intel 核显）
  ├── [0] → IndexError
  └── except Exception → {"message": "no gpu libs"}  ← 误导：实际是 GPUtil 已安装但无 GPU
```

**问题**：
1. **误导性诊断消息**：`"no gpu libs"` 暗示 GPUtil 未安装，实际是已安装但未检测到 GPU。用户在排查 GPU 库安装问题时被误导。
2. **与 `_handle_gpu_status` 不一致**：同文件的 `_handle_gpu_status` (line 665-705) 正确处理了 `gpus = GPUtil.getGPUs()` 后检查 `if gpus:`，然后才取 `gpus[0]`。`_handle_gpu_monitor` 未做此检查。
3. **非零退出码掩埋**：`_handle_gpu_status` 在 GPUtil 无 GPU 时返回 `{"status": "success", "gpus": []}`——正确区分"无库"和"无 GPU"。`_handle_gpu_monitor` 的 `"no gpu libs"` 消息与 `_handle_gpu_status` 的 `[]` 语义冲突。

**影响面**：
- **低**：异常被 `except Exception` 捕获，不会崩溃。但返回 `"no gpu libs"` 与实际情况不符，用户可能误以为需要安装 GPUtil。
- **UX**：`istina gpu monitor` 在无 NVIDIA GPU 机器上返回"no gpu libs"，但 `istina gpu status` 在同一机器上返回 `{"gpus": []}`——同一功能的不同子命令对同一场景返回不一致的诊断结论。

**建议**：

```python
def _handle_gpu_monitor(runtime, args):
    try:
        import pynvml
        # ... pynvml path (unchanged) ...
    except Exception:
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if not gpus:
                return {"status": "success", "message": "no gpu detected", "utilization": None, "memory": None}
            gpu = gpus[0]
            return {
                "utilization": {
                    "gpu_percent": gpu.load * 100,
                    "memory_percent": (gpu.memoryUsed / gpu.memoryTotal) * 100 if gpu.memoryTotal else None,
                },
                ...
            }
        except ImportError:
            return {"status": "success", "message": "no gpu libs", "utilization": None, "memory": None}
        except Exception:
            return {"status": "success", "message": "gpu monitor error", "utilization": None, "memory": None}
```

---

### [CLI-02 Low] `istina.py:239-243` + `handlers.py:25-29` — `_json_dumps` 完全重复定义

```python
# istina.py:239-243
def _json_dumps(result: Any) -> str:
    try:
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False)

# handlers.py:25-29
def _json_dumps(result: Any) -> str:
    try:
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False)
```

**根因分析**：两个文件中定义了完全相同的 `_json_dumps` 函数。内容、签名、行为完全一致。

`istina.py` 的 `_json_dumps` 被 `main()` 和 `_interactive_loop()` 使用。
`handlers.py` 的 `_json_dumps` 被... 实际上 `handlers.py` 中的 `_json_dumps` 在文件内**未被任何函数引用**——所有 handler 函数直接返回 dict，由 `main()` 中的 `_json_dumps` 统一序列化。

**影响面**：
- **维护隐患**：未来修改序列化逻辑（如添加默认值、修改错误格式）时，需同时修改两处。遗漏一处会导致 CLI 输出格式不一致。
- **handlers.py 版本是死代码**：`handlers.py` 的 `_json_dumps` 无任何调用点。`main()` 在 `istina.py` 中统一调用自己的 `_json_dumps`。
- **与批次 66 互补**：批次 66 报告了 `cli_bridge.py` 中 `_interactive = True` 的死代码分支。本批是 `handlers.py` 中 `_json_dumps` 的死代码定义。

**建议**：

方案 1（最小）：删除 `handlers.py` 中的 `_json_dumps`，由 `istina.py` 统一导出：
```python
# istina.py __all__ 已包含 "_json_dumps"
# handlers.py 删除 lines 25-29
```

方案 2（更清晰）：将 `_json_dumps` 移到 `core/foundation/` 下作为共享工具函数。

---

### [CLI-03 Low] `handlers.py:578-588` — `_handle_config_set` 响应返回原始字符串值，而非转换后值

```python
# handlers.py:578-588
def _handle_config_set(runtime, args):
    ...
    runtime.config[key] = _coerce_config_value(key, args.value)
    runtime.save_config()
    return {"status": "success", "key": key, "value": args.value}  # ← 返回原始字符串
```

**根因分析**：`_coerce_config_value` 将字符串值转换为目标类型（bool/int/float），但响应字典的 `"value"` 字段使用 `args.value`（原始输入字符串）而非转换后的值。

**调用链推演**：

```
用户: istina config set llm.temperature 0.3
  │
  ├── args.value = "0.3"
  ├── _coerce_config_value("llm.temperature", "0.3") → 0.3 (float)
  ├── runtime.config["llm.temperature"] = 0.3       ← 存储 float
  ├── runtime.save_config()
  └── return {"value": "0.3"}                       ← 响应中仍是字符串 "0.3"
```

**问题**：调用方（GUI、脚本、其他 API）收到 `"value": "0.3"`（字符串），但实际存储的是 `0.3`（float）。类型不一致可能导致：
- GUI 显示 `"0.3"` 而非 `0.3`（同一值但类型不同）
- 脚本再次读取配置时，得到 float `0.3`，与响应中的字符串 `"0.3"` 类型不匹配

**对比**：`_coerce_config_value` 的设计意图是"尽力转成与目标类型匹配的类型"，但响应中丢弃了转换结果。

**建议**：

```python
coerced = _coerce_config_value(key, args.value)
runtime.config[key] = coerced
runtime.save_config()
return {"status": "success", "key": key, "value": coerced, "original": args.value}
```

---

### [CLI-04 Info] `istina.py:183-184` — `model download` 子命令已定义解析器但无处理函数

```python
# istina.py:183-184
p_model_download = p_model_sub.add_parser("download", help="download model")
p_model_download.add_argument("name", help="model name")
```

**根因分析**：`istina.py` 的 `build_parser()` 为 `istina model download <name>` 创建了完整参数解析器，但 `CLIDispatch.dispatch()` 的 `_handle_model` 方法（handlers.py:610-626）仅处理 `list`/`info`/`disk` 三个子命令：

```python
# handlers.py:610-626
def _handle_model_list(runtime, args): ...
def _handle_model_info(runtime, args): ...
def _handle_model_disk(runtime, args): ...
# _handle_model_download → 不存在
```

用户执行 `istina model download llama-3-8b` 会收到 `{"status": "error", "message": "unknown model action"}`。

**影响面**：
- **UX**：用户看到"download"帮助文本，尝试使用但收到"unknown model action"错误，困惑。
- **低**：功能未实现本身不算 bug，但定义了解析器却不实现处理函数属于"半吊子"设计——要么实现，要么移除解析器。

**建议**：要么实现 `_handle_model_download`（如 HTTP 下载 + 进度回调），要么移除解析器定义。

---

### [GUI-01 Low] `main_window.py:314-317` — `_set_taskbar_progress` 桩函数被 3 处调用

```python
# main_window.py:314-317
def _set_taskbar_progress(self, value: int) -> None:
    # Placeholder for Windows taskbar progress integration.
    # Full implementation would use ITaskbarList3 via COM.
    pass
```

**调用点**：
- Line 297: `self._set_taskbar_progress(0)` — 任务开始时
- Line 304: `self._set_taskbar_progress(100)` — 任务完成时
- Line 305: `QTimer.singleShot(1000, lambda: self._set_taskbar_progress(0))` — 1 秒后重置

**根因分析**：`_set_taskbar_progress` 是 Windows 任务栏进度条的占位实现（使用 ITaskbarList3 COM 接口）。注释说明"Full implementation would use ITaskbarList3 via COM"，但实际代码仅为 `pass`。三个调用点全部无效果。

**影响面**：
- **低**：不影响任何功能，仅浪费 3 次空方法调用（性能影响可忽略）。
- **维护困惑**：新开发者看到方法调用可能认为任务栏进度已实现，实际未生效。Windows 用户在任务栏看不到任务进度指示。

**建议**：要么实现 ITaskbarList3 COM 接口调用，要么移除三个调用点，避免虚假的功能暗示。

---

## §2 历史报告审计

### [AUDIT-1] 批次 71 `20260711_2100_qtlog_widget_parent_audit.md` — 三条 Low 发现均准确

**审计范围**：MAA71-01、MAA71-02、MAA71-03。

**验证结论**：**准确无误**。

验证要点：
- **MAA71-01**：`maaend_control_page.py:174` 的 5 级 `parent` 链确为 `_OPTION_LOCALE_PATH` 定义。`get_project_root()` 位于 `src/core/foundation/paths.py:13-22`，使用 4 级 `parent`（从 `paths.py` 自身推断）。`maaend_control_page.py:174` 使用 5 级 `parent` 链绕过 `get_project_root()`，审计确认论断正确。
- **MAA71-02**：`qt_log_filter.py:55-57` 的 `_INSTALLED` 布尔标志检查与设置非原子。审计确认代码中确实无 `threading.Lock` 保护，与 `TouchManager.get_instance()`、`ThemeManager.__new__()` 的 DCL 模式形成对比。
- **MAA71-03**：`widget_styles.py:49-52` 和 57-60 的 `BLUE_STYLE` 重复定义。审计确认当前代码中两处定义存在且内容完全一致，第二处静默覆盖第一处。

---

### [AUDIT-2] 批次 65 `20260711_1910_prts_worker_race.md` — 确认准确

**审计范围**：PRTS-01（LlmChatWorker 竞态）、PRTS-02（图像附件泄漏）。

**验证结论**：**准确无误**。

验证要点：
- **PRTS-01**：`prts_full_intelligence_page.py:41-46` 的 `LlmChatWorker.run()` 在 `self._bridge.execute()` 返回 `None` 时（CLI 交互进程尚未完成），无条件发出 `{"status": "error", "message": "empty"}` 结果。审计确认 `CLIBridge.execute()` 返回 `None`（异步），`finished.emit(result or {"status": "error", "message": "empty"})` 确实会触发虚假错误消息。
- **PRTS-02**：`_attach_image` 异常时 `_pending_image_b64` 未清理，下次 `_send_chat` 携带已失败的旧图片。审计确认 `_attach_image` 的 `except` 分支仅记录日志未重置 `_pending_image_b64`。

本批 CLI-01/02/03/04 + GUI-01 与批次 65/71 独立，不重叠。

---

## §3 发现统计

| 类别 | 条目 | 严重度 | 状态 |
|------|------|--------|------|
| 新发现 | CLI-01（GPU monitor 误导性消息） | Low | 历史未覆盖 |
| 新发现 | CLI-02（`_json_dumps` 完全重复定义） | Low | 历史未覆盖 |
| 新发现 | CLI-03（`_handle_config_set` 返回原始字符串值） | Low | 历史未覆盖 |
| 新发现 | CLI-04（`model download` 解析器无处理函数） | Info | 历史未覆盖 |
| 新发现 | GUI-01（`_set_taskbar_progress` 桩函数） | Low | 历史未覆盖 |
| 审计验证 | AUDIT-1（批次 71 三条 Low 均准确） | — | 确认无误 |
| 审计验证 | AUDIT-2（批次 65 两条发现均准确） | — | 确认无误 |
| **合计** | **4 新 + 2 审计** | **3L + 1I** | — |

---

## §4 跨批次一致性验证

- **批次 71 MAA71-01/02/03** → 与本批独立文件/模块，不冲突
- **批次 70 RT-01/02/03** → `runtime.py` 与本批 `handlers.py`/`istina.py` 不同文件，不冲突
- **批次 65 PRTS-01/02** → `prts_full_intelligence_page.py` 与本批独立，不冲突
- **批次 69 I18N-01/02/03** → `i18n/__init__.py` 与本批独立，不冲突
- **批次 66 CLI 死代码** → 本批 CLI-02（`_json_dumps` 重复）与批次 66（`_interactive` 死代码）不同问题，互补

---

## §5 验证方法

- 全部发现基于对 `handlers.py`、`istina.py`、`main_window.py` 的**逐行静态阅读**与调用链推演。
- **未执行任何测试**，未修改任何业务代码。
- 重复检测：交叉核对 30 份历史报告确认 CLI-01/02/03/04 和 GUI-01 为全新发现。
- 审计部分基于对 `widget_styles.py`、`qt_log_filter.py`、`maaend_control_page.py`、`prts_full_intelligence_page.py` 的逐行复核。
- 本批严格遵循"避免重复提交历史已覆盖问题"原则。
