# 跨批次综合合成审计报告 — IstinaEndfieldAssistant Sight

> **批次定位**：本批次不进行新模块的全量扫描，而是对 20+ 轮批次审计产出的 97+ 项发现做**跨批次综合合成分析**。
>
> **目标**：识别产生多个具体 bug 的**系统性架构反模式**（root cause patterns），梳理因果链，提出分组修复路线图，并对全部既往报告的审计纠正做终汇总。
>
> **审查方式**：纯静态代码逻辑分析（元分析），未执行测试；所有结论均经既往报告中引用的源码行号与当前代码交叉核对。

---

## 一、跨批次审计纠正终汇总

在 20+ 轮批次中，共产生 **6 处审计纠正**（发现/撤销/降级既往报告中的错误或不必要建议）：

| 编号 | 纠正类型 | 原始报告 | 原始结论 | 纠正结果 | 根本原因 |
|------|---------|---------|---------|---------|---------|
| **CR-1** | 撤销 | 2345.md C4 | break 无条件执行（Critical） | **撤销** | Agent 误读：`break` 在条件分支内（`if process.poll() is not None: break`），实际逻辑正确 |
| **CR-2** | 降级 | 2345.md C8 | `_get_latest_frame` 数据竞争（High） | **降级为 Info** | `_decode_loop` 每帧创建新数组（`frame.to_ndarray()`），无实际数据竞争 |
| **CR-3** | 撤销 | 234853.md Facade C-1 | screenshot 修改 `_connected`（Critical） | **撤销（误报）** | `_screenshot` 为只读操作，不修改 `_connected` |
| **CR-4** | 撤销 | 234853.md Facade C-3 | disconnect 创建新 daemon 线程（Critical） | **撤销（误报）** | `disconnect()` 仅清理客户端引用，不创建线程 |
| **CR-5** | 降级 | 234853.md Facade C-2 | `time.sleep` 阻塞 GUI 线程（High） | **降级为 Low** | 睡眠在守护线程中，不阻塞 GUI 主线程 |
| **CR-6** | 机制修正 | 0200_nav.md NAV-05 | dict 类型 raw_location 导致 TypeError | **机制修正** | dict 不崩溃（`len==2` 走 else）；真实崩溃来自字符串/非数字列表值触发未捕获 ValueError |

**结论**：6 处纠正中，4 处为 agent 误报（CR-1/3/4/5），1 处为严重性高估（CR-2），1 处为机制描述不精确（CR-6）。建议在最终整合报告中标注这些纠正，避免维护者按错误论断修复。

---

## 二、系统性架构反模式识别

以下 6 个架构反模式是产生 97+ 项具体 bug 的**根本原因**。每个反模式均列出其引发的具体问题（括号内为批次编号）。

### 反模式 1：结构性静默失败（Silent Failure by Design）

**定义**：函数在执行失败时不抛异常、不记录日志、不返回错误码，而是返回空值/默认值，使调用方无法区分"成功无结果"与"执行失败"。

**引发的问题**：

| 具体问题 | 位置 | 失效机制 | 批次 |
|---------|------|---------|------|
| **W1 (Critical)** | `vlm_walk_navigator.py:264-280` | `_execute_action` 调用 `_vlm_keyevent` 后不检查返回值，直接记入 history | 2320 |
| W2 (Medium) | `runtime.py:712-730` | `_vlm_keyevent` 的 try/except 捕获不到 keyevent 返回的空串，不记录 warning | 2320 |
| N4 (Medium) | `maa_end/runtime.py:821/830` | 截图失败将 `_connected` 翻转 False，调用方无法区分"瞬断"与"真断连" | 2350 |
| D3 (Medium) | `adb_manager.py:47-55` | `get_devices()` bare except 吞掉 ImportError | 001647 |
| NAV-03 (Medium) | `navigator.py:41` | `__init__` 忽略 `EntityDatabase.load()` 返回值，静默接受空库 | 0200 |
| N12 (Medium) | `maa_end/runtime.py:732-733` | `_try_recover` bare except 吞掉所有异常 | 2350 |
| CFG-12 (Medium) | 多处配置加载 | `except Exception` 吞 JSON 解析错误，静默回退 `{}` | 001631 |
| D11 (Low) | `recovery.py:81-94` | `_clear_canvas` 吞掉所有异常 | 001647 |
| D12 (Low) | `recovery.py:96-111` | `_launch` 异常掩盖原始 activity 错误 | 001647 |

