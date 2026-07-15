# 实现报告：读取全部任务列表（ReadAllTasks）全智能任务

**实现日期**：2026-07-15
**任务分类**：全智能（full_intelligence）
**用户需求**：在主世界页点击任务图标（`assets/templates/Baker/TaskOptions.png`）并 OCR 整页，对任务页内容进行有效格式化缓存。

---

## 1. 设计概要

新增全智能分类任务 `ReadAllTasks`（📋读取全部任务列表）。由于 Go agent 是 gitignored 无法注册 custom action，采用与 `MaterialFarm`/`MaterialCollect` 一致的 Python 编排器模式：`IstinaRuntime._run_task` 拦截 `ReadAllTasks` 走 Python 编排，串联 MaaFW pipeline（进入 Baker 界面 → 点击任务图标 → 关闭）与 OCR 整页识别 + 格式化缓存。

### 编排流程

```
ensure_maaend_ready
  → ensure_game_in_world
  → start_scrcpy（供 OCR 截图）
  → 解析选项（ocr_confidence / save_screenshot / dedup_distance）
  → run_pipeline("SceneEnterMenuBaker")        # 进入 Baker 界面
  → run_pipeline("ReadTaskListClickTaskIcon")  # 点击任务图标，切到事务通讯页签
  → time.sleep(1.0)                             # 等待页面稳定
  → execute("scene.elements", enable_ocr=True, enable_template=False, enable_color=False)
  → 过滤 source=="ocr" 且 confidence >= ocr_confidence
  → _format_task_list_ocr                       # 去重 + 行分组 + 排序 + 拼接
  → _cache_task_list                            # 写 cache/task_list/ 最新+历史+截图
  → run_pipeline("CloseButtonType1")            # 关闭返回大世界
```

## 2. 关键设计决策

### 2.1 复用现有 pipeline 节点而非新建

- `SceneEnterMenuBaker`：复用 `assets/pipelines/scene_navigation.json` 中已有的 Baker 入口节点。
- `ReadTaskListClickTaskIcon`：复用 `BAKER.json` 中 `BakerSwitchTask` 的 `roi=[400,0,600,100]` 与模板 `Baker/TaskOptions.png`，但 `next` 设为空数组——点击后立即停止，避免触发 `BakerSwitchTask → BakerCheckHome` 的完整会话流程（会与 OCR 抢占界面）。
- `CloseButtonType1`：复用 `assets/pipelines/close_info.json` 中通用关闭按钮节点。

### 2.2 OCR 后端优化

仅启用 OCR 后端，关闭 template/color 后端以加速识别（任务列表页主要是文本，无需模板/颜色匹配）。通过 `execute("scene.elements", enable_ocr=True, enable_template=False, enable_color=False)` 路由到 `SceneUnderstandingService.analyze_elements`。

### 2.3 格式化策略（_format_task_list_ocr）

1. **过滤空标签**：剔除 label 为空或纯空白的元素。
2. **位置去重**：同 label + 中心点距离 < `dedup_distance`（归一化坐标，默认 0.02）→ 保留置信度最高者。OCR 常对同一文本多次框选，去重避免重复。
3. **阅读顺序排序**：先按 y 分行（行容差 0.04），行内按 x 排序。
4. **行拼接**：同行元素用双空格连接为一条文本行。

返回 `{lines, element_count, row_count}`。

### 2.4 缓存策略（_cache_task_list）

写入 `cache/task_list/` 目录（通过 `get_cache_subdir("task_list")`）：
- `task_list_cache.json`：最新快照（覆盖写）
- `task_list_<YYYYMMDD_HHMMSS>.json`：历史归档（不覆盖，便于回溯）
- `task_list_<YYYYMMDD_HHMMSS>.png`：可选截图（`save_screenshot=True` 时）

每个缓存文件包含 `timestamp / task / status / serial / element_count / row_count / formatted_lines / raw_elements`。

