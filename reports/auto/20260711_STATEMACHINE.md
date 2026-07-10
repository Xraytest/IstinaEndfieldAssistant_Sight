# 状态机生命周期审计报告 — IstinaEndfieldAssistant Sight

> **批次定位**：本批次从**状态机生命周期**角度审计 IstinaRuntime 的连接/断开/重连状态转换，识别跨批次遗漏的**状态不一致**问题。不重复提交历史已记录的独立 bug，而是分析对象在其完整生命周期中的状态转换完整性。
>
> **审查方式**：纯静态代码逻辑分析，未执行测试；所有结论均经当前 `main` 分支源文件逐行核对。

---

## 一、审计方法：状态机生命周期追踪

### 1.1 追踪对象

| 对象 | 状态属性 | 状态转换触发点 |
|------|---------|-------------|
| `IstinaRuntime` | `_maaend_clients`、`_android_clients`、`connected` | `connect()`、`disconnect()`、`_ensure_maaend_ready()` |
| `MaaEndRuntime` | `_connected` | `connect()`、`disconnect()`、`_cleanup_partial()` |
| `AndroidRuntimeProxy` | `_clients`（内部 AndroidRuntime 引用） | `_client_for()` 惰性创建 |
| `AndroidRuntime` | `_connected`、`_scrcpy_session` | `_connect_once()`、`_cleanup_partial()` |
| `_ScrcpySession` | `_thread`、`_stop_event`、`_local_port` | `start()`、`stop()` |

### 1.2 追踪的操作序列

| 序列 | 步骤 | 目的 |
|------|------|------|
| **S1** | connect(A) → disconnect() → connect(B) | 不同设备间的状态转换 |
| **S2** | connect() → _ensure_maaend_ready() | 自动重连时的状态转换 |
| **S3** | connect() → scrcpy fails → disconnect() | 部分失败的状态转换 |

---

## 二、核心发现

### SM-1（Medium）`_android_clients` 在 disconnect 后不清理，僵尸代理累积

**位置**：`src/core/service/runtime.py:245-273`

```python
def disconnect(self, serial=None):
    ...
    targets = [serial] if serial is not None else list(self._maaend_clients.keys())
    for target in targets:
        runtime = self._maaend_clients.get(target)
        ...
        self._maaend_clients.pop(target, None)  # ← 清理 _maaend_clients
    # 停止 scrcpy
    android = self.android(serial)
    android.stop_scrcpy(serial=serial)
    # ← 未清理 _android_clients！
```

**问题**：`disconnect()` 从 `_maaend_clients` 中移除 MaaEndRuntime，但 `_android_clients` 中的 AndroidRuntimeProxy 引用**永不被移除**。每次断开重连都会在 `_android_clients` 中留下僵尸代理。

**生命周期追踪（S1 序列）**：

```
初始状态：
  _maaend_clients = {}
  _android_clients = {}

connect("A"):
  _maaend_clients["A"] = MaaEndRuntime_A
  _android_clients["A"] = AndroidRuntimeProxy_A  ← 创建
    proxy_A._clients["A"] = AndroidRuntime_A       ← 惰性创建

disconnect():
  _maaend_clients.pop("A")                         ← 清理
  _android_clients["A"] 仍在！                      ← 僵尸
    proxy_A._clients["A"] = AndroidRuntime_A        ← 僵尸（daemon 已停）

connect("B"):
  _maaend_clients["B"] = MaaEndRuntime_B
  _android_clients["B"] = AndroidRuntimeProxy_B   ← 新创建
  _android_clients["A"] 仍在！                      ← 僵尸累积

disconnect():
  _maaend_clients.pop("B")
  _android_clients["B"] 仍在！                      ← 僵尸累积
  _android_clients["A"] 仍在！                      ← 僵尸累积

最终状态：
  _android_clients = {"A": zombie_proxy_A, "B": zombie_proxy_B}
```

**影响**：
- 内存泄漏：每个僵尸代理持有 `AndroidRuntime` 引用，后者持有 `ADBDeviceManager`、`_ScrcpySession`（及其线程/子进程引用）
- 端口泄漏：ADB forward 端口可能未被释放
- 线程泄漏：`_ScrcpySession._decode_loop` 线程可能在 `stop()` 超时后仍存活

**与历史发现的关联**：
- S2/S3（批次 20）已指出 `_android_clients` 不清理，但将其归类为"资源泄漏"而非"状态机生命周期问题"
- 本次从状态机角度分析，揭示了**断开-重连循环**中僵尸代理的累积过程

### SM-2（Medium）`connect()` 在 scrcpy 失败时仍返回 True，状态 invariant 破损

**位置**：`src/core/service/runtime.py:211-231`

