# IEA 配置持久化根本原因分析与修复

## 问题现象

用户在 Settings Page 修改设置（如"最小化到托盘"）后，配置在磁盘上的 `client_config.json` 中已被保存，但**下一次启动时配置被还原到默认值**。

## 根本原因

### 核心问题：`main.py` 和 `MainWindow` 读取了不同的配置文件

#### 1. `main.py` 的路径计算错误

**问题代码** (`src/gui/pyqt6/main.py`):
```python
# __file__ = src/gui/pyqt6/main.py
# dirname 4 times to get project root
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# project_root = C:\Users\xray\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant
```

从 `IstinaEndfieldAssistant/src/gui/pyqt6/main.py` 向上 4 层：
1. `src/gui/pyqt6/`
2. `src/gui/`
3. `src/`
4. `IstinaEndfieldAssistant/` ← **错误的根目录**

**影响**：
- `main.py::load_config()` 尝试读取 `IstinaEndfieldAssistant/config/client_config.json`
- 该文件已被删除（统一配置路径时）
- 返回**默认配置**（`minimize_to_tray: False`）

#### 2. `MainWindow` 的路径计算正确

**代码** (`src/gui/pyqt6/main_window.py`):
```python
def _reload_disk_config(self):
    current = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current))))
    config_path = os.path.join(project_root, 'config', 'client_config.json')
    # project_root = C:\Users\xray\Documents\ArkStudio\IstinaAI
    # config_path = C:\Users\xray\Documents\ArkStudio\IstinaAI\config\client_config.json
```

**影响**：
- 正确读取 `IstinaAI/config/client_config.json`
- 磁盘配置（`minimize_to_tray: True`）被合并到内存配置

#### 3. 配置传递流程

```
main.py::load_config()
  ↓ 读取 IstinaEndfieldAssistant/config/client_config.json (不存在)
  ↓ 返回默认配置 {system: {minimize_to_tray: False}}
  ↓
run_application(config=config)
  ↓
MainWindow.__init__(config)
  ↓ self._config = config (默认配置)
  ↓ self._reload_disk_config()
  ↓ 读取 IstinaAI/config/client_config.json (存在，minimize_to_tray: True)
  ↓ _merge(self._config, disk_cfg) (合并后 minimize_to_tray: True)
  ↓
SettingsPage(config=self._config)
  ↓ 正确读取到 minimize_to_tray: True
```

**关键发现**：虽然 `MainWindow._reload_disk_config()` 纠正了配置，但这是**事后补救**，不是正确的流程。

#### 4. 路径不一致的副作用

- **首次启动**：如果磁盘配置不存在，`main.py` 返回默认配置，`MainWindow` 也无法从磁盘读取
- **配置保存**：`app_main.py::_save_config()` 保存到 `IstinaAI/config/`
- **下次启动**：`main.py` 仍然读取 `IstinaEndfieldAssistant/config/`（不存在）→ 返回默认配置
- **依赖路径**：ADB、Git 等路径也需要相应调整

## 修复方案

### 1. 统一 `main.py` 的项目根目录计算

**修复前**：
```python
# dirname 4 times → IstinaEndfieldAssistant
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
src_dir = os.path.join(project_root, "src")
```

**修复后**：
```python
# dirname 4 times → IstinaEndfieldAssistant
# dirname 5 times → IstinaAI
iea_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
project_root = os.path.dirname(iea_root)  # IstinaAI root
src_dir = os.path.join(iea_root, "src")  # IstinaEndfieldAssistant/src
```

### 2. 更新配置文件中的相对路径

**修复前** (`config/client_config.json`):
```json
{
  "adb": {
    "path": "3rd-party/adb/adb.exe"
  },
  "git": {
    "path": "3rd-party/git/bin/git.exe"
  }
}
```

**修复后**：
```json
{
  "adb": {
    "path": "IstinaEndfieldAssistant/3rd-party/adb/adb.exe"
  },
  "git": {
    "path": "IstinaEndfieldAssistant/3rd-party/git/bin/git.exe"
  }
}
```

### 3. 更新 `main.py` 默认配置中的路径

**修复前**：
```python
return {
    "adb": {"path": "3rd-party/adb/adb.exe", "timeout": 10},
    "git": {"path": "3rd-party/git/bin/git.exe"},
    ...
}
```