## 3. 文件清单

### 新增

| 文件 | 用途 |
|---|---|
| `assets/pipelines/read_task_list.json` | MaaFW pipeline（ReadTaskListMain 元数据节点 + ReadTaskListClickTaskIcon 点击节点） |
| `assets/tasks/ReadAllTasks.json` | 任务定义（full_intelligence 分组，3 选项，entry=ReadTaskListMain） |
| `reports/implementation/2026-07-15_read_all_tasks_implementation.md` | 本报告 |

### 修改

| 文件 | 改动 |
|---|---|
| `assets/tasks/task_index.json` | 新增 ReadAllTasks 条目（按字母序插入 PuzzleSolver 与 ReadAllWiki 之间） |
| `src/core/service/runtime.py` | 新增 `readtask.run` 路由 + `_run_task` 拦截 ReadAllTasks + `_read_task_list_run`/`_format_task_list_ocr`/`_cache_task_list` 三个方法 |
| `src/cli/handlers.py` | 新增 `_handle_readtask` 路由与独立处理函数 |
| `src/cli/istina.py` | 新增 `readtask run` 子解析器，导入 `_handle_readtask` |
| `src/gui/pyqt6/pages/maaend_control_page.py` | NAME_ZH 新增 `"ReadAllTasks": "📋读取全部任务列表"` |
| `3rd-part/maaend/locales/interface/zh_cn.json` | 新增 11 个 task.ReadAllTasks.* / option.ReadAllTasks* 本地化键 |
| `3rd-part/maaend/locales/interface/en_us.json` | 新增对应 11 个英文本地化键 |
| `docs/TASK_LOG.md` | 追加本次任务日志条目 |

### 同步副本（3rd-part/maaend 为 gitignored，仅运行时同步）

- `3rd-part/maaend/resource/pipeline/read_task_list.json`
- `3rd-part/maaend/tasks/ReadAllTasks.json`
- `3rd-part/maaend/tasks/task_index.json`

## 4. 任务选项

| 选项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `ReadAllTasksOcrConfidence` | input(float) | 0.3 | OCR 置信度阈值，低于此值的文本被过滤 |
| `ReadAllTasksSaveScreenshot` | switch | Yes | 是否额外保存任务页截图到缓存目录 |
| `ReadAllTasksDedupDistance` | input(float) | 0.02 | 位置去重阈值（归一化坐标），同标签且中心点距离小于此值时去重 |

## 5. 验证

### 5.1 静态验证（全部通过）

| 验证项 | 命令 | 结果 |
|---|---|---|
| Python 语法 | `python -m py_compile src/core/service/runtime.py src/cli/handlers.py src/cli/istina.py src/gui/pyqt6/pages/maaend_control_page.py` | exit 0 |
| JSON 合法性 | `python -c "json.load(...)"` 对 6 个 JSON（3 源 + 3 同步副本） | `JSON OK` |
| 本地化键校验 | `python scripts/verify_locale_keys.py` | exit 0（仅输出键对照表，无缺失） |
| Pipeline 节点引用 | 校验 `ReadTaskListMain`/`ReadTaskListClickTaskIcon` 在 read_task_list.json；`SceneEnterMenuBaker` 在 scene_navigation.json；`CloseButtonType1` 在 close_info.json | 全部 OK |
| 任务索引 | `ReadAllTasks` 在 task_index.json | OK |
| 任务定义结构 | group=["full_intelligence"], entry="ReadTaskListMain", 3 options | OK |
| 编排器分发 | `readtask.run` 路由（runtime.py:343-344）+ ReadAllTasks 拦截（runtime.py:419-420） | OK |
| 截图返回类型 | `execute("screenshot")` 返回 `Optional[bytes]`，与 `_cache_task_list` 期望一致 | OK |

### 5.2 端到端测试（已通过，设备 192.168.1.12:16512）

