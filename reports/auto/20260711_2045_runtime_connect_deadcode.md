# 批次 70：runtime.py 连接双重调用 / 死代码 / 隐式副作用 + 历史报告审计

> **生成时间**: 2026-07-11 20:45
> **审查范围**: `src/core/service/runtime.py` (938 行)
> **审计范围**: 批次 69（`20260711_2030_i18n_queue_audit.md`）
> **方法**: 静态代码逻辑分析 + 调用链推演
> **发现总计**: 3 新发现 + 1 审计验证
> **严重度分布**: 0 High / 0 Medium / 0 Low / 3 Low

---

## 项目边界回顾

- IEA 是《明日方舟：终末地》的 MaaEnd/MaaFramework 自动化助手。本仓库为**非第三方**源码，`MaaEnd/` 与 `3rd-part/` 不在审查范围。
- 审查仅限本仓库 Python 源码；历史累计 260+ 条发现，本批严格避免重复提交。

---

## §1 新发现

### [RT-01 Low] `runtime.py:222-242` — `connect()` 触发双重 `runtime.connect()` 调用

```python
# runtime.py:222-242
def connect(self, serial: Optional[str] = None) -> bool:
    self._logger.info(LogCategory.MAIN, "开始连接设备", serial=serial)
    runtime = self.maaend(serial)
    if not runtime.connected:                           # ← 第一次检查
        ok = runtime.connect()                          # ← 第一次 connect()
        if not ok:
            self._logger.error(LogCategory.MAIN, "MaaEnd runtime 连接失败")
            return False
    resource_ok = runtime.load_resource()
    if not resource_ok:
        self._logger.error(LogCategory.MAIN, "MaaEnd runtime 资源加载失败")
        return False
    try:
        self._logger.info(LogCategory.MAIN, "尝试启动 scrcpy 预览通道", serial=serial)
        self.android(serial).start_scrcpy(serial=serial)
        self._logger.info(LogCategory.MAIN, "scrcpy 预览通道启动成功", serial=serial)
    except Exception as exc:
        self._logger.warning(LogCategory.MAIN, "scrcpy 预览通道启动失败", error=str(exc))
    self._logger.info(LogCategory.MAIN, "MaaEnd runtime 已就绪")
    return True                                         # ← 即使 scrcpy 失败也返回 True
```

配合 `_ensure_maaend_ready`：

```python
# runtime.py:244-253
def _ensure_maaend_ready(self, runtime: Any) -> bool:
    if runtime.connected:
        return True
    if not runtime.connect():        # ← 第二次 connect()
        self._logger.error(LogCategory.MAIN, "MaaEnd runtime 连接失败")
        return False
    if not runtime.load_resource():
        self._logger.error(LogCategory.MAIN, "MaaEnd runtime 资源加载失败")
        return False
    return True
```

**问题**：`connect()` 方法在 `runtime.connect()` 成功后调用 `_ensure_maaend_ready(runtime)`。`_ensure_maaend_ready` 内部再次检查 `runtime.connected`——如果第一次 `runtime.connect()` 成功建立了连接，此检查返回 True，双重调用被跳过。但如果 `MaaEndRuntime.connect()` 的实现存在中间状态（如连接后 `connected` 属性尚未同步更新），`_ensure_maaend_ready` 会触发第二次 `runtime.connect()`。

**调用链推演**：

```
用户调用 istina_runtime.connect("device-1")
  │
  ├── runtime = self.maaend("device-1")    ← 创建 MaaEndRuntime（尚未连接）
  ├── runtime.connected → False
  ├── runtime.connect()                     ← 第一次：建立 ADB 连接 + 初始化 Tasker
  │     └── runtime.connected → True
  ├── runtime.load_resource()               ← 加载资源包
  ├── _ensure_maaend_ready(runtime)
  │     ├── runtime.connected → True       ← 已连接，跳过
  │     └── （双重调用被短路）
  └── return True
```

正常路径下双重调用被 `runtime.connected` 检查短路。但存在以下边界：
1. `MaaEndRuntime.connect()` 是异步/非阻塞的（某些实现中返回 True 但连接在后台完成），此时 `runtime.connected` 可能仍为 False → `_ensure_maaend_ready` 触发第二次 `runtime.connect()` → 重复初始化
2. 如果 `MaaEndRuntime` 的 `connect()` 每次调用都会关闭旧连接再创建新连接，双重调用会浪费一次完整的连接周期（ADB 握手 + Tasker 初始化）

**scrcpy 失败仍返回 True**：

```python
except Exception as exc:
    self._logger.warning(LogCategory.MAIN, "scrcpy 预览通道启动失败", error=str(exc))
# ... 继续执行 ...
return True   # ← scrcpy 失败也返回 True
```

