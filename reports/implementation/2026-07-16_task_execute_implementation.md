# 2026-07-16 全智能·任务执行 TaskExecute 实现报告

## 1. 背景与目标

用户要求完善"全智能"分类：
1. 先执行"任务列表读取"并在 GUI 展示读取到的任务，用户可选择需要完成什么任务，任务分类与游戏内一致（进行中/ALL/紧要/重要/次要）。
2. 构建"任务执行"全智能任务，完成全部的（逐一）次要任务（任务列表内的一个分类），通过大量 VLM 参与和对任务列表的频繁检查确认 VLM 真的完成了任务。

设计决策（用户通过 AskUserQuestion 明确）：
- **任务注册方式**：将全智能分类的任务单独区分（新建 TaskExecute 任务定义，与 ReadAllTasks 并列）。
- **GUI 选择粒度**：分类+任务双选(checkbox)——分类作为父节点，任务作为子节点带复选框。
- **实现范围**：全部——泛化所有分类，默认次要。

## 2. 架构设计

### 2.1 Python 编排器模式

与 MaterialFarm/MaterialCollect/ReadAllTasks 一致，TaskExecute 不走 MaaFW 单一 pipeline，而是由 `IstinaRuntime._run_task` 拦截 `TaskExecute` 任务名，调用 `_run_category_tasks` 编排：
1. 进入任务列表页（复用 ReadAllTasks 的 `_open_task_list_if_needed`）
2. 若提供 `selected_tasks`：仅执行选中任务；否则点击目标分类标签读取该分类全部任务
3. 对每个任务：切到所属分类 → 点击任务条目 → 开始追踪 → 关闭任务列表 → VLM `nav3.walk_tracking` 导航 → 交互（F 键）→ 频繁验证循环（重新打开任务列表 → 切回分类 → 读取 → 检查任务是否消失）
4. 返回 `completed_tasks` / `failed_tasks`

### 2.2 双入口设计

- **任务树运行 TaskExecute**：读 TaskExecuteCategory 复选框（5 cases，default 次要），执行该分类全部任务。
- **GUI「执行选中任务」按钮**：传 `selected_tasks` 列表（`[{name, category, center}]`），仅执行勾选任务。

### 2.3 分类标签定位

游戏内任务列表左侧栏有 5 个分类标签：进行中 / ALL / 紧要 / 重要 / 次要。
- **OCR 动态检测**：`_click_category_by_name` 通过 OCR 检测左侧栏（归一化 x<0.12）分类文本，点击其中心。
- **兜底坐标**：`_CATEGORY_COORD_FALLBACK = {"次要": (40, 285)}`（仅"次要"经扫描验证，其余分类依赖 OCR）。

## 3. 文件改动清单

### 3.1 源代码（git 跟踪）

| 文件 | 改动类型 | 说明 |
|---|---|---|
| `src/core/service/runtime.py` | 修改 | 路由扩展 + TaskExecute 拦截 + 5 个新方法 + 1 个重命名 |
| `src/cli/handlers.py` | 修改 | `_handle_readtask` action 校验扩展 |
| `src/cli/istina.py` | 修改 | 新增 `run_category` / `list_categorized` 子解析器 |
| `src/gui/pyqt6/pages/maaend_control_page.py` | 修改 | NAME_ZH + 按分类读取按钮 + 复选框树 + 执行选中任务 + 5 个新方法 |
| `src/gui/pyqt6/locales/zh_CN.json` | 修改 | 7 个新 GUI locale 键 |
| `src/gui/pyqt6/locales/en_US.json` | 修改 | 7 个新 GUI locale 键 |
| `assets/tasks/TaskExecute.json` | 新增 | TaskExecute 任务定义（4 选项） |
| `assets/pipelines/task_execute.json` | 新增 | TaskExecuteMain 元数据入口节点 |
| `assets/tasks/task_index.json` | 修改 | 注册 TaskExecute 条目 |
| `docs/TASK_LOG.md` | 修改 | 追加本次任务记录 |
| `reports/implementation/2026-07-16_task_execute_implementation.md` | 新增 | 本报告 |

### 3.2 运行时副本（gitignored，严禁上传）

