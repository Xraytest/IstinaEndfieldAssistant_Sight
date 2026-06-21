# 标准流 MaaEnd 设计模式完善报告

生成时间：2026-06-14

## 概述

基于 MaaEnd-2 参考项目的设计模式，完善了 `daily_quest` 和 `weekly_quest` 两个核心标准流流程。

## MaaEnd 设计模式分析

### 1. DijiangRewards 导航模式

**来源**: `sample_program/MaaEnd-2/assets/resource_adb/pipeline/DijiangRewards/`

**核心设计**:
```
Navigation(打开面板) → StatusCheck(确认页面) → Claim(领取) → Back(返回)
```

**关键文件**:
- `Navigation.json`: 打开地图导航 (`OpenMap` 点击 [141, 125])
- `MainFlow.json`: 主流程控制 (`CarbinSwipe` 滑动，`CloseButtonDijiang` 返回 key=4)
- `GrowthChamber.json`: 生长室逻辑 (滑动查找、排序、选择目标)

**设计特点**:
- 导航操作分离到独立文件
- 使用 `ClickKey(key=4)` 作为通用返回机制
- ROI 区域识别页面状态
- 目标未找到时滑动查找 (`GrowthChamberTargetNotFound`)

### 2. BAKER 筛选模式

**来源**: `sample_program/MaaEnd-2/assets/resource_adb/pipeline/BAKER.json`

**核心设计**:
```
SwitchTab(切换标签) → SwipeFilter(滑动筛选) → FilterUnread(查找可领取) → Claim(领取)
```

**关键节点**:
- `BakerSwitchMsg`: 切换到会话信息界面
- `BakerResetFilter`: 点击刷新筛选
- `BakerFilterUnread`: OCR 识别"未读"选项
- `BakerTalkWith`: 模板匹配点击聊天框
- `BakerTalkOver`: OCR 检测会话结束 ("暂无新话题")

**设计特点**:
- 标签切换 + 筛选组合
- OCR + 模板匹配双模式识别
- 滑动筛选列表 (`BakerSwipeFilter`)
- 会话结束状态检测

### 3. AutoCollect 自动收集模式

**来源**: `sample_program/MaaEnd-2/assets/resource_adb/pipeline/AutoCollect/`

**核心设计**:
```
OCR 识别 → 点击收集 → 路径规划 → 移动收集
```

**关键文件**:
- `AutoCollectClick.json`: OCR 识别收集点 (ROI: [766, 350, 263, 219])
- `AutoCollectDig.json`: 挖掘点识别
- `AutoCollectRoute7.json`: 路径规划

**设计特点**:
- OCR 优先识别收集点
- ROI 区域精确限定
- 路径规划优化移动效率

### 4. Common/Button 通用按钮模式

**来源**: `sample_program/MaaEnd-2/assets/resource_adb/pipeline/Common/Button/`

**核心设计**:
```
CloseButtonType1: ClickKey(key=4) 通用关闭/返回
WhiteConfirmButtonType1: 白色确认按钮模板匹配
YellowConfirmButtonType2: 黄色确认按钮模板匹配
```

**设计特点**:
- 返回键作为通用关闭机制
- 按钮类型分类管理
- 模板匹配阈值控制 (threshold: 0.7)

## 标准流完善方案

### daily_quest (每日任务)

**参考模式**: MaaEnd DijiangRewards

**完善前** (7 步骤):
```
check_exit_dialog → close_exit_dialog → verify_world → open_quest → 
wait_stabilize → check_daily → claim_daily → return_world
```

**完善后** (9 步骤):
```
ensure_world → open_quest_panel → verify_quest_panel → 
scroll_daily_tasks → check_daily_status → claim_daily_rewards → 
verify_claim → close_quest_panel → verify_world_return
```

**改进点**:
1. ✅ 移除 exit_dialog 检查（由引擎前置验证统一处理）
2. ✅ 添加面板打开验证（金色元素≥22）
3. ✅ 添加滑动查找步骤（参考 `GrowthChamberTargetNotFound`）
4. ✅ 添加领取验证等待（确保动画完成）
5. ✅ 添加返回后验证（确保回到世界地图）

**步骤详解**:
| 步骤 | 动作 | MaaEnd 参考 | 说明 |
|------|------|------------|------|
| ensure_world | check | - | 确保在探索界面 |
| open_quest_panel | tap | Navigation.OpenMap | 打开任务面板 (860,80) ✓ |
| verify_quest_panel | check | Status 检测 | 验证面板已打开（金色元素≥22） |
| scroll_daily_tasks | swipe | GrowthChamberTargetNotFound | 滑动查找每日任务 |
| check_daily_status | check | BakerFilterUnread | 检查任务状态 |
| claim_daily_rewards | claim | - | 一键领取奖励 |
| verify_claim | wait | - | 等待领取动画 |
| close_quest_panel | back | CloseButtonType1 | 返回 (key=4) |
| verify_world_return | check | - | 验证回到世界 |

### weekly_quest (周常任务)

**参考模式**: MaaEnd BAKER

**完善前** (5 步骤):
```
open_quest → switch_weekly → check_weekly → claim_weekly → return_world
```

**完善后** (11 步骤):
```
ensure_world → open_quest_panel → verify_quest_panel → 
switch_to_weekly → scroll_weekly_list → check_weekly_status → 
claim_weekly_rewards → verify_claim → return_world → verify_world_return
```