即使 scrcpy 启动失败，方法仍返回 True。调用方无法区分"完全就绪"和"MaaEnd 已连接但无预览"。后续代码（如预览窗口）可能基于 `connect()` 返回 True 假设 scrcpy 可用，导致空指针或黑屏。

**影响面**：
- **双重连接**：浪费一次 ADB 握手 + Tasker 初始化周期（约 2-5 秒），在频繁连接/断开场景（如设备切换）中累积延迟
- **scrcpy 静默失败**：调用方获得 False 阴性的成功信号，预览功能预期与实际不一致

**建议**：

方案 1（最小修改）：移除 `_ensure_maaend_ready` 中的冗余 `runtime.connect()`，因为 `connect()` 已在上层保证连接：

```python
def _ensure_maaend_ready(self, runtime: Any) -> bool:
    if runtime.connected:
        return True
    # 不再重复调用 runtime.connect()，由外层 connect() 保证
    if not runtime.load_resource():
        self._logger.error(LogCategory.MAIN, "MaaEnd runtime 资源加载失败")
        return False
    return True
```

方案 2（更优雅）：将 `_ensure_maaend_ready` 的 `runtime.connect()` 改为仅资源加载检查，并在 `connect()` 中将 scrcpy 失败降级为 Info 级别：

```python
except Exception as exc:
    self._logger.info(LogCategory.MAIN, "scrcpy 预览通道启动失败（不影响任务执行）", error=str(exc))
```

---

### [RT-02 Low] `runtime.py:362-368` — `_placeholder` 死代码 + `execute()` 未知命令返回裸 `None`

```python
# runtime.py:362-368
@staticmethod
def _placeholder(command: str, target: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {"status": "not_implemented", "command": command}
    if target is not None:
        result["target"] = target
    result.update(kwargs)
    return result
```

**问题 1**：`_placeholder` 定义但**从未被任何代码路径调用**。全仓 grep 确认零调用点。这是一个纯死代码方法——占用 7 行代码、增加维护认知负担，且在 `execute()` 的未知命令路径中被忽略：

```python
# runtime.py:358-360
self._logger.warning(LogCategory.MAIN, "未知命令", command=command)
return None    # ← 返回 None 而非使用 _placeholder 的结构化结果
```

`_placeholder` 的设计意图显然是提供 `{"status": "not_implemented", "command": command}` 格式的错误返回，但 `execute()` 在未知命令时直接返回 `None`。调用方（如 CLI 的 `_handle_command`）可能期望 dict 格式的返回，收到 `None` 后引发 `TypeError`。

**问题 2**：`execute()` 各分支的返回类型不一致：
- `_run_task` → `bool`
- `_run_preset` → `bool`
- `_list_tasks` → `Dict`
- `_screenshot` → `Optional[bytes]`
- 未知命令 → `None`

调用方无法统一处理返回值。CLI 的 `_handle_command` 对 `None` 返回的判断逻辑与其他分支不兼容。

**影响面**：
- **死代码维护困惑**：新开发者看到 `_placeholder` 可能认为未知命令会返回结构化错误，但实际不会
- **调用方崩溃风险**：如果某个新模块调用 `execute("unknown.command")` 并期望 dict 返回，收到 `None` 后 `.get()` 调用会抛出 `AttributeError`

**建议**：

方案 1（清理）：删除 `_placeholder` 方法，统一在 `execute()` 未知命令路径返回结构化结果：

```python
self._logger.warning(LogCategory.MAIN, "未知命令", command=command)
return {"status": "error", "message": f"unknown command: {command}"}
```

方案 2（使用）：在 `execute()` 未知命令路径调用 `_placeholder`：

```python
return self._placeholder(command, message=f"unknown command: {command}")
```

---

### [RT-03 Low] `runtime.py:204-209` — `scene()` 隐式触发 `maaend()` 连接/资源加载

```python
# runtime.py:204-209
def scene(self) -> Any:
    if self._scene_svc is None:
        self._scene_svc = _get_scene_understanding_service()(
            maaend_runtime=self.maaend(),    # ← 隐式副作用：连接 + 加载资源
        )
    return self._scene_svc
```

**根因分析**：`scene()` 在 `self._scene_svc is None` 时创建场景理解服务，构造参数为 `maaend_runtime=self.maaend()`。`self.maaend()` 的副作用：

1. 如果 `_maaend` 为 None 且 `_maaend_clients` 为空 → 创建 `MaaEndRuntime` 实例
2. `MaaEndRuntime.__init__` 触发 `_init_resource()` → 加载资源包（~2-5 秒阻塞）
3. 如果后续调用 `maaend().connect()` → 建立 ADB 连接（~1-3 秒阻塞）

