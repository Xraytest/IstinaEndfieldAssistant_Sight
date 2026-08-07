# CloudCN 资源叠加修复 + 降级态连接/启动链韧性（2026-08-07）

## 一、根因分析

### 1. CloudCN 模板全盲（系统性，提交 19399ec）
云端 profile 曾只 `post_bundle(resource_cloud)`。该包**仅含 pipeline 覆盖层、无 `image/` 目录**，
MaaFW `TemplateResMgr` 因此把模板图片搜索根注册为空字符串（maafw 日志可见
`roots_=["",".../resource_adb/image"]`），全部 `TemplateMatch` 节点（`__ScenePrivate*`
场景检测、`CloseButtonType1` 等）图片解析失败，报 `templates or threshold is empty`。
表现为任务反复 ESC 空转、VisitFriends/DijiangRewards/CreditShoppingN2 连续失败、
AndroidOpenGame 在残留资料页因 CloudWaitLogo 误命中 "ENDFIELD" 死循环。

MaaFW v5.12.2 `PipelineResMgr::parse_and_override_once` 语义（源码核实）：
- 单 bundle 内 key 查重（重名整体加载失败，即 nodes.json 问题）；
- **跨 bundle 以 `insert_or_assign` 合并**：后载 bundle 的同名节点以先载同名节点为
  默认值做**字段级覆盖**。官方 `resource_cloud`/`resource_wlroots`/`resource_playcover`
  均为此叠加机制的 pipeline 覆盖层。

此前"禁止同时 post resource 与 resource_cloud"的结论是对单 bundle 查重规则的误读。

### 2. 降级态连接握手被 20s 硬超时切断（提交 b9559c2）
宿主 GPU 被其他进程占用时模拟器渲染降级（screencap 单次 3-6s、MaaFW 速度测试 ~11s），
`_CONNECTION_TIMEOUT_S=20` 在握手进行中切断连接（日志可见速度测试已成功仍报
"ADB 连接超时"）。

### 3. 云启动链不处理「知道了」弹窗（提交 a3724f5）
「您上次游戏的数据正在火速处理中」弹窗的「知道了」按钮（OCR 实测 @(606,420)）不在
`_advance_boot_to_world` 推进按钮期望词中，启动链只能中心盲点 (640,360) 误点，弹窗
持续阻断主世界确认直至预算耗尽。

## 二、修改方案

1. `MaaEndRuntime._resource_bundle_dirs()` 返回有序 bundle 列表：
   - 默认：`[resource, resource_adb]`
   - CloudCN：`[resource, resource_cloud, resource_adb]`
   `load_resource()` 按序 post；`_strip_comments_in_pipeline` 覆盖全部 bundle 的
   pipeline 目录（含注释的 5 个文件在基础包 `resource/pipeline` 下）。
2. `_CONNECTION_TIMEOUT_S` 20→60，覆盖降级态握手；真正损坏环境最坏多等 40s。
3. `_advance_boot_to_world` 推进按钮期望词补「知道了/知道了」。
4. 本地（gitignore）`resource_cloud/pipeline/OpenGame_Cloud.json` 增加
   `CloudCloseProfile` 自愈节点（识别"权限等阶/探索等级"→`Key [4]` BACK），置于
   启动循环最前，防止残留资料页使 CloudWaitLogo 误命中 "ENDFIELD" 死循环。
   （MaaFW Key 动作 key 必须为整数 keycode 数组，字符串 "BACK" 会 parse 失败。）

## 三、影响面

- 云端全部 TemplateMatch 节点恢复图片解析；场景检测（`__ScenePrivate*`）重新生效。
- 跨 bundle 字段级覆盖经 `get_node_data` 实测：云端显式字段覆盖生效
  （CraftingCreationFinish green_mask false→true）、缺省字段继承基础包
  （__ScenePrivateWorldStorySkip timeout=2000）；node_list=4608。
- 连接在 GPU 占用降级态可成功（实测 17:07 握手成功）。
- AndroidOpenGame 冷启动经「知道了」修复后成功进入主世界（17:23）。

## 四、非期待变化

- 基础包 `resource` 的 CN 节点一并加载（叠加机制固有），由 cloud 覆盖层修正差异；
  实测无冲突、无 "key already exists"。
- 连接最坏失败等待从 20s 增至 60s。
- 个体任务（VisitFriends/DijiangRewards/CreditShoppingN2/DeliveryJobs）进入深层菜单
  后的尾部节点仍需单独校准；且云连接降级（网络差、screencap 超时）时 OCR 验证受损，
  属环境/校准天花板，非本次 infra 阻塞。