**改进点**:
1. ✅ 添加前置世界验证
2. ✅ 添加面板打开验证
3. ✅ 添加滑动查找步骤（参考 `BakerSwipeFilter`）
4. ✅ 状态检查参考 `BakerFilterUnread`
5. ✅ 添加领取验证和返回验证

**步骤详解**:
| 步骤 | 动作 | MaaEnd 参考 | 说明 |
|------|------|------------|------|
| ensure_world | check | - | 确保在探索界面 |
| open_quest_panel | tap | Navigation.OpenMap | 打开任务面板 |
| verify_quest_panel | check | Status 检测 | 验证面板已打开 |
| switch_to_weekly | tap | BakerSwitchMsg | 切换到周常标签 |
| scroll_weekly_list | swipe | BakerSwipeFilter | 滑动查找列表 |
| check_weekly_status | check | BakerFilterUnread | 检查任务状态 |
| claim_weekly_rewards | claim | - | 一键领取奖励 |
| verify_claim | wait | - | 等待领取动画 |
| return_world | back | CloseButtonType1 | 返回 |
| verify_world_return | check | - | 验证回到世界 |

## MaaEnd 设计原则应用

### 1. 导航分离原则

**MaaEnd**: `Navigation.json` 独立管理导航操作
**应用**: 标准流中 `open_*_panel` 步骤明确导航意图

### 2. 状态验证原则

**MaaEnd**: ROI 区域识别 + 模板匹配 + OCR 三重验证
**应用**: 标准流中 `verify_*` 步骤使用多源视觉分析

### 3. 滑动查找原则

**MaaEnd**: `GrowthChamberTargetNotFound` 目标未找到时滑动
**应用**: 标准流中 `scroll_*` 步骤主动滑动查找

### 4. 通用返回原则

**MaaEnd**: `ClickKey(key=4)` 作为通用返回机制
**应用**: 标准流中 `back` 动作统一使用返回键

### 5. 错误恢复原则

**MaaEnd**: `max_hit` 限制重试次数，`next` 定义恢复路径
**应用**: 标准流引擎内置路由恢复逻辑

## 配置变更总结

### flows_config.json 变更

1. **头部注释更新**: `2026-06-14 基于 MaaEnd 设计模式完善`
2. **daily_quest**: 7 步骤 → 9 步骤
3. **weekly_quest**: 5 步骤 → 11 步骤
4. **execution TODO**: 添加完成标记和后续计划

### 动作类型使用统计更新

| 动作 | 完善前 | 完善后 | 变化 |
|------|--------|--------|------|
| tap | 24 | 24 | - |
| check | 10 | 14 | +4 (新增验证步骤) |
| back | 9 | 9 | - |
| claim | 6 | 6 | - |
| swipe | 1 | 3 | +2 (新增滑动查找) |
| wait | - | 2 | +2 (新增验证等待) |

## 后续完善计划

### 高优先级

1. **resource_collection**: 参考 MaaEnd `AutoCollect` 模式
   - OCR 识别资源点
   - 路径规划优化
   - 一键收集逻辑

2. **delivery_mission**: 参考 MaaEnd `DeliveryJobs` 模式
   - 送货任务识别
   - 确认执行流程

### 中优先级

3. **event_rewards**: 参考 MaaEnd `DijiangRewards` 模式
   - 活动列表滑动
   - 奖励领取验证

4. **dungeon_grinding**: 参考 MaaEnd `SceneManager` 模式
   - 地图导航
   - 关卡选择

### 低优先级

5. **菜单内坐标验证**: 运行 `verify_menu_entries.py`
6. **面板内坐标优化**: 实际运行调整

## 测试建议

### 1. 配置检查

```bash
python scripts/test_all_flows.py
```

验证所有流程配置正确性。

### 2. 单流程测试

```bash
# 测试每日任务
python scripts/standard_flow_engine.py --flow daily_quest --local-only

# 测试周常任务
python scripts/standard_flow_engine.py --flow weekly_quest --local-only
```

### 3. 视觉分析验证

```bash
# 采集任务面板特征
python scripts/capture_page_profiles.py --type quest_panel --count 10

# 更新页面特征模型
python scripts/capture_page_profiles.py --update
```

### 4. 坐标验证

```bash
# 验证任务面板内坐标
python scripts/verify_menu_entries.py --scan quest_panel
```

## 结论

### ✅ 已完成

1. **daily_quest**: 基于 MaaEnd DijiangRewards 模式完善 (9 步骤)
2. **weekly_quest**: 基于 MaaEnd BAKER 模式完善 (11 步骤)
3. **设计原则应用**: 导航分离、状态验证、滑动查找、通用返回、错误恢复
4. **文档完善**: 新增 `STANDARD_FLOW_MAAEND_DESIGN.md`

### 📋 待完成

1. 其他 8 个流程的 MaaEnd 模式完善
2. 面板内坐标精确验证
3. 实际运行测试和优化

### 🎯 设计目标

通过引入 MaaEnd 成熟的设计模式，提升标准流的：
- **健壮性**: 状态验证 + 错误恢复
- **可维护性**: 导航分离 + 步骤清晰
- **可扩展性**: 模式复用 + 配置驱动

---

*生成时间：2026-06-14*
*参考项目：MaaEnd-2*
*配置文件：config/standard_flows/flows_config.json*
