# 资料页误入根因修复 + 云网络重试宽容 + 测试态 fatal 收集循环（2026-08-07，提交 309111e）

## 一、根因分析

### 1. 为什么"代码总是意外进入资料页"

资料页不是被主动打开的，而是**恢复动作的副作用**：

1. `VisitFriends` 合法进入好友访客终端（设计如此）。
2. 访客终端尾部节点失败（vendored 校准天花板）→ 任务返回 False。
3. 恢复路径 `_recover_to_world` 在 OCR 判定非主世界后，对固定候选坐标
   `(1200,30)/(1135,94)/(1192,94)/(1221,36)/(1187,36)` **盲点击** 最多 4 轮 ×5 点。
   当前页面没有 X 在候选位置时，盲点击命中头像等 HUD 按钮 → 打开资料页。
4. 落入资料页后：`__ScenePrivateAnyExit` 无识别按 ESC×100（约 150s 空转），
   而资料页/访客终端**只有右上 X 关闭按钮**，ESC/BACK 均无效 → 后续所有任务
   在资料页启动、全部失败。

### 2. 为什么"总是使用 ESC"

- `__ScenePrivateAnyExit`（SceneCommon.json）是场景图兜底退出节点：无识别、
  `ClickKey 27`、`max_hit=100`、`post_delay=1500`。任何场景匹配失败都落到这里
  无限按 ESC——对带 X 按钮的云页面完全无效。
- `_lightweight_recover_ui` 的 3×BACK 为历史遗留（当前已是无调用方的死代码，
  本次未删除，仅记录）。

### 3. 云网络瞬态错误缺乏宽容

云串流网络抖动会出现"网络异常/重试/重新连接"错误页，旧代码不识别这些文案，
启动链与弹窗处理把它们当作未知页面；完整重连仅 3 次短退避，云环境恢复耗时
更长时直接中止队列。

## 二、修改方案

1. **识别驱动的 X 关闭**（替代盲 ESC/盲点击）：
   - `_WORLD_BLOCKING_OCR` 增加资料页/访客终端特征词（权限等阶/探索等级/
     干员展示/光荣之路/访客终端），主世界 guard 显式识别。
   - `_verify_in_world_by_ocr` 保留最近一次全屏 OCR 文本 `_last_world_ocr_text`。
   - `_recover_to_world`：OCR 命中 `_PROFILE_CLOSE_KEYWORDS` 时只点右上 X
     `(1220,35)`，不参与盲候选轮转；未命中才走原候选点击。
   - `service/runtime.py::_cloud_cleanup_to_world`：资料页分支 BACK → tap X，
     关键词增加"访客终端"。
   - `__ScenePrivateAnyExit` `max_hit` 100→10：ESC 上限约 15s，深层覆盖层由
     runtime 识别驱动关闭/force-stop 兜底，杜绝 150s 无识别空转。
2. **云网络重试宽容**：
   - `_dismiss_cloud_idle_popup` / `_advance_boot_to_world` 识别并点击
     "网络异常/网络错误/重新连接/重试"等云网络错误页按钮，继续推进启动链。
   - `_reconnect_with_retry`：云版本（包名含 cloud）3→5 次重试、退避 3s→5s 步进。
   - 主世界 guard screencap 超时 4s→8s，宽容降级态慢帧。
3. **测试态 fatal 收集循环（生产隔离）**：
   - 门控：环境变量 `ISTINA_FATAL_RESTART_LOOP=1`（默认关闭，生产行为不变）。
   - fatal（连接彻底无法恢复）→ `_capture_fatal_context` 截屏 + fatal_info.json
     留档到 `.tmp/fatal/<时间戳>_<任务>/` → `_force_restart_to_world` 重启云终末地
     → 队列从头再跑收集卡点。
   - 允许多轮不完整跑通：`ISTINA_FATAL_MAX_ROUNDS`（默认 3）、
     `ISTINA_FATAL_MAX_RESTARTS`（每轮默认 4），防止无限重启。
   - 卡点（fatal + 任务失败 + 当时 OCR 文本）追加写入
     `.tmp/fatal/blockers_summary.json`。

## 三、影响面

- 生产路径（未设环境变量）：`run_queue` 单轮行为与旧版一致（回归测试覆盖）。
- 资料页/访客终端不再靠 ESC/BACK 关闭；`_recover_to_world` 每轮多一次文本判断
  （复用已有 OCR 结果，无额外截屏开销）。
- 场景图兜底 ESC 上限 10 次：极深覆盖层场景转换可能更早失败，由 runtime
  恢复链（X 关闭/force-stop）接管。
- 云版本完整重连最坏耗时增加（5 次 × 最长 25s 退避），换取云网络抖动容忍。

## 四、非期待变化

- `__ScenePrivateAnyExit` 修改位于 `3rd-part/maaend/resource_cloud/`（gitignore，
  本地校准层），不进版本控制；换机器需重新应用。
- `_lightweight_recover_ui`（3×BACK）死代码保留未删，避免与本批修复混合。
- service/runtime.py 存量 17 项 ruff 未处理（不放宽配置，逐文件修复另批进行）；
  mypy 在捆绑解释器不可用为已知存量状态。
