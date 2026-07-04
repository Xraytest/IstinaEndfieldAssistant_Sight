# 修改报告：GUI/CLI 代码传递链重构

> 注意：本报告为历史重构设计文档。报告中提及的 `InferenceManager`、`GUIClient`、`AgentExecutor`、`ExplorationEngine` 等 LLM/VLM/云端相关组件在后续清理中已被移除，当前架构已切换为纯 MaaEnd 自动化模式。

## 1. 现状分析

### 1.1 GUI 端到端代码传递链

```
src/gui/pyqt6/main.py
  -> ADBDeviceManager / ScreenCapture / TouchManager / InferenceManager
  -> GUIClient / create_agent_executor()
  -> run_application()
  -> MainWindow(agent_executor, gui_client, screen_capture, touch_executor, inference_manager, adb_manager, maaend_runtime)
    -> pages/
      - AgentPage(agent_executor, inference_manager)
      - PrtsFullIntelligencePage(agent_executor, screen_capture, touch_executor, inference_manager)
      - MaaEndPage(bridge)
      - DeviceSettingsPage(device_manager, config)
      - MaaEndControlPage(runtime)
```

**核心问题**
- GUI 直接持有并初始化所有核心组件
- 每个 page 直接耦合底层实现
- 无法被 CLI 复用

### 1.2 CLI 代码传递链（重构后）

```
3rd-part\python\python.exe src/cli/istina.py
  -> build_parser(): 只负责参数解析
  -> CLIDispatch(runtime).dispatch(args): 命令分类路由
  -> src/cli/handlers.py: 各命令处理函数（_handle_*）
  -> IstinaRuntime.execute(command, params): 统一执行入口
  -> AndroidRuntimeClient -> 跨进程守护进程(_Daemon)
  -> MaaEndRuntime: 任务/预设/截图
```

**当前状态**
- 统一入口 `src/cli/istina.py` 保持，但 main() 只做解析+路由
- 业务逻辑全部移到 `src/cli/handlers.py`
- 不再拆分 `device_cli.py` / `scenario_cli.py` / `system_cli.py` / `gpu_cli.py`
- 所有 CLI 操作通过 `IstinaRuntime` 统一执行，消除重复初始化

---

## 2. 关键发现：安卓交互层可抽象为进程内单例（线程安全 + socket IPC）

当前代码里，设备能力分布在 `ADBDeviceManager` 与 `TouchManager`，且截图日志显示已有 scrcpy server 启动痕迹，但没有可复用的 `ScrcpyCore` 单例类。

因此本次重构采用更直接的封装：

- 新建 `android_runtime.py`，把 `ADBDeviceManager + TouchManager` 封装为按 serial 进程内单例的独立实例
- 通过 Unix domain socket / TCP localhost fallback 提供 JSON-RPC 接口
- 截图等二进制数据通过 mmap 文件映射传递
- 首次调用时自动启动独立守护进程 `_Daemon`，同一 serial 串行访问
- 内建 `_ScrcpySession`：实现 scrcpy v2.7 `tunnel_forward` 协议，通过 `av.CodecContext` 实时解码 H.264/HEVC/AV1 视频流，缓存最新帧用于截图

---

## 3. 重构目标

1. 分析现有 GUI 端到端代码传递链（已完成，见 1.1）
2. 重构 CLI，调用共享代码链而不是单独创建
3. GUI 与代码实现断开，改为 GUI 调用 CLI
4. scrcpy+adb 封装为 AndroidRuntime 进程内单例，通过 _Daemon 守护线程分离执行
5. 强制新架构，无回滚窗口，立即切断旧路径
6. 同一 serial 串行访问，状态绝对一致
7. 自动化执行，仅最终报告，仅手动验证

---

## 4. 实施方案

### Phase 1: 提取安卓交互独立实例层（进程内单例 + socket IPC）

新建 `src/core/capability/device/android_runtime.py`，把 `ADBDeviceManager + TouchManager` 封装为按 serial 跨进程单例的独立实例：

```python
class AndroidRuntime:
    """跨进程单例客户端连接器，向守护进程发 JSON-RPC 请求。"""

    def __init__(self, serial: str, adb_path: str = "3rd-part/adb/adb.exe"):
        self._serial = serial
        self._adb_path = adb_path
        self._daemon: Optional[_Daemon] = None

    # JSON-RPC 委托给守护进程
    def screenshot(self, serial=None): ...
    def tap(self, x, y, serial=None): ...
    def swipe(self, x1, y1, x2, y2, duration_ms=300, serial=None): ...
    def shell(self, cmd, serial=None): ...
```