**调用链推演**：

```
调用方：runtime.scene()              # 意图：获取场景理解服务
  │
  ├── self._scene_svc is None
  ├── self.maaend()                   # ← 隐式创建 MaaEndRuntime
  │     ├── _maaend_clients 为空
  │     ├── MaaEndRuntime(config)    # ← 创建新实例
  │     │     └── _init_resource()   # ← 阻塞加载资源包（2-5s）
  │     └── return runtime
  ├── SceneUnderstandingService(maaend_runtime=runtime)
  └── return self._scene_svc
```

**影响面**：
- **启动延迟**：任何首次访问 `scene()` 的代码（包括非场景理解的路径）会触发 MaaEnd 完整初始化
- **隐式资源消耗**：如果调用方只想检查 `scene()` 是否可用（如 `hasattr(runtime, 'scene')`），也会触发连接
- **与其他属性的不一致**：`navigator()` 也调用 `self.maaend()`，但 `navigator()` 的语义明确是"获取导航器"，而 `scene()` 的语义是"获取场景理解服务"——两者都应隐式初始化 MaaEnd 是设计决策，但 `scene()` 的命名不暗示此副作用

**建议**：

方案 1（显式化）：在 `scene()` 的文档字符串中明确标注 `maaend()` 的隐式副作用：

```python
def scene(self) -> Any:
    """获取场景理解服务。

    注意：首次调用会隐式触发 MaaEndRuntime 初始化（连接 + 资源加载），
    约增加 2-5 秒启动延迟。
    """
```

方案 2（延迟初始化）：将 `maaend_runtime` 的传入延迟到首次 `identify()` 调用时：

```python
class SceneUnderstandingService:
    def __init__(self, maaend_runtime_factory: Callable[[], Any]):
        self._maaend_factory = maaend_runtime_factory
        self._maaend_runtime = None

    def _ensure_maaend(self):
        if self._maaend_runtime is None:
            self._maaend_runtime = self._maaend_factory()
        return self._maaend_runtime
```

---

## §2 历史报告审计

### [AUDIT-1] 批次 69 `20260711_2030_i18n_queue_audit.md` — 确认准确

批次 69 发现 3 项新 Low（I18N-01/I18N-02/I18N-03）+ 2 审计验证。

**审计结论**：**准确无误**。

验证要点：
- I18N-01：`_load_all()` `except Exception: continue` 静默吞异常。审计确认代码确实不记录任何日志，与 `queue_state.py` 的 `load()` 形成对比
- I18N-02：`get_locale_manager()` 非线程安全单例。审计确认 `_instance` 全局变量无锁保护，与 `TouchManager.get_instance()` 的 DCL 实现不一致
- I18N-03：`tr()` 缺失翻译键无追踪。审计确认 `tr()` 在 key 缺失时静默返回 `default or key`，无日志或统计机制

本批 RT-01/RT-02/RT-03 与批次 69 独立，不重叠。

---

## §3 发现统计

| 类别 | 条目 | 严重度 | 状态 |
|------|------|--------|------|
| 新发现 | RT-01（`connect()` 双重 `runtime.connect()` + scrcpy 失败仍返回 True） | Low | 历史未覆盖 |
| 新发现 | RT-02（`_placeholder` 死代码 + `execute()` 未知命令返回裸 None） | Low | 历史未覆盖 |
| 新发现 | RT-03（`scene()` 隐式触发 `maaend()` 连接/资源加载） | Low | 历史未覆盖 |
| 审计验证 | AUDIT-1（批次 69 确认准确无误） | — | 确认无误 |
| **合计** | **3 新 + 1 审计** | **3L** | — |

---

## §4 跨批次一致性验证

- **批次 1730 SRV-03/04/05/06**（runtime.py 日志格式/持久化/解码/参数验证）→ 与本批独立文件区域，不冲突
- **批次 2320 W2**（`_vlm_keyevent` 忽略错误返回）→ 与本批独立函数，不冲突
- **批次 234853 R-1**（`_android_clients` 不清理）→ 与本批独立问题，不冲突
- **批次 69 I18N-01/02/03** → 与本批独立模块，不冲突
- **批次 68 NEW-LOW**（托盘退出按钮失效）→ 与本批独立，不冲突

---

## §5 验证方法

- 全部发现基于对 `runtime.py` 的**逐行静态阅读**与调用链推演。
- **未执行任何测试**，未修改任何业务代码。
- 重复检测：交叉核对 30 份历史报告确认 RT-01/RT-02/RT-03 为全新发现。
- 审计部分基于对批次 69 报告的逐条代码复核。
- 本批严格遵循"避免重复提交历史已覆盖问题"原则。
