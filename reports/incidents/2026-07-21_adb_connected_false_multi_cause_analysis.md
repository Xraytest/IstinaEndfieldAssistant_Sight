# ADB 连接 true 但 connected 显示 false — 多根因分析

> 报告日期：2026-07-21
> 关联日志：`logs/main.log`（2026-07-21 21:46:03 ~ 22:16:01）
> 关联日志：`3rd-part/maaend/agent/debug/maafw.log`
> 现象：GUI 多次连接 `127.0.0.1:16416`，日志记录 "MaaEnd runtime 连接成功"（ADB 通道已建立），但 GUI 设备页/标准推理页显示"未连接"。

---

## 1. 根因分析

### 1.1 现象链条

调用链（参考 [src/core/service/runtime.py:443-484](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/core/service/runtime.py#L443-L484)）：

```
GUI 点击连接
  └─ cli_bridge.execute("system connect --serial 127.0.0.1:16416")
     └─ CLI 子进程 runtime.connect(serial)
        ├─ MaaEndRuntime.connect()                  # _connect_once 内：
        │   ├─ AdbController.post_connection()       # ADB 通道建立 ✅
        │   ├─ Tasker.bind(resource, controller)     # Tasker 绑定 ✅
        │   ├─ _start_agent()                        # go-service.exe 启动 ✅
        │   └─ self._connected = True                # ← "MaaEnd runtime 连接成功"
        ├─ MaaEndRuntime.load_resource()             # ❌ Resource.Loading.Failed
        │   └─ return False
        └─ return False                              # ← 整体 connect 返回 False
  └─ CLI 输出 status=error
  └─ main_window._on_bridge_command_finished:
     └─ if result.status != "success": maaend_page.set_connected(False)
```

GUI 的 `is_connected` 来自 CLI 命令 `system connect` 的 `status` 字段（参考 [src/gui/pyqt6/main_window.py:598-605](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/gui/pyqt6/main_window.py#L598-L605)）：

```python
if command.startswith("system connect"):
    if result.get("status") == "success":
        self._maaend_page.set_connected(True)
    else:
        self._maaend_page.set_connected(False)
```

而 `MaaEndRuntime._connected` 在 `_connect_once()` 末尾被置为 `True`（[maa_end/runtime.py:390](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/core/service/maa_end/runtime.py#L390)），`load_resource()` 失败时**不会重置**该标志。这导致日志侧显示"MaaEnd runtime 连接成功"（指 ADB/Tasker 通道），但 IstinaRuntime.connect() 整体返回 False，GUI 据此显示 connected=False。

### 1.2 三个独立错误原因（不止一个）

#### 错误原因 A：MaaFW Pipeline 资源加载失败（直接原因）

- **现象**：`[MAIN] Pipeline 资源加载失败或超时 path=C:\...\3rd-part\maaend\resource`，maafw.log 显示 `Resource.Loading.Failed hash=...`
- **直接原因**：`MaaEndRuntime.load_resource()` 中 `self._resource.post_bundle(resource_dir)` 返回失败 job
- **根本原因**：**MaaFW DLL 版本不匹配**
  - 项目自带 DLL：[3rd-part/maaend/agent/maafw/MaaFramework.dll](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/3rd-part/maaend/agent/maafw/MaaFramework.dll)（2,511,360 字节，OLDER）
  - 项目自带 DLL：[3rd-part/maaend/maafw/MaaFramework.dll](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/3rd-part/maaend/maafw/MaaFramework.dll)（2,511,360 字节，OLDER，与 agent/maafw 相同）
  - 用户安装的 maa Python 包自带 DLL：`%APPDATA%\Python\Python312\site-packages\maa\bin\MaaFramework.dll`（2,536,448 字节，NEWER）
  - 项目 [maa_end/runtime.py:84-88](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/core/service/maa_end/runtime.py#L84-L88) 计算了 `_DEFAULT_DLL_DIR`，但**未在主进程 `import maa` 之前设置 `MAAFW_BINARY_PATH` 环境变量**。
  - `maa/__init__.py` 在 import 时执行 `Library.open(path, agent_server=False)`，其中 `path = os.environ.get("MAAFW_BINARY_PATH") or Path(bin/)`。
  - 结果：主 Python 进程（CLI 子进程 + GUI 主进程）`import maa` 时使用 NEWER 版本 DLL，而项目自带的 `3rd-part/maaend/resource` 是给 OLDER 版本 MaaFW 用的，触发 `Resource.Loading.Failed`。
- **附加因素**：`3rd-part/maaend/cache/MaaEnd-win-x86_64-v2.18.0.zip.1.downloading`（2.6MB）显示存在未完成的 MaaEnd 资源下载，资源版本可能不一致。
- **代码位置**：[maa_end/runtime.py:608-634](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/core/service/maa_end/runtime.py#L608-L634)

#### 错误原因 B：CLI 子进程崩溃 `exit_code=-1073741510`（独立错误）

- **现象**：`[GUI] CLI 进程崩溃 exit_code=-1073741510 crash_count=1`，反复出现于 21:46:51 / 22:13:38 / 22:16:01
- **直接原因**：`-1073741510 = 0xC0000135 = STATUS_DLL_NOT_FOUND`，CLI 子进程加载 DLL 失败导致进程级崩溃
- **根本原因**：
  - [cli_bridge.py:231-239](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/gui/pyqt6/cli_bridge.py#L231-L239) 通过 `QProcess.start(self._python_path, ...)` 启动 CLI 子进程，**未调用 `setProcessEnvironment()` 或 `QProcessEnvironment` 注入 `MAAFW_BINARY_PATH`**
  - 子进程 `import maa` 时使用用户 Roaming site-packages 的 NEWER `bin/MaaFramework.dll`
  - NEWER DLL 可能依赖系统未安装的 Visual C++ Runtime 或与 OLDER MaaEnd 资源不兼容，加载时触发进程级崩溃
  - `try/except ImportError` 只能捕获 Python 级异常，无法拦截 DLL 加载导致的进程崩溃
- **代码位置**：[cli_bridge.py:220-249](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/gui/pyqt6/cli_bridge.py#L220-L249)

#### 错误原因 C：adbutils API 不兼容（独立错误，非阻断）

- **现象**：`[ADB] adbutils 获取设备列表失败，回退 subprocess error='AdbClient' object has no attribute 'devices'`，反复出现
- **直接原因**：[adb_manager.py:62](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/core/capability/device/adb_manager.py#L62) 调用 `adb.devices()`
- **根本原因**：项目使用 `adbutils 2.12.0`，该版本已将 `AdbClient.devices()` 方法移除，改为 `device_list()`（同时提供 `iter_device()` / `list()`）。已通过运行时验证：
  ```
  >>> import adbutils
  >>> c = adbutils.AdbClient(host='127.0.0.1', port=5037)
  >>> hasattr(c, 'devices')       # False
  >>> hasattr(c, 'device_list')   # True
  ```
- **影响**：非阻断 — [adb_manager.py:65-78](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/core/capability/device/adb_manager.py#L65-L78) 已实现 subprocess fallback（`adb devices` 命令），`get_devices()` 仍能返回结果。但每次刷新设备列表都打 WARNING 日志，污染日志通道，且 `shell()`/`screencap()` 中调用 `adbutils.AdbClient` 的代码路径仍可能因 API 变更而走 fallback。
- **代码位置**：[adb_manager.py:55-81](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/core/capability/device/adb_manager.py#L55-L81)、`adb_manager.py:90-100`、`adb_manager.py:108-118`

### 1.3 三者关系

| 错误 | 是否阻断 connect | 是否阻断 GUI 显示 connected | 触发频率 |
|------|------------------|---------------------------|---------|
| A. 资源加载失败 | 是（load_resource 返回 False） | 是（CLI status=error → set_connected(False)） | 每次连接必现 |
| B. CLI 进程崩溃 | 是（CLI 整体崩溃，连接命令未执行完） | 是（errorOccurred 信号触发，crash_count 累加） | 间歇性（21:46 / 22:13 / 22:16 三次） |
| C. adbutils API | 否（有 subprocess fallback） | 否（仅噪音日志） | 每次刷新设备列表 |

A 与 B 互为独立但相互掩盖：B 偶发崩溃时根本到不了 A；A 在 B 未发生时主导失败。C 始终在后台产生噪音。

---

## 2. 修改方案

### 方案 A：修复 MaaFW DLL 版本不匹配（根因 A）

**位置 1**：[src/core/service/maa_end/runtime.py](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/core/service/maa_end/runtime.py) 顶部（在 `import maa.*` 之前）

```python
# 在 _DEFAULT_DLL_DIR 计算后立即写入 os.environ，确保后续 import maa 使用项目自带 DLL
import os as _os
if _DEFAULT_DLL_DIR is not None and _os.environ.get("MAAFW_BINARY_PATH") is None:
    _os.environ["MAAFW_BINARY_PATH"] = str(_DEFAULT_DLL_DIR.resolve())
```

**位置 2**：[src/gui/pyqt6/cli_bridge.py](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/gui/pyqt6/cli_bridge.py) `_start_interactive_process`

```python
# QProcess 启动前注入环境变量
from PySide6.QtCore import QProcessEnvironment  # 或 PyQt6.QtCore
env = QProcessEnvironment.systemEnvironment()
env.insert("MAAFW_BINARY_PATH", str(_DEFAULT_DLL_DIR.resolve()))  # 需 import
self._process.setProcessEnvironment(env)
self._process.start(cmd[0], cmd[1:])
```

或更简单：在 GUI 主进程启动早期（`main.py`）`os.environ["MAAFW_BINARY_PATH"] = ...`，子进程自动继承。

### 方案 B：修复 CLI 子进程崩溃（根因 B）

方案 A 注入 `MAAFW_BINARY_PATH` 后，CLI 子进程 `import maa` 将使用项目自带 OLDER DLL，与 bundled resource 匹配，崩溃应消失。如仍崩溃，需进一步排查：

- 用 `dumpbin /dependents` 或 Dependencies.exe 检查 OLDER `MaaFramework.dll` 依赖的 DLL 是否齐全
- 确认 `3rd-part/python/python.exe` 启动时 PATH 是否包含 `3rd-part/maaend/agent/maafw/`
- 必要时在 `_start_interactive_process` 中设置 `env.insert("PATH", maaend_agent_maafw_dir + ";" + env.value("PATH"))`

### 方案 C：修复 adbutils API 不兼容（根因 C）

**位置**：[src/core/capability/device/adb_manager.py:55-81](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/core/capability/device/adb_manager.py#L55-L81)

```python
def get_devices(self) -> List[ADBDeviceInfo]:
    devices: List[ADBDeviceInfo] = []
    try:
        import adbutils
        adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
        # adbutils >= 2.0 使用 device_list()，< 2.0 使用 devices()
        device_iter = getattr(adb, "device_list", None) or getattr(adb, "devices", None)
        if device_iter is None:
            raise RuntimeError("adbutils AdbClient 无 device_list/devices 方法")
        for device in device_iter():
            devices.append(ADBDeviceInfo(serial=device.serial, state=device.state))
        return devices
    except Exception as e:
        self._logger.warning(LogCategory.ADB, "adbutils 获取设备列表失败，回退 subprocess", error=str(e))
    # ... subprocess fallback 保持不变
```

`shell()` 和 `screencap()` 中 `adb.device(serial=...)` 调用 API 未变，无需修改。

### 方案 D：让 `MaaEndRuntime.connected` 与 IstinaRuntime.connect 语义一致（可选）

`_connected` 标志在 `load_resource()` 失败时仍为 True，可能导致 `runtime.connected` 属性与 GUI 显示不一致。建议在 `load_resource()` 失败路径补一行 `self._connected = False`：

```python
# maa_end/runtime.py:620-622
if not self._wait_job(job, timeout_s=60.0):
    self.logger.error(LogCategory.MAIN, "Pipeline 资源加载失败或超时", path=str(resource_dir))
    self._connected = False  # ← 新增：资源加载失败视为整体未连接
    return False
```

---

## 3. 影响面

| 修改 | 涉及文件 | 涉及函数 / 信号 / 调用点 |
|------|---------|------------------------|
| A1（runtime.py 注入 env） | `src/core/service/maa_end/runtime.py` | 模块顶层副作用：`import maa.*` 之前执行；影响所有 `MaaEndRuntime` 实例；影响所有 `from core.service.maa_end.runtime import ...` 的下游模块 |
| A2（cli_bridge.py 注入 env） | `src/gui/pyqt6/cli_bridge.py` | `_start_interactive_process`；影响所有 CLI 子进程；与 `errorOccurred` / `finished` 信号解耦 |
| A2（main.py 启动注入） | `src/gui/pyqt6/main.py` | 启动早期；影响 GUI 主进程 + 所有子进程 |
| B（CLI 崩溃排查） | `src/gui/pyqt6/cli_bridge.py` | `_on_error` / `_on_finished` 的 `crashed` 分支；`processCrashed` 信号；`MainWindow._on_cli_crashed` 自动重连逻辑 |
| C（adbutils 兼容） | `src/core/capability/device/adb_manager.py` | `get_devices()`；调用方：`device_settings_page._refresh_device_list`、`adb_manager._first_device_serial`、`adb_manager.shell`、`adb_manager.screencap` |
| D（_connected 重置） | `src/core/service/maa_end/runtime.py` | `load_resource`；影响 `IstinaRuntime.connected` 属性、`runtime.connected` 检查点（如 `navigator` 中的截图源选择 `maaend.screenshot if maaend.connected else android.screenshot`） |

**调用链影响范围**：
- `IstinaRuntime.connect` → `MaaEndRuntime.connect` → `_connect_once` → `load_resource`
- `IstinaRuntime.connected` 属性 → `MaaEndRuntime.connected` 属性 → `_connected` 标志
- `MainWindow._on_bridge_command_finished("system connect", result)` → `set_connected(bool)` → `connection_changed` 信号 → `device_settings_page` / `maaend_control_page` UI 更新

---

## 4. 非期待变化

### 4.1 方案 A 注入 `MAAFW_BINARY_PATH` 的副作用

- **DLL 冲突**：若用户机器上其它 Python 项目依赖 user site-packages 的 NEWER maa 包，IEA 启动后修改 `os.environ["MAAFW_BINARY_PATH"]` 不影响其它进程（环境变量不跨进程传播），仅影响 IEA 自身子进程。✅ 安全。
- **DLL 仍找不到**：若 OLDER DLL 依赖的系统 DLL（VC++ Runtime 等）未安装，注入 env 后仍可能崩溃，需进一步用 Dependencies.exe 排查。
- **回退**：删除 `os.environ["MAAFW_BINARY_PATH"]` 即可恢复使用 NEWER DLL。

### 4.2 方案 B 修改 PATH 的副作用

- **PATH 顺序污染**：将 `maafw/` 目录 prepend 到 PATH 可能让其它依赖 MaaFW DLL 的程序加载到 OLDER 版本。建议优先用 `MAAFW_BINARY_PATH` 环境变量（MaaFW 专用），不修改 PATH。
- **回退**：还原 cli_bridge.py 的 `setProcessEnvironment` 调用。

### 4.3 方案 C 修改 adbutils 调用的副作用

- **兼容性**：`getattr(adb, "device_list", None) or getattr(adb, "devices", None)` 同时兼容 adbutils 1.x 和 2.x，无回退风险。
- **回退**：还原为 `adb.devices()`，但会复现 WARNING 噪音。

### 4.4 方案 D 重置 `_connected` 的副作用

- **navigator 截图源切换**：[runtime.py:384](file:///c:/Users/cheng/Documents/ArkStudio/IstinaAI/IstinaEndfieldAssistant_Sight/src/core/service/runtime.py#L384) `screenshot_fn = maaend.screenshot if (maaend and maaend.connected) else android.screenshot`。若 `load_resource` 失败后 `_connected = False`，navigator 会回退到 `android.screenshot`（依赖 scrcpy，启动慢），可能影响 VLM 导航前几步。但 `load_resource` 失败时本就无法执行任务（无 pipeline），navigator 不会被调用，影响可忽略。
- **回退**：删除新增的 `self._connected = False` 行。

### 4.5 综合回退策略

1. 优先实施方案 A + 方案 C，方案 B 作为方案 A 的从属验证（A 实施后 B 大概率自愈）。
2. 方案 D 可选，仅作为语义一致性加固，不解决核心问题。
3. 若方案 A 实施后仍出现 CLI 崩溃，启用方案 B 的 PATH 注入。
4. 修复后需做 5 次连续连接验证（参考 project_memory 中的"任务列表页导航必须成功 5 次连续验证"约定），确认 GUI 显示 connected=True 且无 CLI 崩溃日志。

---

## 5. 验证清单

- [ ] 实施方案 A 后，启动 GUI → 设备页点击连接 → 日志应出现 `Pipeline 资源加载成功 path=...resource`（而非 `失败或超时`）
- [ ] `maafw.log` 应出现 `Resource.Loading.Succeeded`（或类似成功事件），不再出现 `Resource.Loading.Failed`
- [ ] GUI 设备页 / 标准推理页应显示"已连接"，`is_connected=True`
- [ ] 实施方案 C 后，`main.log` 不再出现 `adbutils 获取设备列表失败` WARNING
- [ ] 5 次连续连接验证：每次均成功，无 CLI 崩溃（`exit_code=-1073741510` 不再出现）
- [ ] 检查 `3rd-part/maaend/cache/` 中 `.downloading` 文件是否需要清理或重新下载完整 MaaEnd 资源