**关键设计**
- 进程内单例（线程安全），通过 Unix domain socket 保证同一 serial 只创建一个后端实例
- Socket 路径动态生成（根据设备 serial），避免冲突；Windows 回退到 TCP localhost，端口策略为 `50000 + hash(serial) % 10000`
- 使用 JSON-RPC 协议进行 IPC 通信
- 守护线程 `_Daemon` 运行（同一进程内），首次 CLI 调用时自动启动
- 同一 serial 串行访问，守护进程内用 `threading.Lock` 保证状态一致
- 长连接保活，GUI 启动时建立连接，退出时显式关闭
- 截图等二进制数据通过 mmap 文件映射内存共享传递，减少磁盘 IO

### Phase 2: 提取统一运行时层

新建 `src/core/service/runtime.py`，封装所有核心组件的初始化：

```python
class IstinaRuntime:
    """共享运行时 — GUI 和 CLI 的统一初始化入口"""

    def __init__(self):
        self.config = self._load_config()
        self.android = None
        self.maaend = None

    def execute(self, command: str, params: dict) -> Any:
        """统一执行入口 — 根据 command 路由到具体方法"""
        ...
```

**关键设计**
- 采用统一 Command 模式，只暴露 `execute(command, params)` 统一入口
- 配置来源：固定从 `config/client_config.json` 加载
- 每次操作前热加载，GUI/CLI 行为一致
- 生命周期：每个 CLI 子进程创建自己的 `IstinaRuntime`，退出时销毁
- 通信路径：CLI 子进程 -> IstinaRuntime -> AndroidRuntimeProxy -> AndroidRuntime -> _Daemon

### Phase 3: 重构 CLI 调用共享层

统一入口保持不变，但改为“只解析、不处理”：

```python
# src/cli/istina.py
def main(argv=None):
    args = parser.parse_args(argv)
    runtime = IstinaRuntime()
    dispatch = CLIDispatch(runtime)
    result = dispatch.dispatch(args)
    print(_json_dumps(result))
    return 0 if result.get("status") == "success" else 1
```

```python
# src/cli/handlers.py
class CLIDispatch:
    def dispatch(self, args):
        if args.command == "system": return self._handle_system(args)
        if args.command == "daily": return self._handle_daily(args)
        ...
```

**结果返回契约**：所有 CLI 子命令输出结构化 JSON，GUI 解析后更新 UI。

**命令路由**：GUI 只调用 `src/cli/istina.py` 一个入口，通过子命令参数路由到不同功能。

**实际调整**：保持统一 `istina.py` 入口，不拆分 `device_cli.py` / `scenario_cli.py` / `system_cli.py` / `gpu_cli.py`。

### Phase 4: 断开 GUI 直接依赖（强制新架构，无回滚窗口）

修改以下文件，GUI 不再直接持有核心组件：

- `src/gui/pyqt6/main_window.py` — 不再持有核心组件
- `src/gui/pyqt6/pages/agent_page.py` — 只保留 `bridge`
- `src/gui/pyqt6/pages/maaend_control_page.py` — 只保留 `bridge`
- `src/gui/pyqt6/pages/device_settings_page.py` — 只保留 `bridge`
- `src/gui/pyqt6/pages/prts_full_intelligence_page.py` — 只保留 `bridge`

新增 `src/gui/pyqt6/cli_bridge.py` — GUI 侧 CLI 调用桥接器：
- 通过 `QProcess` 调用 `src/cli/istina.py`
- 捕获 stdout JSON
- 将 JSON 结果转换为 Qt 信号/槽更新 UI
- 子进程崩溃时自动重启，在 GUI 日志部分展示
- 连续崩溃达到 5 次后在 GUI 显示提醒，用户可选择重试或忽略

**强制新架构**：立即切断旧路径，所有 GUI 操作必须通过 CLI 子进程。无回滚窗口。

---

## 5. LLM 模块嵌入（llama.cpp 本地推理）

### 设计原则
- **最小侵入**：在现有 `IstinaRuntime` 中增加 LLM 能力，不破坏 MaaEnd/规则引擎主链路
- **默认启用**：GUI/CLI 启动时自动预热 `llama-server.exe`，退出时关闭
- **独立可调用**：既支持通过 `LlmClient` 直接调用，也通过 CLI 子命令暴露
- **CUDA 优先**：默认启用 GPU 卸载，失败时自动回退 CPU

### 新建文件
| 文件 | 说明 |
|---|---|
| `src/core/capability/llm/__init__.py` | 包标记 |
| `src/core/capability/llm/runtime.py` | `LlamaServerRuntime`：管理 `llama-server.exe` 常驻进程，负责启动/停止/健康检查 |
| `src/core/capability/llm/client.py` | `LlmClient`：封装 OpenAI 兼容 API，提供 `chat(prompt) -> output` 接口 |

