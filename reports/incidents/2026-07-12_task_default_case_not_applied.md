# 任务 default_case 未应用 + checkbox 浅合并丢失选项分析

## 时间
2026-07-12

## 现象
GUI 队列执行 *Schedule 任务（SellProduct、AutoStockStaple、AutoCollect、ProtocolSpace）时，attach weekday flags 保持全 false，ScheduleRecognition 永远返回 false，任务走 *End 跳过分支。即使 GUI 选项编辑器预选了所有 weekday（基于 default_case），未打开选项编辑器的队列条目（如直接应用预设）仍不传递选项。

## 根因分析

### 缺陷 1：build_pipeline_override 未应用 default_case（DEFAULT-01）

`runtime.py:568-573` 原实现：
```python
for opt_name in task_options:
    value = options.get(opt_name)
    if value is None:
        continue  # ← 选项未提供时直接跳过，不应用 default_case
    opt_def = option_defs.get(opt_name, {})
    override.update(self._apply_option(opt_def, value))
```

MaaEnd 任务选项定义中，`checkbox`/`switch`/`select` 类型可声明 `default_case`（如 SellProductSchedule 的 default_case 列出全部 7 个 weekday）。当 GUI 不传递某选项（如直接应用预设未打开选项编辑器）时，`options.get(opt_name)` 返回 None，`build_pipeline_override` 直接跳过该选项，`default_case` 从未被应用。

对比 MaaEnd 上游设计：`default_case` 是"用户未选择时的默认值"，应在选项缺失时自动生效。GUI 选项编辑器（L1289-1294）正确地用 `default_case` 预选 checkbox，但仅在用户打开编辑器时才保存选项到队列条目。

### 缺陷 2：checkbox 多 case 浅合并丢失选项（MERGE-01）

`runtime.py:609-611` 原实现：
```python
for case in cases:
    if case.get("name") in active_cases:
        result.update(case.get("pipeline_override") or {})  # ← 浅合并
```

每个 weekday case 的 `pipeline_override` 结构相同：
```json
{"SellProductScheduleEnabled": {"attach": {"monday": true}}}
```

`dict.update()` 做浅合并：第二个 case 的 `SellProductScheduleEnabled` 完全覆盖第一个，`attach.monday` 被丢失。处理 7 个 weekday 后，仅保留最后一个（sunday）。

此缺陷是预先存在的（非本修复引入）：即使用户在 GUI 选择多个 weekday，也只有最后一个生效。但因 default_case 从未被应用（缺陷 1），此代码路径之前未被触发。

### 影响范围

4 个 *Schedule 任务均受影响：
- SellProduct（SellProductSchedule，7 weekday cases）
- AutoStockStaple（AutoStockStapleSchedule，7 weekday cases）
- AutoCollect（AutoCollectSchedule，7 weekday cases）
- ProtocolSpace（ProtocolSpaceSchedule，7 weekday cases）

其他 checkbox 选项同样受 MERGE-01 影响（如 AutoCollectRoutes 14 items、AutoCollectCommonRoutes 8 items、ResourceRecycleStationRegion 2 items、StashBackpackType 2 items、VisitFriendsProductionAssistControl 3 items），但仅当用户选择多个 case 时才触发。

## 修改方案

### 修复 1：default_case 回退（DEFAULT-01）

`runtime.py:568-576`，当 `value is None` 时检查 `default_case`：
```python
for opt_name in task_options:
    value = options.get(opt_name)
    opt_def = option_defs.get(opt_name, {})
    if value is None:
        default_case = opt_def.get("default_case")
        if default_case is None:
            continue
        value = default_case
    override.update(self._apply_option(opt_def, value))
```

### 修复 2：checkbox 深合并（MERGE-01）

`runtime.py:611`，`result.update()` → `result = self._merge_overrides(result, ...)`：
```python
for case in cases:
    if case.get("name") in active_cases:
        result = self._merge_overrides(result, case.get("pipeline_override") or {})
```

`_merge_overrides` 递归合并嵌套 dict，确保多个 case 的 `attach.{weekday}` 正确叠加。

## 影响面

- `build_pipeline_override`：所有通过 `run_task`/`run_pipeline`/`_retry_task` 执行的任务均受影响。switch/select 类型仅处理一个 case，`default_case` 回退不影响其行为。checkbox 类型受益于深合并。
- GUI 选项编辑器：不受影响，已正确预选 default_case。
- CLI `task run`/`preset run`：现在会应用 default_case，无需用户显式传递所有选项。
- 其他任务检查结果：所有 checkbox 选项均有 default_case（无遗漏）；14 个 switch/select 选项无 default_case（DailyRewards 5个、ProtocolSpace 2个、RealTimeTask 7个），属上游设计的 opt-in 特性，无需修改。

## 非期待变化

1. **switch/select 的 default_case 现在会被应用**：之前 switch/select 选项未提供时也被跳过（与 checkbox 相同）。修复后，如 `AutoStockpileAllowDataUpload(switch,dc=Yes)` 未提供时会自动应用 "Yes" case 的 pipeline_override。这是正确行为（符合上游设计），但可能改变之前"未传选项 = 无 override"的隐式行为。风险评估：低——default_case 是上游声明的默认值，应用它是正确的。
2. **checkbox 深合并可能暴露之前被掩盖的 case 冲突**：如果两个 case 的 pipeline_override 对同一字段设置不同值，深合并后后者覆盖前者（与浅合并行为一致，但之前因浅合并丢失大部分 case，冲突不明显）。风险评估：极低——weekday cases 设置不同字段（attach.monday vs attach.tuesday），无冲突。
3. **性能影响**：`_merge_overrides` 使用 `json.loads(json.dumps(...))` 做深拷贝，比 `dict.update()` 慢。但 checkbox cases 数量通常 <20，性能差异可忽略。
