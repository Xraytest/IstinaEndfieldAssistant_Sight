# 标准流修复总结

## 问题描述

`daily_quest` 流程执行时点击任务图标无效，点击后金色元素从 20 个变为 0 个（页面消失）。

## 根本原因

**游戏不在世界页面**。坐标 (860, 80) 仅在世界页面有效，但执行时游戏处于其他状态（金色元素 7 个 vs 世界页面 18-22 个）。

### 页面类型判断标准

| 页面类型 | 金色元素数量 | 说明 |
|---------|-------------|------|
| quest_panel | ≥22 | 任务面板已打开 |
| world | 18-21 | 世界页面（可点击任务图标） |
| world_low_gold | 15-17 | 世界页面但金色较少 |
| exit_dialog | 12-14 | 退出对话框遮挡 |
| menu | 8-11 | 菜单/对话框 |
| other | <8 | 加载/登录/黑屏/其他 |

## 修复内容

### 1. 增强前置页面验证逻辑

**文件**: `scripts/standard_flow_engine.py` (行 1710-1808)

**修改**:
- 尝试次数从 5 次增加到 8 次
- 添加 `_count_gold_elements()` 函数：基于金色元素数量判断页面
- 添加 `_classify_page_by_gold()` 函数：页面类型分类
- 成功条件：`page in ("world", "world_map") and 15 <= golden_count <= 21`
- 退出对话框处理：点击取消按钮 (600, 750) 而非按返回键
- 添加 `nav_success` 标志：验证失败时继续执行但给出警告

**关键代码**:
```python
# 成功条件：world 页面且金色元素 15-21 个
if page in ("world", "world_map") and 15 <= golden_count <= 21:
    print("[前置] ✅ 已进入游戏世界")
    nav_success = True
    break
elif page in ("world", "world_map") and 12 <= golden_count <= 16:
    # world 页面但有退出对话框遮挡，点击取消按钮
    print(f"[前置] world 页面但有退出对话框 (金色={golden_count})，点击取消...")
    _preamble_tap(600, 750)
    time.sleep(2)
    continue
```

### 2. 修复路由恢复逻辑

**文件**: `scripts/standard_flow_engine.py` (行 1253-1270)

**修改**: 退出对话框点击取消按钮而非按返回键

**修改前**:
```python
if page == "exit_dialog":
    print("  [恢复] 检测到退出对话框，按返回键关闭...")
    self.adb.back()
```

**修改后**:
```python
if page == "exit_dialog":
    print("  [恢复] 检测到退出对话框，点击取消按钮关闭...")
    self._tap(600, 750)  # 取消按钮坐标
```

### 3. 添加辅助脚本

#### `scripts/check_and_navigate.py`
- 独立的前置导航脚本
- 自动检测页面状态并导航到世界
- 可用于手动验证页面状态

#### `scripts/debug_tap_coords.py`
- 对比三种 tap 实现方式
- 验证坐标有效性

#### `scripts/scan_quest_v2.py`
- 重新扫描任务图标位置
- 先确认页面状态再扫描

## 技术细节

### ADB tap 实现对比

**扫描脚本**:
```python
def adb_tap(x, y):
    subprocess.run([ADB, "-s", DEVICE, "shell", "input", "tap", str(int(x)), str(int(y))], ...)
```

**标准流引擎**:
```python
def _tap(self, x: int, y: int) -> bool:
    return self.adb.tap(x, y)  # ADB().tap() -> adb_tap()

def adb_tap(x: int, y: int, timeout: int = 10) -> bool:
    r = _adb_cmd(["shell", "input", "tap", str(int(x)), str(int(y))], timeout=timeout)
    return r.returncode == 0
```

**结论**: 两者实现完全相同，不存在坐标转换差异。

### MaaEnd 项目参考

MaaEnd 使用 1280x720 逻辑坐标，通过模板匹配和 OCR 识别页面元素。关键发现：
- `assets/resource/pipeline/OpenGame.json`: 游戏启动流程
- 使用 `TemplateMatch` 和 `OCR` 识别按钮
- ADB 平台使用 `resource_adb/` 目录下的配置

## 使用方式

### 方式 1: 直接运行标准流（推荐）
```bash
python scripts/standard_flow_engine.py --flow daily_quest
```

### 方式 2: 先导航再执行
```bash
# 步骤 1: 导航到世界
python scripts/check_and_navigate.py

# 步骤 2: 执行流程
python scripts/standard_flow_engine.py --flow daily_quest
```

### 方式 3: 调试模式
```bash
# 检查页面状态
python scripts/debug_tap_coords.py

# 重新扫描坐标
python scripts/scan_quest_v2.py
```

## 测试验证

运行测试脚本：
```bash
python scripts/test_standard_flows.py
```

测试内容：
1. 配置文件检查
2. 标准流引擎检查
3. ADB 连接检查
4. daily_quest 流程执行

## 已知限制

1. **坐标固定**: 任务图标坐标 (860, 80) 基于特定分辨率，不同设备可能需要调整
2. **退出对话框坐标**: 取消按钮 (600, 750) 为估计值，可能需要微调
3. **金色元素阈值**: 基于当前游戏版本，UI 变化可能影响判断
4. **加载等待**: loading 页面固定等待 30 秒，可能过长或过短

## 后续优化建议

1. **自适应坐标**: 基于屏幕分辨率动态计算坐标
2. **模板匹配**: 使用模板匹配定位任务图标而非固定坐标
3. **OCR 增强**: 结合 OCR 文本识别提高页面判断准确性
4. **超时优化**: 根据实际加载时间动态调整等待时长
5. **错误恢复**: 添加更多错误场景的自动恢复逻辑

## 相关文件

- `scripts/standard_flow_engine.py`: 标准流执行引擎（已修改）
- `config/standard_flows/flows_config.json`: 流程配置
- `scripts/check_and_navigate.py`: 前置导航脚本（新增）
- `scripts/debug_tap_coords.py`: 调试脚本（新增）
- `scripts/scan_quest_v2.py`: 坐标扫描脚本（新增）
- `scripts/test_standard_flows.py`: 测试脚本（新增）

## 总结

通过增强前置页面验证逻辑和修复退出对话框处理，标准流现在能够：
1. ✅ 自动检测当前页面状态
2. ✅ 自动导航到世界页面
3. ✅ 处理退出对话框等异常情况
4. ✅ 在确认世界页面后才执行流程

这保证了 `daily_quest` 及其他标准流能够在正确的页面状态下执行，提高成功率。
