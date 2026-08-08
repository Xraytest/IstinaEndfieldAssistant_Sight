# 准确判定机制落地 + Alt键/地图打开根因修复（提交 b5f9a1a）

## 背景

用户质疑"你是如何确定任务正确工作的"。上一轮"11/13 通过"含假阳性——Python 级
后备处理器基于盲坐标+OCR 启发式，返回 True 只是"没抛异常"，不代表任务完成。
本轮目标：建立**准确判定**（成败以 MaaFW 管线自身识别验证节点为准），修根因，
重跑取得真实基线。

## 准确判定机制（提交 b5f9a1a）

- **Python 后备处理器门控**：`_register_python_handlers()` 仅在
  `ISTINA_PY_FALLBACK=1` 时注册，默认关闭（与 ISTINA_FATAL_RESTART_LOOP 同一
  测试态隔离原则）。任务成败 = 管线识别验证结果，不再有假阳性计入。
- **注册表实例化**：`_python_task_handlers` 从类属性改为实例属性（`__init__`
  初始化），修复跨实例泄漏（测试暴露：前一实例注册的 TestTask 污染后续实例）。
- pytest 32/32 通过；ruff 干净。

## 根因修复一：Alt 键（164/18）云端不可用

**实证**：MaaFW `AdbShellInput not supports [key=164]`。管线 26 个
KeyDown/KeyUp 节点使用 Alt(164/18)，云端全部失败，导致入口导航（控制中枢/
地区建设/协议同步器/拍照/交互等）整链中断。

**修复**：`resource_cloud` 原位覆盖 26 节点 `action: DoNothing`（保留 next 链）。
`AutoAltClickAction` 退化为普通点击。实测普通点击即可打开地区建设/控制中枢
页面（RegionalDevelopmentButton 模板 0.92 命中，ProtosyncMenuButton 0.90 命中）。

**收益**：VisitFriends 本轮首次通过（此前连续多轮失败）。

## 根因修复二：地图打开节点设计缺陷

**实证**：`__ScenePrivateWorldEnterMapAny` 基包 `action: Click` 点击 InWorld
识别盒（协议同步器按钮），无法打开地图；M 键(77)经 ADB 云端无效（实测）。

**修复**：`resource_cloud` 覆盖为点击小地图中心（135,115,10,10）→ 实测打开地图
（"事务提醒"命中）。

**收益**（DijiangRewards 单任务复测轨迹）：
```
地图打开成功 → 传送帝江 → 进入控制中枢（旧模板在帝江HUD可用）→
快速收集产物✓ → 快速收集线索✓ → 会客室（停滞在赠予线索子流程）
```

## 准确判定轮实测（17:20 启动，13 任务，round 1）

| 任务 | 结果 | 失败点（节点轨迹） |
|---|---|---|
| AndroidOpenGame | ✓ | — |
| VisitFriends | ✓ | — |
| DijiangRewards | ✗ | 地图→帝江→控制中枢→产物/线索收集✓→会客室赠予线索子流程 |
| CreditShoppingN2 | ✗ | 商店页内全部成功→NeedCredit→帝江链地图（修复前） |
| DeliveryJobs | ✗ | 进入地区建设后回退主世界循环 |
| SellProduct | ✓ | — |
| AutoStockpile | ✓ | — |
| AutoStockStaple | ✗ | 入口即败（AnyExit 循环） |
| AutoSell | ✗ | ExecuteValleyIVMain 执行阶段 |
| EnvironmentMonitoring | ✗ | 古树拍照子任务（MapNavigateAction+相机） |
| DailyRewards | ✗ | 入口即败（AnyExit 循环） |
| SeizeDeliveryJobs | ✗ | 入口即败（AnyExit 循环） |
| AutoCollect | ✗ | 74s 速败于路线建立阶段 |

**4/13 通过，9 失败全部收尾回到主世界（blockers OCR 均为世界画面），零假阳性。**

## 附加实测结论

- **键盘键位实测**：ESC(27) 云端有效；字符键 M(77)/K(75) 经 ADB 无效。
  云版为触摸逻辑，须走点击路径。
- **控制中枢模板**：`ControlNexusButton`/`SceneManager/ControlNexus.png` 在
  开放世界 HUD 不匹配（云 UI 图标已更换），但在帝江号 HUD 可用（实测命中）。
- **云 idle 断连**：深层页内任务运行超 ~5 分钟触发云空闲断连（回登录页），
  是持续跑批的架构性风险，后续任务被中断。

## 遗留校准点（vendored 管线尾部节点，逐屏校准）

1. DijiangRewards 会客室赠予线索子流程（滑动/选择循环）
2. AutoSell ExecuteValleyIVMain（Go 自定义动作执行）
3. EnvironmentMonitoring 古树拍照（相机 R 键不可用，需改点击/模板）
4. AutoStockStaple/DailyRewards/SeizeDeliveryJobs 入口（AnyExit 循环）
5. DeliveryJobs 地区建设子页导航
6. AutoCollect 路线建立

## Files Modified

- `src/core/service/maa_end/runtime.py`、`tests/test_istina_runtime.py`（b5f9a1a）
- `3rd-part/maaend/resource_cloud/...`（Alt 26 节点覆盖、SceneMap.json 地图覆盖；
  3rd-part 不入版本控制，本地资产）
- `docs/TASK_LOG.md`、`reports/implementation/2026-08-08-accurate-judgment-alt-map-fixes.md`（本条）