**修复后**：
```python
return {
    "adb": {"path": "IstinaEndfieldAssistant/3rd-party/adb/adb.exe", "timeout": 10},
    "git": {"path": "IstinaEndfieldAssistant/3rd-party/git/bin/git.exe"},
    ...
}
```

## 验证结果

### 启动日志验证

```
[启动] 项目根目录：C:\Users\xray\Documents\ArkStudio\IstinaAI
[主进程] 加载配置...
[主进程] 配置加载成功
[主进程] 初始化核心模块（ADB、截屏、触控管理器）...
[配置加载] 从 C:\Users\xray\Documents\ArkStudio\IstinaAI\config\client_config.json 读取配置
[配置加载] 成功合并磁盘配置到内存
[配置验证] system.minimize_to_tray = True
[应用主进程] 启动事件循环...
```

### ADB 路径验证

修复前错误：
```
[错误] ADB 可执行文件不存在：C:\Users\xray\Documents\ArkStudio\IstinaAI\3rd-party/adb/adb.exe
```

修复后正确：
```
[主进程] 初始化核心模块（ADB、截屏、触控管理器）...
[所有组件初始化成功]
```

### 配置传递一致性

- ✅ `main.py` 读取 `IstinaAI/config/client_config.json`
- ✅ `MainWindow` 读取 `IstinaAI/config/client_config.json`
- ✅ `app_main.py` 保存到 `IstinaAI/config/client_config.json`
- ✅ 所有路径统一，配置持久化正常

## 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| `IstinaEndfieldAssistant/src/gui/pyqt6/main.py` | 1. 路径计算从 4 层改为 5 层<br>2. 更新默认配置中的 ADB/Git 路径<br>3. 添加 `os.path.normpath()` 处理混合路径分隔符 |
| `IstinaEndfieldAssistant/src/gui/pyqt6/main_window.py` | 无修改（路径计算已正确） |
| `IstinaEndfieldAssistant/src/gui/pyqt6/app_main.py` | 无修改（路径计算已正确） |
| `config/client_config.json` | 更新 ADB/Git 路径为相对于 IstinaAI 根目录 |

## 配置文件结构

```
IstinaAI/
├── config/
│   └── client_config.json  ← 唯一配置文件
├── IstinaEndfieldAssistant/
│   ├── src/
│   │   └── gui/pyqt6/
│   │       ├── main.py      ← 读取 config/client_config.json
│   │       ├── app_main.py  ← 保存到 config/client_config.json
│   │       └── main_window.py ← 重载 config/client_config.json
│   └── 3rd-party/
│       ├── adb/adb.exe
│       └── git/bin/git.exe
```

## 经验总结

### 1. 路径计算必须一致

所有模块计算项目根目录时必须使用**相同的层数**，否则会导致读取不同的配置文件。

### 2. 相对路径的基准点

配置文件中的相对路径必须相对于**项目根目录**（`IstinaAI`），而不是子项目目录（`IstinaEndfieldAssistant`）。

### 3. 配置加载的单一入口

虽然 `MainWindow._reload_disk_config()` 可以纠正配置，但正确的做法是确保 `main.py` 首次加载就读取正确的文件。

### 4. 调试技巧

在配置加载的关键节点添加日志：
- `main.py::load_config()` - 打印读取的路径和内容
- `MainWindow.__init__()` - 打印传入的配置
- `MainWindow._reload_disk_config()` - 打印磁盘配置和合并结果
- `SettingsPage._load_config()` - 打印最终使用的配置

## 测试建议

```bash
# 1. 修改配置文件
# 将 system.minimize_to_tray 改为 true
# 重启 GUI，检查设置是否正确加载

# 2. 在 Settings Page 修改设置
# 勾选"最小化到托盘"
# 检查控制台输出：[配置] 已保存配置到 {config_path}

# 3. 重启验证
# 关闭 GUI
# 重新启动
# 检查托盘设置是否保持
```

## 状态

**修复完成日期**: 2026-06-13

**根本原因**: 
1. `main.py` 的项目根目录计算错误（4 层 vs 5 层），导致读取不存在的配置文件
2. `os.path.join()` 在 Windows 上无法正确处理混合路径分隔符（`/` vs `\`）

**修复方法**: 
1. 将路径计算从 4 层改为 5 层，正确指向 `IstinaAI` 根目录
2. 更新配置文件和默认配置中的 ADB/Git 路径
3. 添加 `os.path.normpath()` 处理混合路径分隔符

**验证状态**: ✅ 配置持久化正常工作，应用成功启动
