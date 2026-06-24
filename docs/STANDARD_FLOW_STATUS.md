# 标准流状态报告

生成时间：2026-06-11

## 概述

| 项目 | 状态 |
|------|------|
| 配置版本 | 4.0 |
| 总流程数 | 10 |
| 启用流程数 | 10 |
| 已验证坐标 | 7 个 |
| 待验证坐标 | 11 个 |

## 已验证坐标 (✓)

| 坐标名 | 值 | 验证结果 |
|--------|-----|---------|
| quest_icon | [860, 80] | ✓ ADB tap 扫描最佳 59.9% |
| event_icon | [928, 53] | ✓ MID 352K 从 world 打开活动面板 |
| menu_icon | [1392, 79] | ✓ BIG 1.72M 从 world 打开系统菜单 |
| city_map | [150, 150] | ✓ MID 88K 从 world 打开城市地图 |
| industry_panel | [300, 80] | ✓ BIG 从 world 打开工业计划面板 |
| region_building | [400, 35] | ✓ BIG 从 world 打开地区建设面板 |
| industry_brief | [90, 120] | ✓ MID 85K 从 world 打开工业简报面板 |

## 待验证坐标 (?)

| 坐标名 | 值 | 说明 |
|--------|-----|------|
| base_entry_menu | [960, 400] | → 菜单内基建入口 (需运行 verify_menu_entries.py) |
| char_entry_menu | [1200, 330] | → 菜单内角色入口 (需运行 verify_menu_entries.py) |
| daily_claim | [975, 288] | ? 任务面板内每日领取按钮 |
| weekly_tab | [810, 300] | ? 任务面板内周常标签页 |
| claim_all | [810, 900] | ? 面板内通用领取按钮 |
| event_sub | [900, 200] | ? 活动面板内子区域 |
| mid_action | [540, 400] | ? 通用面板中部操作按钮 |
| production_btn | [540, 600] | ? 基建内生产队列按钮 |
| confirm_btn | [540, 690] | ? 基建内确认按钮 |
| confirm_dialog | [810, 1035] | ? 弹窗确认按钮 |
| exit_cancel | [600, 750] | 退出对话框取消按钮 (估计值) |

## 流程状态

### 1. daily_quest (每日任务)

**状态**: ✅ 核心逻辑已修复

**步骤**:
1. check_exit_dialog - 检查退出对话框
2. close_exit_dialog - 点击取消按钮 (600, 750)
3. verify_world - 验证进入世界
4. open_quest - 点击任务图标 (860, 80) ✓
5. check_daily - 检查每日任务状态
6. claim_daily - 点击领取 (975, 288) ?
7. return_world - 返回探索界面

**修复内容**:
- ✅ 前置页面验证逻辑增强 (8 次尝试，金色元素判断)
- ✅ 退出对话框自动处理 (点击取消而非按返回)
- ✅ 路由恢复逻辑完善

### 2. weekly_quest (周常任务)

**状态**: ⚠️ 部分坐标待验证

**步骤**:
1. open_quest - (860, 80) ✓
2. switch_weekly - (810, 300) ?
3. check_weekly
4. claim_weekly
5. return_world

### 3. resource_collection (资源收集)

**状态**: ⚠️ 菜单内坐标待验证

**步骤**:
1. open_menu - (1392, 79) ✓
2. enter_base - (960, 400) →
3. check_production
4. collect_resources
5. return_world

### 4. base_management (基地管理)

**状态**: ⚠️ 菜单内坐标待验证

**步骤**:
1. open_menu - (1392, 79) ✓
2. enter_base - (960, 400) →
3. check_facilities
4. restart_queue - (540, 600) ?
5. return_world

### 5. character_ascension (角色突破)

**状态**: ⚠️ 菜单内坐标待验证

**步骤**:
1. open_menu - (1392, 79) ✓
2. enter_character - (1200, 330) →
3. find_candidate
4. perform_ascension - (540, 400) ?
5. return_world

### 6. weapon_crafting (武器锻造)

**状态**: ⚠️ 菜单内坐标待验证

**步骤**:
1. open_menu - (1392, 79) ✓
2. enter_base - (960, 400) →
3. open_workshop - (540, 400) ?
4. craft
5. return_world

### 7. event_rewards (活动奖励)

**状态**: ⚠️ 面板内坐标待验证

**步骤**:
1. open_events - (928, 53) ✓
2. navigate_event_panel - (900, 200) ?
3. claim_events
4. return_world

### 8. delivery_mission (送货任务)

**状态**: ⚠️ 菜单内坐标待验证

**步骤**:
1. open_menu - (1392, 79) ✓
2. enter_base - (960, 400) →
3. check_delivery
4. select_delivery - (540, 600) ?
5. confirm_delivery - (540, 690) ?
6. return_world

### 9. dungeon_grinding (刷副本)

**状态**: ⚠️ 地图内坐标待验证