**因果链**：
```
函数执行失败
  → 返回空值/默认值（无异常、无日志）
    → 调用方将"未执行"记为"已执行"（W1 history.append）
      → 上层逻辑基于错误状态继续执行
        → 最终在远离根因的位置出现不可解释的行为
```

**修复方向**：
1. 建立"失败必须可见"原则：任何 I/O、RPC、子进程调用失败必须记录 warning 以上日志
2. 关键返回值（如 keyevent 结果、截图结果）应返回 `(result, error)` 二元组或抛异常
3. 统一异常处理中间件：在 `_dispatch` 和 `_vlm_keyevent` 层建立标准错误处理管道

---

### 反模式 2：守护进程验证不对称（Daemon Validation Asymmetry）

**定义**：安全/逻辑校验在底层守护进程中实现，但上层入口点（CLI/GUI handler）未执行同等校验，导致"代码有白名单但调用方可绕过"的结构性缺陷。

**引发的问题**：

| 具体问题 | 位置 | 不对称机制 | 批次 |
|---------|------|-----------|------|
| **D2 (High)** | `handlers.py:467-473` vs `android_runtime.py:613-619` | `_handle_shell` 直接传递用户输入，但 daemon shell 分支已强制白名单 | 001647/0343 |
| D1 (High) | `recovery.py:72` | `_force_stop` 参数构造错误，mksh 将其解释为单个命令 | 001647 |
| C1 (Medium) | `handlers.py:448` | `_handle_device_keyevent` 仅校验前缀，未过滤 shell 元字符 | 0240 |
| SEC-01 (Medium) | `handlers.py:30-38` | `_write_or_base64` 的 `--out` 路径未验证 | 0235 |

**因果链**：
```
CLI 入口接收用户输入
  → 不校验直接传递到下层 API
    → 下层 API 可能在另一侧有校验（如 daemon 白名单）
      → 但入口校验缺失导致：
        - 校验逻辑分散在两处，维护者只知其一不知其二
        - 未来重构时容易移除一侧校验
        - 用户无法从入口获得即时反馈（如 keyevent 前缀校验 vs 白名单）
```

**修复方向**：
1. 在 CLI handler 层建立**前置校验**，与 daemon 层校验形成"双重门卫"
2. `_handle_shell` 直接复用 `_is_allowed_shell_cmd`，避免逻辑分散
3. `_handle_device_keyevent` 调用 `_is_valid_keyevent` 做前置过滤

---

### 反模式 3：惰性初始化与盲目属性访问（Lazy Init Blind Access）

**定义**：某个属性通过 property/lazy 机制惰性初始化并回填原始属性，但其他代码路径直接读写原始属性而非 property，导致"部分路径走惰性初始化，部分路径读 None"的竞态。

**引发的问题**：

| 具体问题 | 位置 | 失效机制 | 批次 |
|---------|------|---------|------|
| **2345-C10 (High)** | `runtime.py:697` | `_nav3_walk` 读 `self._llm_client`（原始属性），但 LLM 可能尚未初始化 | 2345/0343 |
| N-3 (Medium) | `istina.py:374-382` | `_auto_warmup` 在 `llm stop` 时仍触发预热 | 2400 |

**因果链**：
```
属性 A 通过 property 惰性初始化
  → property 创建对象并回填 self._A（原始属性）
    → 部分代码路径读 self._A（原始属性）
      → 若该路径在 property 首次访问之前执行 → 读到 None
        → 下游函数收到 None 而非预期对象 → 静默降级或崩溃
```

