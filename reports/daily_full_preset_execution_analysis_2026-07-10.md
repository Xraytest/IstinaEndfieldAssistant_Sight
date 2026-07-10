# DailyFull 预设执行与软件正确性分析报告

## 1. 执行目标

通过运行 `DailyFull` 每日全套预设，并结合代码静态分析与执行过程中的屏幕媒体，判断当前软件是否能正确完成日常自动化流程。

## 2. 代码静态分析摘要

对 `src/gui/pyqt6/`、`src/core/service/`、`src/core/capability/device/`、`src/core/service/maa_end/`、`src/cli/` 进行了深度静态分析，主要发现如下：

| 级别 | 数量 | 典型问题 |
|------|------|----------|
| P0 | 4 | 任务队列跨线程操作 Qt 对象、`QThread.terminate()`、命令构造错误导致 JSON 被空格切碎、`MainWindow` 截图 path 分支 base64 解码错误 |
| P1 | 11 | `_connect_with_timeout` 守护线程未清理、`_cleanup_partial` 未关闭 native 资源、`_try_recover` 无条件重启应用、AndroidRuntime `ipc/` 目录未预创建、`_recv` 无长度限制、模态对话框阻塞测试等 |
| P2 | 16 | 崩溃计数未重置、并发命令队列无原子性、自动重连定时器堆叠、动画对象泄漏、`QWidget` 导入缺失等 |
| P3 | 8 | UX、类型提示、国际化键不一致等 |

> 详细清单见 `reports/comprehensive_audit_agent_swarm_176.md` 及本次分析原始输出。

## 3. 执行过程

### 3.1 环境

- 设备：`192.168.1.12:16512`（MuMu 模拟器）
- 命令：`python src/cli/istina.py daily --options '{"preset":"DailyFull"}'`
- 辅助：在执行期间每 5 秒通过 ADB `screencap` 采集一次屏幕，保存到 `output/daily_screenshots/`

### 3.2 执行结果

```text
[WARNING] [core.capability.device.android_runtime] scrcpy 会话异常 TimeoutError timed out
[WARNING] [root] [MAIN] 任务执行失败 task=VisitFriends
[WARNING] [root] [MAIN] 预设执行中断 preset=DailyFull failed_task=VisitFriends
```

- 总耗时：**471.32 秒（约 7 分 51 秒）**
- 最终状态：`error`
- `maaend_connected`：**false**
- 采集截图：**85 张**

### 3.3 屏幕媒体分析

| 阶段 | 截图时间戳 | 屏幕状态 | 说明 |
|------|------------|----------|------|
| 开始 | 10:35 | Android 桌面 | 游戏未启动，停留在 MuMu 桌面 |
| 中段 | 10:37 ~ 10:40 | Android 桌面 / 黑屏 / 加载界面 | 手动启动游戏后仍停留在登录/加载界面 |
| 结束 | 10:43 | 游戏加载界面（NOW LOADING） | 未能进入大世界，预设即在 `VisitFriends` 超时失败 |

关键观察：

1. **从桌面启动时**：`DailyFull` 的第一个任务 `VisitFriends` 没有主动启动游戏的能力；`VisitFriendsMainAction` 仅重置状态，真正的游戏进入依赖 `SceneAnyEnterWorld` 子任务。
2. **手动启动游戏后**：游戏停留在标题/登录界面，`__ScenePrivateLogin` 依赖 `SceneManager/LoginExit.png` 模板匹配；当前标题界面左上角无该退出按钮，导致登录节点无法命中。
3. **`__ScenePrivateLoginContinue` 期望 OCR 识别底部“点击任意位置继续”**，但当前登录提示位于顶部“用户 137****0510 欢迎进入游戏”，OCR 区域（底部）不匹配。
4. 加载界面出现后，MaaEnd 识别不到 `InWorld`，`VisitFriends` 在 471 秒后超时，随后 scrcpy 会话也超时，连接状态丢失。

## 4. 根因判定

软件**当前无法正确执行 DailyFull 全套预设**，主要根因：

1. **资源不匹配**：`3rd-part/maaend/resource/pipeline/SceneManager/SceneLogin.json` 中的登录识别模板和 OCR 期望与当前游戏版本登录界面不符。
2. **缺少前置启动**：Istina 运行时的 `daily.run` 流程没有在游戏未启动时主动拉起并等待进入大世界的健壮逻辑；它直接假设游戏已处于可操作状态。
3. **恢复机制粗暴**：`_try_recover` 在任务失败后会无条件 `force-stop` 并重启游戏（`com.hypergryph.endfield`），但重启后仍回到登录界面，无法解决识别问题。
4. **GUI 层高危缺陷**：若从 GUI 运行同一流程，还存在任务队列跨线程访问 Qt 对象、`QThread.terminate()`、命令字符串拼接被 `split()` 切碎等 P0 问题，极易崩溃或行为异常。

## 5. 结论

**当前软件不能正确运作 DailyFull 每日全套预设。**

- 纯 CLI 执行：在 471 秒后失败于第一个任务 `VisitFriends`，未产生任何有效日常收益。
- 屏幕证据：整个执行期间未进入游戏大世界，停留在桌面、登录或加载界面。
- 代码证据：登录识别资源与当前游戏界面不匹配，且上层流程缺少可靠的游戏启动/登录等待机制。

## 6. 修复建议（按优先级）

1. **更新登录识别资源**：重新截取 `SceneManager/LoginExit.png`，并将 `__ScenePrivateLoginContinue` 的 OCR 区域/文本适配为当前登录界面。
2. **增加前置启动与等待**：在 `daily.run` / `preset.run` 前统一调用 `AndroidAppRestartPolicy.restart()` 或 `monkey` 启动应用，并循环等待 `InWorld` 识别成功再进入后续任务。
3. **修复 GUI 层 P0 缺陷**：将 `_runtime_queue_runner` 移回主线程（或仅在工作线程做纯计算，GUI 更新走信号）、移除 `QThread.terminate()`、修正 `task run` 命令构造方式。
4. **改进恢复策略**：`_try_recover` 重启前应先尝试截图确认当前页面，避免误判导致反复重启。
5. **补充端到端回归测试**：至少覆盖“桌面 → 启动游戏 → 登录 → 进入大世界 → 执行单个预设任务”这一完整链路。

## 7. 附录

- 截图目录：`output/daily_screenshots/`
- 汇总文件：`output/daily_screenshots/summary.json`
- 执行日期：2026-07-10