| 文件 | 改动类型 | 说明 |
|---|---|---|
| `3rd-part/maaend/resource/pipeline/task_execute.json` | 新增 | pipeline 副本 |
| `3rd-part/maaend/tasks/TaskExecute.json` | 新增 | 任务定义副本 |
| `3rd-part/maaend/tasks/task_index.json` | 修改 | 注册 TaskExecute 条目 |
| `3rd-part/maaend/locales/interface/zh_cn.json` | 修改 | 21 个 TaskExecute locale 键 |
| `3rd-part/maaend/locales/interface/en_us.json` | 修改 | 21 个 TaskExecute locale 键 |

## 4. 关键实现细节

### 4.1 Runtime 泛化（`src/core/service/runtime.py`）

**路由扩展**（execute 方法）：
```python
if domain == "readtask" and action == "run_category":
    return self._run_category_tasks(params)
if domain == "readtask" and action == "list_categorized":
    return self._list_categorized_tasks(params)
```

**TaskExecute 拦截**（_run_task 方法）：
```python
if name == "TaskExecute":
    result = self._run_category_tasks(params)
    return bool(result.get("status") == "success")
```

**`_run_category_tasks` 选项解析**（TaskExecute* 为主，BlueTask* 兼容）：
```python
cat_opt = options.get("TaskExecuteCategory")
if isinstance(cat_opt, list):
    category = cat_opt[0] if cat_opt else "次要"
elif cat_opt:
    category = str(cat_opt)
else:
    category = str(options.get("category", "次要")) or "次要"
selected_tasks = options.get("selected_tasks")
vlm_max_steps = int(options.get("TaskExecuteVlmMaxStepsValue", options.get("BlueTaskVlmMaxStepsValue", 60)))
```

**`_execute_category_task` 频繁验证循环**：
```python
for check_idx in range(max_verification_checks):
    # 重新打开任务列表 → 切回分类 → 读取 → 检查任务是否消失
    if task_name not in current_task_names:
        return {"status": "success", ...}
    time.sleep(2.0)
return {"status": "error", "message": f"任务未在 {max_verification_checks} 次检查后消失"}
```

### 4.2 GUI 复选框树（`src/gui/pyqt6/pages/maaend_control_page.py`）

**分类+任务双选树构建**：
```python
cat_item = QTreeWidgetItem(self._task_list_tree, [cat_name])
cat_item.setFlags(cat_item.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)
cat_item.setCheckState(0, Qt.CheckState.Unchecked)
for t in tasks:
    child = QTreeWidgetItem(cat_item, [tname])
    child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
    child.setCheckState(0, Qt.CheckState.Unchecked)
```

**父节点勾选→子任务全选/全不选**（带防递归）：
```python
def _on_task_list_tree_item_changed(self, item, column):
    if self._task_list_tree_blocks_signal:
        return
    data = item.data(0, Qt.ItemDataRole.UserRole) or {}
    if data.get("kind") != "category":
        return  # 子任务勾选变化由 ItemIsAutoTristate 自动处理父节点三态
    new_state = item.checkState(0)
    self._task_list_tree_blocks_signal = True
    try:
        for i in range(item.childCount()):
            item.child(i).setCheckState(0, new_state)
    finally:
        self._task_list_tree_blocks_signal = False
```

**执行选中任务**：
```python
selected = self._collect_selected_tasks()  # [{name, category, center}]
options = {"selected_tasks": selected}
result = self._sync_execute("readtask.run_category", {"serial": serial, "options": options}, timeout_ms=900000)
```

## 5. 验证

### 5.1 静态校验

| 校验项 | 命令 | 结果 |
|---|---|---|
| Python 语法 | `3rd-part\python\python.exe -m py_compile src\core\service\runtime.py src\cli\handlers.py src\cli\istina.py src\gui\pyqt6\pages\maaend_control_page.py` | exit 0 |
| JSON 合法性 | `json.load` 10 个 JSON 文件 | 全部 `JSON OK` |
| Locale 键对称 | `scripts\verify_locale_keys.py` | exit 0 |

### 5.2 端到端测试（待用户执行）