**修复方向**：
1. `runtime.py:697/706` 将 `self._llm_client` 改为 `self._llm_client_instance`（一行修复）
2. 审计全仓库是否存在其他"读原始属性 vs 读 property"的不对称

---

### 反模式 4：原生资源隐式管理（Native Resource Opacity）

**定义**：持有原生资源（ADB 连接、mmap 文件描述符、子进程句柄、DLL 引用）的对象在销毁时依赖 Python `__del__` 而非显式 `close()`/`dispose()`，导致资源泄漏不可控。

**引发的问题**：

| 具体问题 | 位置 | 泄漏机制 | 批次 |
|---------|------|---------|------|
| C7 (Medium) | `android_runtime.py:_cleanup_partial` | 仅将引用置 None，未调用 MaaFW 对象的 dispose | 2345 |
| N10 (Medium) | `maa_end/runtime.py:222-265` | `_connect_once` 失败后 AdbController 仅置 None，未关闭 | 2350 |
| N6 (Medium) | `android_runtime.py:626-658` | `_encode_binary` 中 mmap 失败后 fd 在 finally 前未关闭 | 2350 |
| S2/S3 (Medium) | `runtime.py` | `_android_clients` 从不清理，atexit 阶段僵尸进程累积 | 0020 |

**因果链**：
```
对象持有原生资源（ADB socket、mmap fd、DLL handle）
  → 销毁时仅 self._obj = None
    → Python GC 最终调用 __del__
      → 但 __del__ 可能不执行（循环引用、解释器退出时）
        → 原生资源泄漏（端口占用、文件锁定、进程残留）
```

**修复方向**：
1. 为 `AndroidRuntime`、`MaaEndRuntime`、`AdbController` 定义显式 `close()`/`dispose()` 协议
2. 在 `_cleanup_partial` 中按正确顺序调用 dispose（先断开 agent → 再释放 tasker → 再关闭 ADB）
3. `atexit` 注册清理函数，确保进程退出时释放所有原生资源

---

### 反模式 5：配置管道无校验（Unvalidated Configuration Pipeline）

**定义**：配置文件从加载、解析、存储到使用的全管道缺乏 schema 校验、路径约束和原子写入，任何一个环节出错都会静默降级到默认值，用户无法诊断。

**引发的问题**：

| 具体问题 | 位置 | 失效机制 | 批次 |
|---------|------|---------|------|
| CFG-09 (Medium) | `runtime.py:109-110` | 任意 `--config` 路径可指向项目外部 | 001631 |
| CFG-10 (Medium) | `llm/runtime.py:240-247` | `_resolve_model_path` 允许绝对路径逃逸 | 001631 |
| CFG-11 (Medium) | `client_config.json` | `n_gpu_layers=999` 易导致 OOM | 001631 |
| CFG-12 (Medium) | 多处配置加载 | bare except 吞 JSON 错误，静默回退 `{}` | 001631 |
| SEC-01 (Medium) | `handlers.py:30-38` | `--out` 路径未验证，可写任意位置 | 0235 |
| CFG-15 (Medium) | `runtime.py:447-455` | `_load_config` bare except 吞 MemoryError | 0235 |

**因果链**：
```
配置文件加载
  → 无 schema 校验（JSON 格式正确但语义错误）
    → bare except 吞掉所有错误（格式错误、权限不足、内存不足）
      → 静默回退 `{}`（默认值）
        → 关键配置（device serial、LLM 路径）使用不匹配的默认值
          → 运行时出现不可解释的行为（连错设备、LLM 启动失败）
```

**修复方向**：
1. 定义配置 schema（`client_config.schema.json`），加载时校验
2. `_load_config` 拆分异常类型（FileNotFoundError / JSONDecodeError / PermissionError）
3. `_resolve_config_path` 和 `_resolve_model_path` 增加路径约束（必须在项目目录内）
4. 配置写入使用原子写（`.tmp` + `os.replace`）

---