```python
def connect(self, serial=None):
    runtime = self.maaend(serial)
    if not runtime.connected:
        ok = runtime.connect()
        if not ok:
            return False
    resource_ok = runtime.load_resource()
    if not resource_ok:
        return False
    try:
        self.android(serial).start_scrcpy(serial=serial)  # ← 可能失败
    except Exception as exc:
        self._logger.warning(...)  # ← 仅记录警告
    self._logger.info("MaaEnd runtime 已就绪")
    return True  # ← 即使 scrcpy 失败也返回 True！
```

**问题**：`connect()` 的返回值 `True` 意味着"设备已就绪"。但 scrcpy 失败时，返回 `True` 且日志仅记录 warning。调用方（GUI 的 `_on_bridge_command_finished`）收到 `{"status": "success"}`，认为预览通道已建立。

**状态 invariant 破损**：
```
期望：connect() → True  ⟺  MaaEnd 已连接 AND scrcpy 已启动 AND 资源已加载
实际：connect() → True  ⟺  MaaEnd 已连接 AND 资源已加载（scrcpy 可能未启动）
```

**触发场景**：
1. 用户点击"连接设备"
2. MaaEnd 连接成功、资源加载成功
3. scrcpy 启动失败（8s 超时、ADB forward 失败、编解码器不兼容）
4. `connect()` 返回 True
5. GUI 显示"已连接"，预览区域空白
6. 用户不知道预览未启动，认为连接正常

**与历史发现的关联**：
- H1（批次 2210）已指出 scrcpy 超时过紧、失败后 `_scrcpy_session` 死引用
- 本次发现的是**状态 invariant 破损**——`connect()` 的返回值语义不完整

### SM-3（Medium）`_ensure_maaend_ready` 不启动 scrcpy，部分连接状态

**位置**：`src/core/service/runtime.py:233-242`

```python
def _ensure_maaend_ready(self, runtime):
    if runtime.connected:
        return True
    if not runtime.connect():  # ← MaaEndRuntime.connect()，不启动 scrcpy
        return False
    if not runtime.load_resource():
        return False
    return True  # ← MaaEnd 已连接，但 scrcpy 未启动
```

**问题**：`_ensure_maaend_ready` 调用 `MaaEndRuntime.connect()`（仅连接 MaaEnd 框架），不调用 `IstinaRuntime.connect()`（后者才启动 scrcpy）。这意味着自动重连后，系统处于"部分连接"状态——MaaEnd 可用但预览不可用。

**触发场景**：
1. 用户连接设备 → `connect()` 调用 → scrcpy 启动
2. 用户断开设备 → `disconnect()` 调用 → scrcpy 停止，但僵尸代理留在 `_android_clients`
3. 用户运行任务 → `_ensure_maaend_ready` 自动重连 MaaEnd → scrcpy **未启动**
4. 任务执行但无预览

**与 SM-1 的关联**：SM-1（僵尸代理）导致 `android(serial)` 返回旧代理，但 scrcpy 未启动。即使 `_ensure_maaend_ready` 尝试启动 scrcpy，它也不做（因为 `_ensure_maaend_ready` 根本不调用 scrcpy 启动）。

**修复方向**：`_ensure_maaend_ready` 在 MaaEnd 连接成功后，也应启动 scrcpy（复用 `self.android(serial).start_scrcpy()`）。

---

## 三、状态机完整生命周期图

### 3.1 IstinaRuntime 连接状态转换

```
                    ┌─────────────┐
                    │  未连接      │
                    │ (_android={} │
                    │  _maaend={}) │
                    └──────┬──────┘
                           │ connect(serial)
                           ▼
                    ┌─────────────┐
                    │  MaaEnd连接中 │
                    │ (MaaEnd.conn │
                    │  ect()调用中) │
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
     ┌──────────────┐          ┌──────────────┐
     │ MaaEnd连接成功│          │ MaaEnd连接失败│
     │ + scrcpy成功 │          │ return False  │
     │ (完整连接)    │          └──────────────┘
     └──────────────┘
              │
              │ scrcpy 失败
              ▼
     ┌──────────────┐
     │ MaaEnd连接成功│ ← SM-2: 状态 invariant 破损
     │ + scrcpy失败 │   (True 不代表完整连接)
     │ (部分连接)    │
     └──────────────┘
              │
              │ disconnect()
              ▼
     ┌──────────────┐
     │ 断开连接后    │ ← SM-1: _android_clients 僵尸累积
     │ (_maaend={}   │   (_android_clients 保留旧引用)
     │  _android={A} │
     │  _android={B})│
     └──────────────┘
              │
              │ connect(new_serial)
              ▼
     ┌──────────────┐
     │ 重连后        │ ← SM-1: 新代理创建，旧代理僵尸化
     │ (_maaend={new}│
     │  _android={A, │
     │  B, new})     │
     └──────────────┘
```