**步骤**:
1. open_map - (150, 150) ✓
2. check_stages
3. select_stage - (540, 400) ?
4. start_battle
5. collect_rewards
6. return_world

### 10. auto_move (3D 移动)

**状态**: ✅ 无需坐标验证

**步骤**:
1. ensure_world - navigate to explore
2. move_forward - swipe (200,1700)→(200,1400)
3. check_position
4. return_world

## 核心修复

### 前置页面验证 (standard_flow_engine.py 行 1710-1808)

**功能**:
- 8 次尝试验证页面状态
- 基于金色元素数量判断页面类型
- 自动处理退出对话框/菜单/加载等异常状态

**页面类型判断标准**:
| 页面类型 | 金色元素数量 |
|---------|-------------|
| quest_panel | ≥22 |
| world | 18-21 |
| world_low_gold | 15-17 |
| exit_dialog | 12-14 |
| menu | 8-11 |
| other | <8 |

### 路由恢复逻辑 (standard_flow_engine.py 行 1253-1360)

**功能**:
- 验证 tap 后是否到达预期页面
- 自动恢复路由错误 (退出对话框/标题画面/加载中)
- 重试机制 (最多 3 次)

**恢复策略**:
1. 退出对话框 → 点击取消按钮 (600, 750)
2. 标题画面 → 点击中央进入游戏
3. 加载中 → 等待加载完成
4. 世界地图未打开面板 → 重试点击
5. 其他页面 → 按返回重试

## 测试工具

### 1. test_all_flows.py

```bash
python scripts/test_all_flows.py
```

检查所有标准流的配置正确性。

### 2. verify_menu_entries.py

```bash
# 扫描所有菜单入口坐标
python scripts/verify_menu_entries.py --scan-all

# 单独验证基建入口
python scripts/verify_menu_entries.py --target base

# 单独验证角色入口
python scripts/verify_menu_entries.py --target char
```

### 3. capture_page_profiles.py

```bash
# 采集页面特征样本
python scripts/capture_page_profiles.py --type world --count 10
python scripts/capture_page_profiles.py --type quest_panel --count 5

# 更新特征数据库
python scripts/capture_page_profiles.py --update
```

## 待办事项

### 高优先级

1. **验证菜单内坐标** (影响 6 个流程)
   - 运行 `verify_menu_entries.py --scan-all`
   - 更新 `base_entry_menu` 和 `char_entry_menu` 坐标
   - 测试 `resource_collection`, `base_management`, `character_ascension` 等流程

2. **验证面板内坐标** (影响 daily_quest, weekly_quest)
   - 确认 `daily_claim` (975, 288) 在任务面板内有效
   - 确认 `weekly_tab` (810, 300) 在任务面板内有效
   - 确认 `claim_all` (810, 900) 在各面板内有效

### 中优先级

3. **测试 daily_quest 完整流程**
   ```bash
   python scripts/standard_flow_engine.py --flow daily_quest
   ```

4. **采集页面特征样本**
   - 运行 `capture_page_profiles.py` 采集各页面样本
   - 更新 `advanced_analyzer.py` 的 `PAGE_PROFILES`

### 低优先级

5. **优化提示词**
   ```bash
   python scripts/standard_flow_engine.py --flow daily_quest --optimize-prompts
   ```

6. **扩展流程覆盖**
   - 添加更多标准流程 (签到/邮件/好友等)

## 执行建议

### 方式 1: 直接运行标准流

```bash
# 执行单个流程
python scripts/standard_flow_engine.py --flow daily_quest

# 执行所有流程
python scripts/standard_flow_engine.py --flow all

# 本地模型运行
python scripts/standard_flow_engine.py --flow daily_quest --local-only
```

### 方式 2: 先验证再执行

```bash
# 步骤 1: 验证菜单坐标
python scripts/verify_menu_entries.py --scan-all

# 步骤 2: 更新配置
# 手动更新 config/standard_flows/flows_config.json

# 步骤 3: 测试流程
python scripts/standard_flow_engine.py --flow daily_quest
```

## 已知限制

1. **坐标固定**: 基于 1080x1920 分辨率，不同设备需调整
2. **退出对话框坐标**: (600, 750) 为估计值，可能需要微调
3. **金色元素阈值**: 基于当前游戏版本，UI 变化可能影响判断
4. **加载等待**: loading 页面固定等待 30 秒

## 总结

✅ **已完成**:
- 标准流引擎核心逻辑完善
- 前置页面验证增强
- 路由恢复逻辑完善
- 7 个世界页面坐标验证
- 测试工具链完整

⚠️ **待完成**:
- 菜单内坐标验证 (2 个)
- 面板内坐标确认 (9 个)
- 完整流程测试

📋 **下一步**:
1. 运行 `verify_menu_entries.py` 验证菜单坐标
2. 更新配置并测试 `daily_quest` 流程
3. 逐步验证其他流程