```bash
3rd-part\python\python.exe -m cli.istina readtask run --options "{}" --serial 192.168.1.12:16512
```

**结果**：`status=success`，`raw_ocr_count=21`，`formatted_line_count=9`。

执行步骤全部成功：

| step | status | 备注 |
|---|---|---|
| enter_baker | success | attempt=1（两步进入 + action=Click override） |
| switch_to_task_tab | success | attempt=1（BakerEntry + next 列表 override） |
| ocr | success | raw_count=21 |
| format | success | line_count=9 |
| cache | success | 写入 `cache/task_list/task_list_cache.json` + 历史归档 |
| close | success | CloseButtonType1 返回大世界 |

格式化输出（9 行，按阅读顺序）：

```
//BAKER/事务通讯
司  管理员，刚才收到四  号谷地工人们提出...
巴  来自塞什卡的求助...  管理员，我们收到了
8  过，息壤设施的问...  管理员，庄天师嘱托
来有没有空？有些...  管理员，不知道你近  -请选择会话
管理员。  十分抱歉打扰到您，  ÉMPTY
总桩吗  你现在能马上来一趟
全部显示
20ms  UID: 1439188325
```

缓存文件 `cache/task_list/task_list_cache.json` 含 21 个 `raw_elements`（每个含 label/type/source/confidence/center/bbox/action）+ `formatted_lines` + 元信息（timestamp/task/status/serial/element_count/row_count）。

> 测试过程中发现并修复的两个阻断性缺陷详见第 8 节。

## 6. 影响面

- **新增任务**，不影响现有 DailyFull/Harvest/MaterialFarm/MaterialCollect 等流程。
- `IstinaRuntime.execute` 新增 `readtask.run` 路由，不影响其他命令。
- `_run_task` 新增 `ReadAllTasks` 拦截分支，其他任务名仍走原 MaaFW 路径。
- GUI NAME_ZH 新增一个键，不影响现有任务显示。
- CLI 新增 `readtask` 子命令，不影响现有命令。
- 本地化新增 11 个键（zh_cn/en_us 对称），`verify_locale_keys.py` 通过。

## 7. 非期待变化与已知限制

- **ReadTaskListClickTaskIcon 的 `next` 为空**：与原 `BakerSwitchTask` 不同，点击后不进入 `BakerCheckHome` 会话流程。这是有意设计——OCR 需要稳定停留在任务列表页，不能让 pipeline 继续推进会话。
- **`time.sleep(1.0)` 硬编码等待**：未使用 `post_wait_freezes` 之后的动态等待，因为 OCR 走的是 `scene.elements` 而非 pipeline 节点，pipeline 的 `post_wait_freezes` 不覆盖此场景。1.0 秒为经验值，网络慢/设备慢时可能需要调大。
- **OCR 仅识别当前可视区域**：任务列表若可滚动，单次 OCR 只能读到首屏。本任务不实现滚动翻页读取（用户需求是"OCR 整页"，理解为单页）。
- **格式化行容差 0.04 为经验值**：对任务列表这类行间距规整的界面合适；若任务条目含多行描述，可能误合并。可通过降低 `dedup_distance` 缓解，但行容差目前未作为选项暴露。

## 8. 测试中发现的问题与修复

端到端测试过程中暴露两个阻断性缺陷，均已修复。

### 8.1 OCR-ENTER：Baker 入口 Alt+Click 误触大世界模式切换