### 反模式 6：单例并发无锁（Singleton Concurrency Blindness）

**定义**：多个单例类（ThemeManager、TemplateRegistry、TouchManager、LlamaServerRuntime）的 `__new__`、`get_instance`、初始化方法均无锁保护，并发场景下可能创建多实例或出现竞态条件。

**引发的问题**：

| 具体问题 | 位置 | 竞态机制 | 批次 |
|---------|------|---------|------|
| N-7 (Medium) | `theme_manager.py:393-402` | `ThemeManager.__new__` 无锁，并发启动时双实例 | 2400 |
| N-8 (Medium) | `theme_manager.py:445-453` | 全局 `COLORS`/`FONTS` 字典修改无锁 | 2400 |
| N-9 (Medium) | `theme_manager.py` | 主题状态与 `_STYLESHEET` 缓存不一致 | 2400 |
| LLM-06 (Medium) | `llm/runtime.py:42` | `_owned_pids` 集合并发 add/discard 无锁 | 2350_llm |
| LLM-08 (Low) | `llm/runtime.py:52-58` | `_atexit_cleanup` 遍历 `_instances` 无锁 | 2350_llm |
| D10 (Low) | `touch_manager.py:58-64` | 单例 `_instance` 永不重置 | 001647 |
| REC-7 (Low) | `template_registry.py:22-25` | 单例 `__new__` 无锁 | 2350_rec |
| PN-3 (Medium) | `pipeline_node.py:135-137` | `merge` 方法非原子操作 | 0026 |
| N11 (Medium) | `maa_end/runtime.py:133-178` | `load_tasks`/`load_presets` 无锁并发调用 | 2350 |
| PL-3 (Low) | `pipeline_loader.py:21/37` | `_loaded_modules` 无锁 | 0026 |

**因果链**：
```
GUI 启动或任务触发并发调用
  → 单例 `__new__` 同时被多个线程进入
    → 两个线程都认为自己是"第一个"，创建两个实例
      → 两个实例持有不同的原生资源（ADB、DLL、线程）
        → 状态不一致（COLORS 字典半写、_connected 翻转）
          → 难以复现的偶发 bug（取决于线程调度时序）
```

**修复方向**：
1. 为所有单例 `__new__` 增加 `threading.Lock`（`_instance_lock = threading.Lock()`）
2. 全局字典（`COLORS`、`FONTS`、`_instances`）修改使用锁或 `threading.RLock`
3. 初始化方法（`load_tasks`、`_atexit_cleanup`）增加 `threading.Lock` 保护关键区段

---

## 三、因果链深度分析：W1 的级联失效

