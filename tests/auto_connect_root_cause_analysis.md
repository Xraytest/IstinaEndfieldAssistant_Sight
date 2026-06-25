# 启动时自动连接问题根因分析

## 问题现象
- 在设备设置页面勾选 **"启动时自动连接"** 后，重启程序没有自动连接上次设备
- 用户感知：选择没有保存/持久化

## 根因分析

### 1. 持久化机制本身正常
`_on_auto_connect_changed` 和 `_save_config` 从项目初始提交（`edc133d`）就已存在：

```python
# device_settings_page.py
def _on_auto_connect_changed(self, state):
    enabled = state == Qt.CheckState.Checked
    self._config.setdefault('device', {})
    self._config['device']['auto_connect'] = enabled
    self.settings_changed.emit(self._config)  # 触发持久化

# app_main.py
main_window.settings_changed.connect(_save_config)
```

勾选复选框后，配置确实会写入 `config/client_config.json`。

### 2. 真正的三个缺陷

| 缺陷 | 表现 | 根因 |
|------|------|------|
| **保存值相反** | 勾选实际保存 `False`，取消勾选保存 `True` | Qt `stateChanged` 信号发射的是**变化前的旧状态**，槽函数错误地将 `state` 当作新状态使用 |
| **启动时不生效** | 重启后不自动连接 | `main.py` 启动流程从未读取 `auto_connect` 配置 |
| **UI 显示 stale** | 扫描/切换页面后"上次连接"不更新 | `_scan_devices` 和页面切换后未刷新设备信息 |

### 3. 为什么没能保存（核心发现）

**Qt 的 `QCheckBox.stateChanged` 信号发射的是「旧状态」**，不是新状态。

```python
# 错误实现（项目初始代码就有）
def _on_auto_connect_changed(self, state):
    enabled = state == Qt.CheckState.Checked  # state 是旧状态！
    ...

# 用户勾选复选框时的执行流程：
# 1. setChecked(True) 触发 stateChanged 信号
# 2. 信号参数 state = Qt.CheckState.Unchecked (0)  ← 变化前的旧状态
# 3. enabled = False
# 4. auto_connect 被保存为 False  ← 与用户意图相反！
```

**结论：配置不是"没保存"，而是"保存了反值"。**

由于：
1. 保存的是反值，重启后 `main.py` 读取到 `False`，不执行自动连接
2. UI 没有反馈（之前还有 UI stale 问题）
3. 用户主观认为"完全没保存"

实际上持久化链路完全正常，只是写入的值错了。

### 4. 为什么之前的修改没发现

- `3eff50b`：只增加启动逻辑，未修改保存逻辑
- `d9d77f2` / `1a56273`：只增加 UI 刷新
- 测试直接调用槽函数并传入 `Qt.CheckState.Checked`，模拟的是新状态，与真实信号行为不符

### 5. 系统性影响

项目中发现两处相同的问题：

| 文件 | 槽函数 | 问题 |
|------|--------|------|
| `device_settings_page.py` | `_on_auto_connect_changed` | 使用 `state` 参数判断 |
| `settings_page.py` | `_on_tray_changed` | 使用 `state` 参数判断 |

两处都已修复为使用 `checkbox.isChecked()` 读取当前真实状态。

## 修复方案

### 修复 1：修正保存逻辑（`7372aac`）
```python
def _on_auto_connect_changed(self, state):
    enabled = self._auto_connect_cb.isChecked()  # ✅ 读取当前真实状态
    self._config.setdefault('device', {})
    self._config['device']['auto_connect'] = enabled
    self.settings_changed.emit(self._config)
```

### 修复 2：启动时自动连接（`3eff50b`）
在 `main.py` 启动流程中增加：
```python
auto_connect = config.get('device', {}).get('auto_connect', False)
if auto_connect:
    last_device = adb_manager.get_last_connected_device()
    if last_device:
        adb_manager.connect_device(last_device)
```

### 修复 3：UI 刷新（`1a56273` + `d9d77f2`）
- `_scan_devices` 扫描完成后调用 `_update_device_info()`
- 新增 `showEvent` 处理，页面显示时刷新设备信息

## 验证
- 信号链路完整：`DeviceSettingsPage` → `MainWindow` → `_save_config` → 原子写入文件
- 启动链路完整：`main.py` 读取配置 → 调用 `connect_device`
- UI 刷新完整：扫描后 + 页面显示时刷新
- 测试覆盖：12 个 pytest 用例全部通过

## 结论
**配置持久化机制一直正常工作**，问题在于：
1. 槽函数读取了 Qt 信号的旧状态参数，导致保存值与用户操作相反
2. 启动代码之前从未使用持久化的配置
3. UI 没有及时反映状态变化

这导致用户感知为"未保存"，实际是"保存了反值 + 未使用 + 未显示"。