- **现象**：`run_pipeline("SceneEnterMenuBaker")` 报成功，但实际未进入 Baker 界面，游戏被切到工业/探索模式（界面状态被破坏，需手动 BACK 键恢复）。
- **根因**：`__ScenePrivateWorldEnterMenuBaker` 节点的原始 `action` 为 `AutoAltClickAction`（Alt+Click）。Baker 图标 ROI `[168,113,101,95]` 落在大世界视图区，Alt+Click 在该区域触发的是模式切换而非打开 Baker 菜单。
- **修复**（`src/core/service/runtime.py` `_read_task_list_run`）：
  1. 通过 `pipeline_override` 将 `__ScenePrivateWorldEnterMenuBaker` 的 `action` 改为普通 `Click`：`runtime.run_pipeline("SceneEnterMenuBaker", {"__ScenePrivateWorldEnterMenuBaker": {"action": "Click"}})`。
  2. 改为两步进入：第一步 `SceneEnterMenuBaker`（action=Click）打开 Baker；第二步 `BakerEntry` 复用原始页签检测流程，并通过 override 其内部节点的 `next` 列表，使流程在命中"事务通讯"界面时停止——`BakerCheckTask.next=[]`（已在事务通讯→停止）、`BakerCheckMsg.next=[BakerSwitchTask]`（在会话消息→点 TaskOptions 切换）、`BakerOverCheck.next=[BakerSwitchTask]`（无会话→点 TaskOptions 切换，不走 BakerOverEnd 退出）、`BakerOverEnd.next=[]`（双重保险防退出）。
  3. 两步各含 3 次重试（间隔 2.0s）。

### 8.2 OCR-API：maafw Python 绑定 API 误用导致 OCR 始终返回空（根因）

- **现象**：两步 Baker 进入全部成功后，OCR 步骤秒级返回 `raw_count=0`，格式化行数为 0。但 `3rd-part/maaend/config/debug/maafw.log` 显示 C++ 层 OCR 实际成功识别 22 条文本（含 "//BAKER/事务通讯"、"全部显示"、"来自塞什卡的求助..." 等，置信度 0.9+）。
- **根因**：`src/core/capability/element_recognition/backends/ocr_backend.py` 的 `_run_maafw_ocr` 旧实现：
  ```python
  detail = job.get()          # 返回 TaskDetail（含 node_id_list），非 RecognitionDetail
  if not detail or not detail.hit:   # ← TaskDetail 无 .hit → AttributeError
  ```
  `job.get()` 返回的是 `TaskDetail`（任务级详情，含 `task_id`/`node_id_list`），而非 `RecognitionDetail`（识别级详情）。代码却直接访问 `.hit/.best_result/.all_results` 这些仅存在于 `RecognitionDetail` 的字段，触发 `AttributeError`；该异常被 `OCRBackend.recognize` 外层的 `try/except Exception: logger.debug(...)` 静默吞掉，导致 OCR 永远返回空列表，无任何可见报错。
- **正确的 maafw API 路径**：
  ```
  tasker.post_recognition(JRecognitionType.OCR, JOCR, image) -> TaskJob
  job.wait()                              # 必须显式 wait，否则 node_id_list 为空
  task_detail = job.get()                 # -> TaskDetail
  node_detail = tasker.get_node_detail(task_detail.node_id_list[0])  # -> NodeDetail
  detail = node_detail.recognition        # -> RecognitionDetail（真正的 OCR 详情）
  detail.hit / detail.best_result / detail.all_results
  ```
- **修复**：重写 `_run_maafw_ocr` 按上述路径取 `RecognitionDetail`，并保留 `task_id` 兜底（`node_id_list` 为空时通过 `get_task_detail(task_id)` 重查一次）。
- **影响范围**：此为通用修复，惠及所有依赖 `OCRBackend.recognize` 的链路——`scene.elements` 命令、VLM 导航的 OCR 辅助、其他 OCR 场景。修复前这些链路的 maafw OCR 路径均实际失效（ silently 返回空）。

### 8.3 诊断过程要点

- 通过 `3rd-part/maaend/config/debug/maafw.log` 确认 C++ 层 OCR 成功（22 条结果），定位问题在 Python 绑定读取层而非识别层。
- 日志中 `image=[720,1280,16]` 的 `16` 是 OpenCV 类型码（CV_8UC3=16），非通道数，图像为正常 BGR 3 通道，非异常。