W1（VLM 行走完全失效）是**结构性静默失败**与**守护进程验证不对称**两个反模式叠加的典型案例。其失效链如下：

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 用户执行 "nav3 walk to_entity xxx"                                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ runtime.execute("nav3.*") → Navigator.to_coords_vlm                     │
│   → VlmWalkNavigator.walk_to()                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ VlmWalkNavigator._execute_action()                                      │
│   input_fn("w")  ← 字母键，非 ADB 合法 keyevent                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ IstinaRuntime._vlm_keyevent("w")                                        │
│   try: android.keyevent("w")                                            │
│   except: logger.warning(...)  ← 永远不会触发                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ AndroidRuntime.keyevent("w")                                            │
│   response = self._call("keyevent", {"key": "w"})                       │
│   return response.get("result", "")  ← 丢弃 error 字段                  │
│                                                                          │
│   守护进程返回: {"error": "invalid keyevent: 'w'"}                      │
│   keyevent() 返回: ""                                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ _is_valid_keyevent("w")                                                 │
│   return False  ← 白名单仅含 17 个 KEYCODE_* 常量和数字               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ _vlm_keyevent 收到空串 ""                                                │
│   try/except 不捕获（无异常抛出）                                        │
│   → 无任何日志记录                                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ _execute_action                                                         │
│   history.append({**action, "status": "executed"})                      │
│   → 将"未执行的动作"记为"已执行"                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────�│
│ VLM 认为自己在移动，日志显示动作已发出                                    │
│ 但设备上零位移                                                           │
│ 直到 stuck 检测（~30s 后）触发 fallback → navmesh                        │
└─────────────────────────────────────────────────────────────────────────┘
```

**级联失效的三重静默**：
1. **守护进程层静默**：返回 error 但不抛异常，调用方收到"成功"响应
2. **门面层静默**：`_vlm_keyevent` 的 try/except 对空串返回无感知，不记日志
3. **导航层静默**：`_execute_action` 不检查返回值，将失败记为成功

**修复方案（分层）**：
- **P0 可见化**（5 行代码）：`keyevent()` 在 `response.get("error")` 时抛异常或返回错误码；`_vlm_keyevent` 记录 warning
- **P1 键位映射**（架构级）：将 VLM 移动键映射到游戏支持的 KEYCODE 或通过 scrcpy 注入真实键码，而非 `input keyevent w`

---

## 四、因果链深度分析：C10 的初始化顺序陷阱

C10（`_nav3_walk` 传 `None` LLM client）是**惰性初始化与盲目属性访问**反模式的典型案例：

```
┌─────────────────────────────────────────────────────────────────────────┐
│ IstinaRuntime.__init__                                                  │
│   self._llm_client = None          ← 原始属性，初始为 None             │
│   self._llm_client_instance = None  ← 门面 property 后端               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
            ┌───────────────────────┴───────────────────────┐
            │                                               │
            ▼                                               ▼
┌───────────────────────────────┐           ┌───────────────────────────────┐
│ 路径 A：用户先 "llm chat"      │           │ 路径 B：用户直接 "nav3 walk"   │
│ → execute("llm.chat")          │           │ → execute("nav3.walk")         │
│ → runtime.py:878               │           │ → runtime.py:697              │
│   读 self._llm_client_instance │           │   读 self._llm_client          │
│   → property 触发：             │           │   → None（原始属性未初始化）   │
│     LlmClient() 创建            │           │   → to_coords_vlm 收到 None   │
│     self._llm_client = 实例     │           │   → fallback_to_navmesh        │
│   → self._llm_client 被回填     │           │   → VLM 路径形同虚设          │
└───────────────────────────────┘           └───────────────────────────────┘
```

**关键发现**：`_llm_client_instance` property（`runtime.py:128-132`）在首次访问时创建 `LlmClient` 并**回填 `self._llm_client`**。这意味着路径 A 执行后，路径 B 也能正常工作。但路径 B 在前时，VLM 路径被静默降级。

**修复方案**（一行代码）：
```python
# runtime.py:697/706
# 将 self._llm_client 改为 self._llm_client_instance
llm_client=self._llm_client_instance  # 触发 lazy init
```

---

## 五、因果链深度分析：配置静默失败链

配置加载的**无校验配置管道**反模式产生级联影响：

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 用户编辑 client_config.json，误删逗号 → JSON 格式错误                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ runtime._load_config()                                                 │
│   try: json.load(f)                                                    │
│   except Exception: logger.warning(...); return {}                     │
│   → JSONDecodeError 被吞，返回 {}                                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ runtime.__init__() 使用默认值                                          │
│   device.serial = "localhost:16512"（默认）                             │
│   llm.model_path = ""（默认）                                           │
│   llm.n_gpu_layers = 999（不安全的默认值）                              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 运行时行为                                                              │
│   → 尝试连接默认设备（可能不存在）                                       │
│   → LLM 启动时 model_path 为空 → 启动必失败                            │
│   → n_gpu_layers=999 → OOM 崩溃                                        │
│   → 用户看到"设备连接失败"或"LLM 启动超时"，无法关联到配置错误           │
└─────────────────────────────────────────────────────────────────────────┘
```