**CLI 测试**：
```bash
# 按分类读取
3rd-part\python\python.exe src\cli\istina.py readtask list_categorized --serial 192.168.1.12:16512

# 执行次要分类全部任务
3rd-part\python\python.exe src\cli\istina.py readtask run_category --options "{\"category\":\"次要\"}" --serial 192.168.1.12:16512

# 执行选中任务
3rd-part\python\python.exe src\cli\istina.py readtask run_category --options "{\"selected_tasks\":[{\"name\":\"拍摄一群蓄水源石虫\",\"category\":\"次要\"}]}" --serial 192.168.1.12:16512
```

**GUI 测试**：
1. 启动 GUI：`3rd-part\python\python.exe src\gui\pyqt6\main.py`
2. 连接设备
3. 任务列表卡片 → 点击「按分类读取」→ 复选框树展示 5 个分类及其任务
4. 勾选要执行的分类或任务 → 点击「执行选中任务」
5. 观察日志和结果弹窗

## 6. 影响面分析

### 6.1 正面影响

- 新增全智能任务 TaskExecute，与 ReadAllTasks 互补（读取 + 执行）。
- GUI 用户可按游戏内分类分组查看任务并选择性执行，不再只能全量执行次要分类。
- CLI 新增 `run_category` / `list_categorized` 子命令，支持脚本化按分类执行。
- Runtime 泛化支持任意分类，为未来扩展（如执行"紧要"分类）奠定基础。

### 6.2 向后兼容

- `_run_blue_tasks` / `readtask.run_blue` / `readtask.list_blue` 保留，行为不变（仅次要分类）。
- `_run_blue_tasks_btn` 变量名保留（项目记忆约束），仅文案改为「执行选中任务」。
- 原「读取任务列表」按钮（平铺展示）保留，新增「按分类读取」按钮（复选框树展示）。
- TaskExecute 任务定义使用 `$task.TaskExecute.*` / `$option.TaskExecute*` 本地化键，与现有任务无冲突。

### 6.3 风险点

- **分类标签坐标**：仅"次要"(40,285) 经扫描验证，其余分类依赖 OCR 动态检测。若 OCR 误识别左侧栏其他 UI 元素为分类标签，可能点击错误位置。缓解：`_CATEGORY_COORD_FALLBACK` 兜底 + OCR 置信度过滤。
- **频繁验证循环耗时**：每个任务执行后最多 `max_verification_checks`（default 5）次重新打开任务列表检查，每次约 5-8 秒，5 次 = 25-40 秒/任务。若分类有 N 个任务，总验证耗时约 N×30 秒。缓解：用户可通过 `TaskExecuteMaxVerifyChecks` 选项调整。
- **VLM 导航成功率**：依赖 `nav3.walk_tracking` 通过 VLM 识别任务追踪标识自主导航。若任务追踪标识不可见或 VLM 误判方向，可能导致导航失败。缓解：`TaskExecuteVlmMaxSteps`（default 60）限制单任务步数，避免无限循环。

## 7. 非期待变化

- `_run_blue_tasks_btn` 变量名保留未改（项目记忆约束），仅文案改为「执行选中任务」。
- `_run_blue_tasks` 方法名保留，内部逻辑改为执行选中任务（原逻辑为执行次要分类全部任务）。
- `ItemIsAutoTristate` 在 PyQt6 中自动处理子节点→父节点三态更新，`_on_task_list_tree_item_changed` 中子任务勾选变化时直接 return，无需手动同步父节点。
- 分类标签坐标仅"次要"经扫描验证，其余分类依赖 OCR 动态检测+兜底坐标方案（未来可通过扫描验证补充其他分类坐标）。
- 3rd-part/maaend 下的运行时副本同步不会被 git 跟踪（.gitignore 排除），符合"严禁上传3rd-part"硬约束。

## 8. 后续工作建议

1. **端到端设备测试**：在真实设备上验证 TaskExecute 全流程（按分类读取 → 勾选 → 执行 → 频繁验证）。
2. **分类标签坐标补全**：通过扫描验证补充"进行中"/"ALL"/"紧要"/"重要"的兜底坐标，降低对 OCR 的依赖。
3. **VLM 导航优化**：若频繁验证循环发现任务未完成率较高，可考虑增加 VLM 步数或优化追踪标识识别 prompt。
4. **GUI 复选框树增强**：可考虑添加「全选/全不选」按钮、「按分类筛选」下拉框等便捷操作。