### 3.2 MaaEndRuntime 连接状态转换

```
                    ┌─────────────┐
                    │   Disconnected│
                    └──────┬──────┘
                           │ connect()
                           ▼
                    ┌─────────────┐
                    │  Connecting  │
                    │ (_connect_   │
                    │  with_timeout│
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
     ┌──────────────┐          ┌──────────────┐
     │   Connected   │          │ 连接失败      │
     │ (_connected   │          │ (_connected   │
     │  = True)      │          │  可能被设为   │
     │               │          │  True—竞态)   │
     └──────┬───────┘          └──────────────┘
            │ disconnect()
            ▼
     ┌──────────────┐
     │ Disconnected  │ ← _cleanup_partial 不释放原生资源
     │ (_connected   │   (C7/N10/N6/S2-S3 反模式 4)
     │  = False)     │
     └──────────────┘
```

---

## 四、修复建议

### 4.1 SM-1 修复：`disconnect()` 清理 `_android_clients`

```python
def disconnect(self, serial=None):
    ...
    # 清理 MaaEnd 客户端
    targets = [serial] if serial is not None else list(self._maaend_clients.keys())
    for target in targets:
        runtime = self._maaend_clients.get(target)
        if runtime is None:
            continue
        try:
            runtime.disconnect()
        except Exception as e:
            ...
        self._maaend_clients.pop(target, None)
        # ← 新增：同时清理 Android 客户端
        self._android_clients.pop(target, None)

    # 停止 scrcpy（如果指定了 serial，只停止该 serial 的 scrcpy）
    if serial:
        android = self.android(serial)
        android.stop_scrcpy(serial=serial)
```

**修改量**：1 行新增（`self._android_clients.pop(target, None)`）。

### 4.2 SM-2 修复：`connect()` 在 scrcpy 失败时降级返回

```python
def connect(self, serial=None):
    runtime = self.maaend(serial)
    if not runtime.connected:
        ok = runtime.connect()
        if not ok:
            return False
    resource_ok = runtime.load_resource()
    if not resource_ok:
        return False
    scrcpy_ok = True
    try:
        self.android(serial).start_scrcpy(serial=serial)
    except Exception as exc:
        self._logger.warning(...)
        scrcpy_ok = False
    if not scrcpy_ok:
        return {"status": "partial", "message": "MaaEnd connected but scrcpy failed"}
    self._logger.info("MaaEnd runtime 已就绪")
    return True
```

**修改量**：返回类型从 `bool` 变为 `Union[bool, dict]`，需更新调用方。

**替代方案（最小修改）**：保持返回 `True`，但在日志中升级为 error 级别，并在返回值中增加 `scrcpy` 字段：
```python
return {"status": "success", "scrcpy": scrcpy_ok}
```

### 4.3 SM-3 修复：`_ensure_maaend_ready` 启动 scrcpy

```python
def _ensure_maaend_ready(self, runtime):
    if runtime.connected:
        # ← 新增：确保 scrcpy 也在运行
        try:
            serial = getattr(runtime, '_device_address', None)
            if serial:
                self.android(serial).start_scrcpy(serial=serial)
        except Exception:
            pass  # scrcpy 非关键路径
        return True
    if not runtime.connect():
        return False
    if not runtime.load_resource():
        return False
    # ← 新增：连接成功后启动 scrcpy
    try:
        serial = getattr(runtime, '_device_address', None)
        if serial:
            self.android(serial).start_scrcpy(serial=serial)
    except Exception:
        pass
    return True
```

---

## 五、与既往报告的关联

| 既往发现 | 关系 | 说明 |
|---------|------|------|
| **S2/S3** (0343.md) | 扩展 | S2/S3 从"资源泄漏"角度报告 `_android_clients` 不清理，本批从**状态机生命周期**角度分析僵尸代理的累积过程 |
| **H1** (2210.md) | 扩展 | H1 从 scrcpy 超时/死引用角度报告，本批从**connect() 返回值语义**角度分析状态 invariant 破损 |
| **N-1** (2400.md) | 独立 | `ensure_src_path` 路径错误与状态机无关 |
| **W1** (2320.md) | 独立 | VLM 行走失效与状态机无关 |

---

## 六、不重复提交声明

本批发现的 3 项状态机生命周期问题（SM-1/2/3）在 23 轮既往审计中**未被作为独立条目记录**。S2/S3 已部分覆盖 `_android_clients` 不清理问题，但未从状态机生命周期角度分析僵尸代理的累积过程，也未涉及 `connect()` 返回值语义和 `_ensure_maaend_ready` 的部分连接状态。

---

*本报告为状态机生命周期审计，未修改任何业务代码。所有分析均经当前 `main` 分支源文件逐行核对。*