**修复方案**：
1. `_load_config` 拆分异常类型，对 `JSONDecodeError` 输出明确错误（含行号）
2. 配置写入使用原子写（`.tmp` + `os.replace`），避免中断后文件损坏
3. 定义 `client_config.schema.json`，加载时校验必要字段（`device.serial`、`llm.model_path`）
4. 安全默认值：`n_gpu_layers` 改为 `-1`（自动），`device.serial` 改为空（不自动连接）

---

## 六、分组修复路线图

基于架构反模式分析，将 97+ 项发现按**修复的架构层**分组，而非按优先级数字排序：

### 第一层：基础设施层（消除反模式根源）

| 反模式 | 涉及问题 | 修复动作 | 影响范围 |
|--------|---------|---------|---------|
| 原生资源隐式管理 | C7, N10, N6, S2/S3 | 为 AndroidRuntime/MaaEndRuntime 定义 `close()` 协议；`_cleanup_partial` 调用 dispose | 消除 4 项 Medium |
| 单例并发无锁 | N-7, N-8, N-9, LLM-06, LLM-08, D10, REC-7, PN-3, N11, PL-3 | 所有单例 `__new__` 加 `threading.Lock`；全局字典加锁 | 消除 6 项 Medium + 5 项 Low |
| 配置管道无校验 | CFG-09/10/11/12, SEC-01, CFG-15 | `_resolve_config_path` 路径约束；`_load_config` 拆分异常；原子写；schema 校验 | 消除 6 项 Medium |

### 第二层：门面/API 层（消除守护进程验证不对称）

| 反模式 | 涉及问题 | 修复动作 | 影响范围 |
|--------|---------|---------|---------|
| 守护进程验证不对称 | D2, D1, C1, SEC-01 | CLI handler 层前置校验；`_handle_shell` 复用白名单；`_force_stop` 参数拆分 | 消除 2 项 High + 2 项 Medium |
| 惰性初始化盲目访问 | 2345-C10, N-3 | `_nav3_walk` 读 `_llm_client_instance`；`_auto_warmup` 排除所有非 llm 命令 | 消除 1 项 High + 1 项 Medium |

### 第三层：可观测性层（消除结构性静默失败）

| 反模式 | 涉及问题 | 修复动作 | 影响范围 |
|--------|---------|---------|---------|
| 结构性静默失败 | W1, W2, N4, D3, NAV-03, N12, CFG-12, D11, D12 | `keyevent()` 在 error 时抛异常；`_vlm_keyevent` 记录 warning；截图失败区分瞬断/真断连；`EntityDatabase.load()` 返回值参与校验 | 消除 1 项 Critical + 7 项 Medium + 3 项 Low |

### 第四层：功能修复层（具体功能缺陷）

| 问题 | 修复动作 | 影响范围 |
|------|---------|---------|
| W1 键位映射 | VLM 移动键映射到游戏支持的 KEYCODE 或 scrcpy 注入 | 消除 1 项 Critical |
| NAV-02 | `to_coords` 排除 `map_id="unknown"` | 消除 1 项 Medium |
| PN-1 | action dict 缺 type 键不再静默回退 DoNothing | 消除 1 项 Medium |
| PL-1/2 | BOM 保护 + 递归 glob | 消除 2 项 Medium |
| REC-1 | OCR Route 1 不再阻止 Route 2/3 回退 | 消除 1 项 Medium |

### 第五层：技术债层（Low/Info 级改进）

| 类别 | 涉及问题 | 修复动作 |
|------|---------|---------|
| 死代码清理 | I18N-1, L1, L2 | 移除 `install_qt_translator`、`_json_dumps` 等死代码 |
| 错误处理增强 | NAV-10, D4-D12, LLM-03/05/07/08/09/10/11 | 裸 except 拆分、超时参数、输入校验 |
| 性能优化 | REC-4/5, REC-12 | 游戏场景检测条件执行、颜色匹配预计算 |
| 可维护性 | CFG-01~05, DOC-02/03/04/05/06, CFG-18 | 模板文件、文档路径同步、schema 定义 |

---

## 七、风险影响评估

若上述反模式不修复，按子系统评估的长期风险：