### 配置设计
`config/client_config.json` 新增段：
```json
"llm": {
  "enabled": true,
  "model_path": "models/LLM/Qwen3.5-4B-UD-Q4_K_XL.gguf",
  "port": 9998,
  "n_gpu_layers": 999,
  "context_size": 32768,
  "threads": 12,
  "temperature": 0.3,
  "flash_attention": "on",
  "kv_cache_type": "q8_0",
  "batch_size": 2048,
  "ubatch_size": 1024,
  "no_repack": true,
  "no_cont_batching": true
}
```

### 调用方式
- **CLI**：`3rd-part\\python\\python.exe src/cli/istina.py llm prompt "分析当前页面"`
- **GUI/代码**：`LlmClient().chat("prompt")`
- **CLI Bridge**：`self._bridge.execute("llm prompt", {"text": "..."})`

### 启动策略
- 可执行文件：`3rd-part/llama-cpp/llama-server.exe`
- 默认参数：`-ngl 999`、`--port 9998`、`--api`
- 健康检查：启动后等待 `/health` 返回 ready（最长 60 秒）
- 回退：CUDA 初始化失败时自动追加 `--n-gpu-layers 0` 重启

---

## 6. 关键文件清单

### 新建文件
| 文件 | 说明 |
|---|---|
| `src/core/capability/device/android_runtime.py` | Android 交互独立实例层，进程内单例（线程安全），Unix domain socket（动态路径）+ JSON-RPC + mmap 内存共享，守护线程 |
| `src/core/service/runtime.py` | 统一运行时层，Command 模式 API，包含 MaaEndRuntime |
| `src/core/service/__init__.py` | 导出 `IstinaRuntime` |
| `src/cli/handlers.py` | 独立命令处理函数，istina.py main() 只做解析+路由 |
| `src/gui/pyqt6/cli_bridge.py` | GUI 调用 CLI 的桥接器，subprocess + JSON 结果解析，自动重启 + 5次崩溃后提醒 |
| `src/core/capability/element_recognition/scene_service.py` | `SceneUnderstandingService`：场景理解服务，集成 OCR/模板匹配/YOLO 分析 |

### 修改文件
| 文件 | 变更 |
|---|---|
| `src/cli/istina.py` | main() 只解析命令并委托给 `CLIDispatch`，新增 `llm` 子命令 |
| `src/core/service/runtime.py` | 封装 `AndroidRuntimeProxy`、`MaaEndRuntime`、`LlamaServerRuntime`、`LlmClient`、`SceneUnderstandingService`，提供统一 `execute()` 入口 |
| `src/gui/pyqt6/main_window.py` | 移除核心组件创建，只保留 `CLIBridge` |
| `src/gui/pyqt6/pages/*` | 移除直接核心组件引用，只保留 `bridge` 调用 |

---

## 7. 验证计划

1. **CLI 冒烟测试**: `3rd-part\\python\\python.exe src/cli/istina.py device info` 验证共享层可用
2. **AndroidRuntime 单例与 socket 通信测试**: 验证同一 serial 只创建一个后端实例，JSON-RPC + mmap 传输正常
3. **Unix domain socket 通信测试**: 验证 JSON-RPC 协议正常，mmap 内存共享截图数据正常
4. **GUI 启动测试**: 启动 GUI，验证各页面通过子进程调用 CLI 能正常返回 JSON 结果
5. **设备操作测试**: 在 GUI 的 Device Settings 页面执行截图/触控操作
6. **标准流测试**: 在 GUI 的 MaaEnd 页面执行任务队列
7. **错误恢复测试**: 模拟 CLI 子进程崩溃，验证 GUI 自动重启并在日志展示，连续5次崩溃后提醒，用户可选择重试或忽略
8. **热加载测试**: 修改配置文件，验证 CLI 能正确读取新配置
9. **串行访问测试**: 验证同一 serial 的并发请求被正确排队处理
10. **LLM 启动测试**: 启动 GUI/CLI，验证 `llama-server.exe` 进程存在，健康检查通过
11. **LLM API 调用测试**: CLI `llm prompt` 返回正常文本，GUI 通过 `CLIBridge` 调用 LLM 并显示结果
12. **LLM CUDA 回退测试**: 无 CUDA 环境时自动降级到 CPU 模式，确认启动成功
13. **LLM 关闭清理测试**: 退出 GUI/CLI，确认 `llama-server.exe` 进程结束

---

## 8. 预期效果

- `AndroidRuntime` 作为进程内单例，scrcpy+adb 分离式调用，避免重复创建
- CLI 模块复用同一个 `IstinaRuntime`，消除重复初始化
- GUI 与核心实现完全解耦，GUI 只负责展示和调度 CLI
- 强制新架构，无回滚窗口，代码库保持唯一真相源
- 同一 serial 串行访问，状态绝对一致
- 后续维护只需修改 `runtime.py` 和 `android_runtime.py` 两处，GUI 和 CLI 自动受益

---

**本方案已按实际实现更新。**
