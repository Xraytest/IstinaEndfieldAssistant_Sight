# 批次 62：MaaEndControlPage 新发现 + 历史报告审计复核

> **生成时间**: 2026-07-11 18:10
> **审查范围**: `src/gui/pyqt6/pages/maaend_control_page.py` (1740+ 行), `src/gui/pyqt6/cli_bridge.py` (291 行)
> **审计范围**: 批次 61（`20260711_165135.md`）、批次 1745（`20260711_1745_audit.md`）、批次 1730（`20260711_1730_srv_gui_layer.md`）
> **方法**: 静态代码分析 + 历史报告交叉验证
> **发现总计**: 1 新发现 + 3 审计验证
> **严重度分布**: 0 High / 0 Medium / 0 Low / 1 Low

---

## 项目边界回顾

- IEA 是《明日方舟：终末地》的 MaaEnd/MaaFramework 自动化助手。本仓库为**非第三方**源码：`MaaEnd/` 与 `3rd-part/` 均被 `.gitignore` 忽略，**不在审查范围**。
- 审查仅限本仓库 Python 源码；安全收敛已下沉至 `shell_security.py`。
- 历史累计 260+ 条发现；本批严格避免重复提交历史已覆盖问题。

---

## §1 新发现

### [NEW-LOW] `maaend_control_page.py:364-376` — `_resolve_connect_params` 静默吞没所有异常，隐藏配置读取失败根因

```python
def _resolve_connect_params(self) -> Dict[str, Any]:
    try:
        from core.foundation.paths import get_project_root
        config_path = Path(get_project_root()) / "config" / "client_config.json"
        if config_path.is_file():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            serial = (((data.get("device") or {}).get("last_connected"))
                      or ((data.get("device") or {}).get("serial")))
            if serial:
                return {"serial": serial}
    except Exception:
        pass
    return {}
```

**问题**：`except Exception: pass` 捕获并吞没**所有**异常类型（`JSONDecodeError`、`PermissionError`、`OSError`、`ImportError` 等），不记录日志、不通知用户、不区分正常情况（文件不存在/无 serial）与异常情况（文件损坏/无权限）。

**影响面分析**：

该函数由 `_do_auto_connect`（line 1334-1338）在 GUI 启动时调用：

```python
def _do_auto_connect(self) -> None:
    params = self._resolve_connect_params()
    result = self._sync_execute("system connect", params, timeout_ms=15000)
    self._on_auto_connect_finished(bool(result and result.get("status") == "success"))
```

当 `_resolve_connect_params` 因异常返回空 dict 时：
1. `system connect` 以空 params 执行 → CLI handler 接收 `{"serial": None}` → 连接失败
2. `_on_auto_connect_finished(False)` 设置 `_auto_connect_attempted = True`
3. 用户看到 "Auto-connect failed at startup, will not retry."（line 1347）
4. **根因完全隐藏**：用户不知道是配置文件损坏、路径解析失败、还是其他异常

**关键区分**：
- **正常空返回**（文件不存在 / 有文件但无 serial 字段）：不应报错，静默返回 `{}` 是正确行为
- **异常空返回**（JSON 损坏 / 权限不足 / `get_project_root()` 失败）：应记录日志或通知用户

**具体异常场景**：
| 异常类型 | 触发条件 | 当前行为 | 应有行为 |
|----------|----------|----------|----------|
| `JSONDecodeError` | `client_config.json` 被手动编辑损坏 | 静默返回 `{}`，用户看到通用连接失败 | 记录警告日志 "配置 JSON 损坏，忽略自动连接" |
| `PermissionError` | 配置文件被锁或无读取权限 | 静默返回 `{}`，同上 | 记录错误日志 |
| `OSError` | 磁盘错误 | 静默返回 `{}`，同上 | 记录错误日志 |
| `ImportError` | `get_project_root` 模块异常（极端情况） | 静默返回 `{}`，同上 | 记录错误日志 |

**建议**：

```python
def _resolve_connect_params(self) -> Dict[str, Any]:
    from core.foundation.paths import get_project_root
    try:
        config_path = Path(get_project_root()) / "config" / "client_config.json"
    except Exception as exc:
        self._logger.warning(LogCategory.GUI, "项目路径解析失败，跳过自动连接", error=str(exc))
        return {}
    if not config_path.is_file():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        self._logger.warning(LogCategory.GUI, "配置读取失败，跳过自动连接", error=str(exc))
        return {}
    serial = (((data.get("device") or {}).get("last_connected"))
              or ((data.get("device") or {}).get("serial")))
    if serial:
        return {"serial": serial}
    return {}
```

关键改进点：
1. 区分"文件不存在"（正常路径）与"文件损坏/不可读"（异常路径）
2. 异常场景记录结构化日志，便于调试
3. 保留正常空返回语义（无 serial 字段时不自动连接）

**注意**：本文件存在其他 `except Exception: pass` 模式（line 1110、1223、1234 等），但它们位于非关键路径（UI 刷新、缓存读写），影响面较窄。`_resolve_connect_params` 是**唯一**影响启动连接决策的静默异常点，因此单独列为发现。

---

## §2 历史报告审计