| 反模式 | 不修复的后果 | 时间尺度 |
|--------|------------|---------|
| 结构性静默失败 | VLM 导航、LLM 连接、实体定位等功能在用户不知情的情况下静默降级，debug 成本极高（需逐层加日志定位） | 即时 |
| 守护进程验证不对称 | 未来重构时可能移除 daemon 层校验（认为"入口已校验"），重开安全漏洞 | 中期 |
| 惰性初始化盲目访问 | 新功能接入时若未遵循"读 property 而非原始属性"约定，产生新的 None 传递 bug | 中期 |
| 原生资源隐式管理 | 长时间运行的任务累积僵尸进程/文件描述符，最终 OOM 或端口耗尽 | 长期 |
| 配置管道无校验 | 用户编辑配置后功能静默失效，反复报告"bug"实为配置错误，增加支持成本 | 即时 |
| 单例并发无锁 | 偶发线程竞态 bug 极难复现（取决于线程调度），可能在特定硬件/负载下才触发 | 长期 |

---

## 八、修复建议优先级（综合视角）

| 优先级 | 项 | 修改量 | 消除问题数 | 理由 |
|--------|----|--------|-----------|------|
| **P0** | C10 一行修复 | 1 行 | 1 High | 修改成本极低，消除 nav3 walk 初始化顺序缺陷 |
| **P0** | W1 失败可见化 | ~10 行 | 1 Critical + 1 Medium | 先让问题可见，再议架构修复；5 行代码改变整个调试体验 |
| **P1** | D1 `_force_stop` 参数拆分 | 1 行 | 1 High | 恢复强制停止功能，修复恢复链路 |
| **P1** | D2 CLI handler 前置校验 | ~5 行 | 1 High（降级为已缓解）+ 1 Medium | daemon 层已有白名单，handler 层复用即可 |
| **P1** | 单例加锁 | ~20 行 | 6 Medium + 5 Low | 消除 11 项并发安全问题 |
| **P1** | `_cleanup_partial` 显式 dispose | ~30 行 | 4 Medium | 消除原生资源泄漏 |
| **P2** | 配置管道加固 | ~50 行 | 6 Medium | schema 校验、路径约束、原子写 |
| **P2** | W1 键位映射架构 | ~100 行 | 1 Critical | 架构级修复，需评估 scrcpy/KEYCODE 方案 |
| **P2** | NAV-02/PN-1/PL-1/2/REC-1 | ~40 行 | 5 Medium | 具体功能缺陷修复 |
| **P3** | 全部 Low/Info | — | 40+ | 死代码清理、错误处理增强、性能优化、文档同步 |

---

## 九、本批不重复提交声明

本批**未**作为"新发现"重复提交任何已在历史报告中记录的具体条目。新增内容仅限：

1. **6 个架构反模式**的识别与因果链分析（反模式 1-6）
2. **W1/C10 配置失败链**的级联失效深度分析（§三、§四）
3. **6 处审计纠正**的终汇总（§一）
4. **分组修复路线图**（§六、§八），按架构层而非优先级数字排序
5. **风险影响评估**（§七），评估不修复各反模式的长期后果

---

## 十、与既往报告的对比

| 维度 | 既往报告（20+ 批次） | 本批（合成审计） |
|------|---------------------|----------------|
| 分析粒度 | 逐文件/逐函数 | 跨文件/跨子系统 |
| 产出内容 | 97+ 项独立发现 | 6 个架构反模式 + 因果链 + 路线图 |
| 修复建议 | 按优先级排序（P0/P1/P2） | 按架构层分组（基础设施/门面/可观测性/功能/技术债） |
| 审计纠正 | 各批次独立纠正 | 终汇总（6 处纠正一览） |
| 覆盖方式 | 文件级全覆盖 | 元分析（对全覆盖结果的综合分析） |

---

*本报告为元分析，未修改任何业务代码。所有结论均经既往报告中引用的源码行号与当前 `main` 分支代码交叉核对。*
