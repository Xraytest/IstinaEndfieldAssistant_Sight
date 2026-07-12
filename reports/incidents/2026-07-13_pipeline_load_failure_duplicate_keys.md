# Pipeline 资源加载失败 — AndroidOpenGame_CN 重复 key 冲突

**日期**: 2026-07-13
**触发**: 用户反馈"阅读最新的日志，修改使得软件无法正确连接到设备"

---

## 1. 根因分析

### 现象

`logs/main.log` L13431 显示：

```
[2026-07-12 16:44:32] [ERROR] Pipeline 资源加载失败 path=...3rd-part\maaend\resource
[2026-07-12 16:44:32] [ERROR] MaaEnd runtime 资源加载失败
```

连接流程因此中断，`connect()` 返回失败。CLI 进程随后崩溃（L13439: 16:44:50）。

### 时间线（关键证据）

| 时刻 | 事件 |
|---|---|
| 2026-07-09 00:16 | `GameSwitch/AndroidOpenGame.json` 创建（已含 4 个变体空对象） |
| 2026-07-12 15:56:15 | 最后一次 Pipeline 资源加载成功 |
| 2026-07-12 16:32:17 | **`OpenGame.json` 被修改**（添加 4 个重复 key） |
| 2026-07-12 16:44:32 | Pipeline 资源加载失败 |
| 2026-07-12 16:44:50 | CLI 进程崩溃 |

### 根因

上一轮修复（见 `reports/incidents/2026-07-12_android_open_game_cn_undefined.md`）误判 `AndroidOpenGame_CN` 在所有 pipeline JSON 中未定义，于是在 `3rd-part/maaend/resource/pipeline/OpenGame.json` 中添加了 4 个空对象定义：

```json
"AndroidOpenGame_CN": {},
"AndroidOpenGame_Bilibili": {},
"AndroidOpenGame_Global": {},
"AndroidOpenGame_VN": {},
```

但实际上 `3rd-part/maaend/resource/pipeline/GameSwitch/AndroidOpenGame.json` 早已定义了相同的 4 个 key：

```json
{
    "AndroidOpenGame_CN": {},
    "AndroidOpenGame_Bilibili": {},
    "AndroidOpenGame_Global": {},
    "AndroidOpenGame_VN": {}
}
```

MaaFW `Resource.post_bundle(resource_dir)` 递归加载 pipeline 目录下所有 JSON，遇到同名 key 在不同文件中重复定义时会因 "key already exists" 失败，整个 `post_bundle` job 置为失败。`MaaEndRuntime.load_resource()` 检测到 `job.succeeded == False` 后记录 "Pipeline 资源加载失败" 并返回 False，连接流程中断。

### 上一轮分析错误的原因

上一轮分析搜索时漏查了 `GameSwitch/AndroidOpenGame.json`——只搜索了 `OpenGame.json` 和聚合节点 `nodes.json`，未遍历 `GameSwitch/` 子目录。`nodes.json` 中虽也包含 `AndroidOpenGame_CN` key，但它是聚合副本且已被 `_relocate_aggregate_nodes()` 移出 pipeline 目录，不参与 `post_bundle` 加载，所以不是冲突源。

真正的冲突源是 `GameSwitch/AndroidOpenGame.json`，它在 pipeline 目录内，与新增定义产生重复。

---

## 2. 修改方案

### 撤销重复定义

`3rd-part/maaend/resource/pipeline/OpenGame.json` — 移除上次添加的 4 行：

```diff
     "AndroidOpenGame": {
         "pre_delay": 0,
         "post_delay": 0,
         "next": [
             "OpenGame"
         ]
     },
-    "AndroidOpenGame_CN": {},
-    "AndroidOpenGame_Bilibili": {},
-    "AndroidOpenGame_Global": {},
-    "AndroidOpenGame_VN": {},
     "PCOpenGame": {
```

### 验证

扫描整个 `3rd-part/maaend/resource/pipeline/` 目录（300 个 JSON 文件、3929 个 key）：
- 重复 key 数：**0**
- `AndroidOpenGame_*` 4 个变体 key 仅在 `GameSwitch/AndroidOpenGame.json` 中定义（单一来源）

---

## 3. 影响面

- **直接影响**: 撤销重复定义后，`post_bundle` 不再冲突，`load_resource()` 恢复成功，连接流程正常。
- **不影响**: `AndroidOpenGame_CN` 等 4 个变体仍由 `GameSwitch/AndroidOpenGame.json` 提供，task JSON 的 `pipeline_override` 引用这些 key 依然有效。
- **运行时文件**: `3rd-part/maaend/resource/pipeline/OpenGame.json` 在 .gitignore 范围内，不入 git。

---

## 4. 非期待变化

### 上一轮"退出到登入页面"问题的根因需重新评估

上一轮报告断言 `AndroidOpenGame_CN` 未定义导致 MaaFW 回退到 `OpenGame` pipeline → `CloseButton` 误匹配 → 退出到登入页面。**该结论被推翻**：`AndroidOpenGame_CN` 一直有定义（空对象），MaaFW 执行空对象节点会直接成功结束，不会回退到 `OpenGame` pipeline。

"退出到登入页面"的真正根因待重新调查，可能方向：
1. 队列中后续任务（如 `VisitFriends`）的 pipeline 在仪表盘界面误匹配关闭按钮
2. `_try_recover` 异常恢复时 `AndroidAppRestartPolicy.restart()` 强制重启游戏
3. 用户实际执行的 `ClientVersion` 选项未生效，仍走 `AndroidOpenGame.next=["OpenGame"]` 默认分支

### `load_resource` 错误日志不足

`MaaEndRuntime.load_resource()` 在 `job.succeeded == False` 时仅记录 "Pipeline 资源加载失败"，未输出 `job` 的详细错误信息（如 MaaFW 内部的 "key already exists" 文本）。建议后续在失败分支追加 `job.status` / `job.error` 等字段日志，便于快速定位 `post_bundle` 失败的具体原因。本次未修改该处，留待后续。