### [AUDIT-1] 批次 61 `20260711_165135.md` 审计 — 两条 Info 发现均合理，无需纠正

**SG-01 Info**（`scene_geometry.py:272`）：平坦图像显著性图 std=0 时阈值退化。

审计结论：**合理，维持 Info**。分析正确指出了 `threshold = max(percentile(89), mean + std*0.8)` 在 std=0 时的退化场景。建议添加 `threshold = max(threshold, 0.05)` 下限保护是有效的边界处理方案。与批次 34 J04（saliency 累积乘法抑制）互补，不重叠。

**SRV-02 Info**（`scene_service.py:57`）：`verify_by_key_elements` 子串匹配假阳性。

审计结论：**合理，维持 Info**。`any(t in fn for fn in found_names)` 子串匹配确实可能产生前缀/后缀误匹配（如 `"button" in "toolbutton"`）。分析正确，建议改为精确匹配或边界匹配有效。

**总体评价**：批次 61 为 0 High / 0 Medium / 0 Low / 2 Info 的精简批次，两条发现均为边界场景优化建议，无过评、无矛盾。

---

### [AUDIT-2] 批次 1745 `20260711_1745_audit.md` 审计 — 4 条审计纠错均合理，无需纠正

**A1（推翻批次 56 SRV-01 High）**：force-stop 命令格式分析正确。`subprocess.check_output(list)` 的 argv 语义 + `adb shell` 对 post-shell 参数的拼接语义分析无误。`shell_security.py` 白名单 `"am force-stop "` 互证有力。结论正确，D1 为假阳性。

**A2（降级批次 56 SRV-02 Medium → Info）**：`_start_agent` 轮询逻辑分析正确。"立即退出=失败；存活 0.5s=就绪"语义清晰，并非"逻辑倒置"。降级为 Info/Style 合理。

**A3（确认批次 56 SRV-03 / 批次 61 AUDIT-1）**：`runtime.py:740` 格式字符串 `%s` 用法正确，与批次 61 审计结论一致。确认无误。

**A4（复核批次 56 SRV-06/SRV-07）**：两条发现状态同步正确，不重复计数。

**NEW-LOW**（`llm/client.py:74` health_check 端点）：分析正确，`str.split('/v1', 1)[0]` 在不含 `/v1` 时返回整个原串导致重复 `/v1`。建议修复方案有效。

**总体评价**：批次 1745 以代码逻辑推演为核心，4 条审计纠错均有决定性证据支撑（argv 语义、adb 拼接语义、白名单互证），无自我矛盾。

---

### [AUDIT-3] 批次 1730 `20260711_1730_srv_gui_layer.md` 审计 — 审查范围覆盖但无控制页发现

批次 1730 审查范围包含 `maaend_control_page.py`（1642 行），但报告正文中**零条**涉及该文件的发现。10 条新发现集中于 `runtime.py`、`llm/runtime.py`、`gpu_check.py`、`shell_security.py`、`device_settings_page.py`。

审计结论：批次 1730 审查了控制页文件但未产生新发现，这与本批审计结果**一致**——控制页的大部分问题已被早期批次（2315/2345/235000 等）覆盖，本批仅发现 `_resolve_connect_params` 这一遗漏点。

---

## §3 发现统计

| 类别 | 条目 | 严重度 | 状态 |
|------|------|--------|------|
| 新发现 | NEW-LOW（`_resolve_connect_params` 静默异常吞没） | Low | 历史未覆盖 |
| 审计验证 | AUDIT-1（批次 61 SG-01/SRV-02 合理） | — | 确认无误 |
| 审计验证 | AUDIT-2（批次 1745 A1-A4 合理） | — | 确认无误 |
| 审计验证 | AUDIT-3（批次 1730 控制页审查充分） | — | 确认无误 |
| **合计** | **1 新 + 3 审计** | **1L** | — |

---

## §4 跨批次一致性验证

- **批次 61 SG-01**（`scene_geometry.py` 平坦图像阈值）→ 无后续批次覆盖或纠正，仍存活。
- **批次 61 SRV-02**（`scene_service.py` 子串匹配）→ 无后续批次覆盖或纠正，仍存活。
- **批次 1650 REC-02**（`recognizer.py` Tier 3 子串匹配）→ 与本批审计范围不同文件，不冲突。
- **批次 1745 A1-A4** → 本批确认无矛盾，所有审计纠错逻辑自洽。
- **批次 56 SRV-01** → 批次 1745 A1 已推翻为假阳性，本批不重复。
- **批次 56 SRV-02** → 批次 1745 A2 已降级，本批不重复。
- **批次 56 SRV-08** → device_settings_page 重连定时器，与本批 `_resolve_connect_params`（maaend_control_page）为不同文件、不同代码路径，不冲突。

---

## §5 验证方法

- 全部发现基于对 `maaend_control_page.py`、`cli_bridge.py`、`handlers.py` 的**逐行静态阅读**与调用链追踪。
- **未执行任何测试**，未修改任何业务代码。
- 审计部分基于对批次 61、批次 1730、批次 1745 报告的逐条代码复核。
- 本批严格遵循"避免重复提交历史已覆盖问题"原则。
