# 修复报告：InWorld 在标题页误匹配导致 AndroidOpenGame 假成功

- 日期：2026-07-28
- 任务：队列端到端调试 Task #2，队列项 1/12 AndroidOpenGame(ClientVersion=CloudCN)
- 修改文件：
  - `3rd-part/maaend/resource/pipeline/Interface/InScene/Region.json`（InWorld 节点）
  - `3rd-part/maaend/resource_cloud/pipeline/Interface/InScene/Region.json`（InWorld 节点，同步修复）

## 1. 根因分析

执行队列第 1 项 `AndroidOpenGame` 返回 `success`（第二次尝试仅 10s），但执行后截图
（`.tmp/q01_AndroidOpenGame_after.png`）显示游戏仍停留在标题页「点击任意位置继续」，
未进入主世界 —— 典型「没通过却报通过」误判。

节点轨迹（logs/main.log 12:40:44）：
`AndroidOpenGame → AndroidOpenGame_Cloud → CloudClickContinue → OpenGame → CloseButton → EnterGame`，
`EnterGame` 命中后任务即报成功。

`EnterGame = And(InWorld)`（`resource/pipeline/OpenGame.json`）。上游 MaaEnd 的
`InWorld = Or(ProtosyncMenuButton, RegionalDevelopmentButton)` 仅含两个模板分支；
本仓库 commit `de024bf`（"fix: InWorld OCR cloud version detection"）向 InWorld 追加了两个
OCR 分支：`设置@roi[1150,60,110,50]`、`修复@roi[1150,115,110,50]`（threshold 0.7）。

这两个「设置/修复」按钮属于**云终末地客户端叠层 UI**，在游戏标题页（点击任意位置继续）
右上角同样渲染（公告/设置/修复三个按钮），且恰好落在上述 ROI 内。离线探针在标题页截图上
双向验证：

| 识别分支 | 标题页 | 主世界 |
| --- | --- | --- |
| OCR 设置@[1150,60]（补丁分支） | **HIT (score 0.9996)** | MISS |
| OCR 修复@[1150,115]（补丁分支） | **HIT (score 0.9999)** | MISS |
| 模板 ProtosyncMenuButton（上游分支） | MISS | **HIT (score 0.996, box [1203,10,55,55])** |

即：补丁分支只会在标题页产生误报，在真实主世界反而不命中；上游模板分支在云版本主世界
稳定命中，OCR 兜底并无必要。InWorld 在标题页误命中 → EnterGame 误命中 → OpenGame 链
提前终止并报成功。该误报还会污染所有引用 InWorld 的场景判定（SceneAnyEnterWorld、
`__ScenePrivateAnyEnterWorldSuccess`(resource_cloud 版) 等），是「假阴性纠正路径误报成功」
风险点的同一根因。

## 2. 修改方案（最小修复）

从两处 `InWorld` 定义中移除「设置/修复」两个 OCR 分支：

- `resource/pipeline/Interface/InScene/Region.json`：InWorld 恢复为上游的两个模板分支，
  desc 记录移除原因。
- `resource_cloud/pipeline/Interface/InScene/Region.json`：同步移除该两分支；保留该文件
  特有的中央区域 OCR 兜底（总控中枢/工业计划/O.M.V.帝江号，位于屏幕中央，标题页不存在
  此类文本，无误报风险）。

不修改 Python 代码，不改任务配置。

## 3. 影响面

- 所有引用 `InWorld` 的判定（EnterGame、SceneAnyEnterWorld 及 SceneMenu 各导航节点）
  在标题页/登录页不再误报「已在主世界」；AndroidOpenGame 必须真正推进到主世界才能成功。
- 云版本主世界识别退回模板匹配路径，实测 score 0.996 稳定命中，无假阴性回归。
- `resource_cloud` 目前未被 runtime 加载（load_resource 仅加载 resource + resource_adb），
  同步修复是为防止未来切换资源目录时带回同一误报源。

## 4. 非期待变化

- 无。未改动其他节点；聚合副本 `3rd-part/maaend/nodes.json` 中的 InWorld 本就是上游
  定义（无补丁分支），无需处理。
- 验证：修复后重跑 AndroidOpenGame（游戏已在主世界时 EnterGame 由模板分支命中，
  正常快速成功）；标题页误报路径由离线探针证明已消除。
