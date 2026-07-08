# 识别、Pipeline 与任务系统

## 1. Element Recognition & Task 层问题

### High

1. **`PipelineRunner` 泄漏 MaaFW 运行时耦合**
   `pipeline_runner.py:29` 名为通用图执行器，却直接导入并调用 `maa.tasker`、`maa.pipeline`（lines 19-20, 173, 246）。
   **修复**：提取 `MaaFWMatcherAdapter` 并注入。

2. **`TaskRunner` 无法向 `PipelineRunner` 注入 `maa_tasker`**
   `task_runner.py:16-24` 构造默认 `PipelineRunner()` 时无 `maa_tasker` 参数，导致任务执行永久锁定 OpenCV 回退，而元素识别可使用 MaaFW。
   **修复**：向 `TaskRunner.__init__` 添加 `maa_tasker` 并转发。

### Medium

3. **`SceneUnderstandingService` 死参数 `template_threshold`**
   `scene_service.py:27` 接收但未转发给 `EndfieldElementRecognizer`。
   **修复**：移除或转发。

4. **`_evaluate_and`/`_evaluate_or` 使用伪造 `DirectHit` 节点 hack**
   `pipeline_runner.py:309-343` 创建假 `PipelineNode` 仅用于按字符串解析子节点名，语义不清。
   **修复**：改为直接按名称查找图节点。

5. **`_wait_for_freeze()` 空实现**
   `pipeline_runner.py:378-380` 为 `pass`，静默忽略配置。
   **修复**：实现或删除配置项。

6. **`ColorBackend.recognize_gameplay_scene()` 职责错位**
   `color_backend.py:97` 执行 3D 场景理解（蓝色占比、肤色检测），不属于颜色匹配。
   **修复**：迁移到 `SceneGeometryAnalyzer`。

### Low

7. **模块 docstring 声称 "5 种识别技术"**
   `recognizer.py:4-9` 将页面分类列为第 5 种后端，实际是后处理步骤。
   **修复**：修正描述。

8. **`SceneUnderstandingService` 与 `EndfieldElementRecognizer` YOLO 默认值不一致**
   Service 默认 `False`，Recognizer 默认 `True`。
   **修复**：统一或文档说明。

9. **`OCRBackend.set_maa_tasker()` 死 API**
   从未被调用，`maa_tasker` 总通过构造函数传入。
   **修复**：删除。

10. **`YOLOBackend.is_loaded()` 暴露但无人消费**
    **修复**：删除或内部使用。

11. **`TemplateBackend._match_single()` SIFT 阈值魔法数**
    `threshold * 20` 无注释解释单位转换。
    **修复**：添加常量或注释。

---

## 2. IEA 识别后端

```python
class EndfieldElementRecognizer:
    def __init__(self):
        self._backends = [
            TemplateBackend(),   # OpenCV SIFT + MaaFW 双路由
            OCRBackend(),        # MaaFramework OCR (JOCR)
            ColorBackend(),      # HSV 颜色空间轮廓检测
            YOLOBackend(),       # YOLO11 游戏对象检测
        ]
```

- **模板匹配**：OpenCV SIFT 特征 + 直接匹配，同时集成 MaaFramework `post_recognition`
- **OCR**：MaaFramework 内置 OCR (JOCR)
- **颜色分析**：HSV 颜色空间轮廓检测
- **YOLO**：Ultralytics YOLO11 推理
- **场景分类**：`SceneUnderstandingService` 综合多源结果，通过评分签名（required elements、color、OCR keywords、fallback）分类页面
- **页面历史**：维护页面历史栈和 dominant-page 追踪

## 3. MaaEnd 资源驱动识别

MaaEnd 的场景识别完全依赖：
- `assets/resource/image/` 中的模板图片（按功能分目录，基准分辨率 1280x720）
- MaaFramework 原生的 `TemplateMatch`、`OCR`、`ColorMatch` pipeline 节点
- 识别逻辑硬编码在 pipeline JSON 中
- 支持绿幕模板处理

## 4. IEA Pipeline 引擎

- **`PipelineNode`**：数据类表示识别/操作节点，支持 `DirectHit`、`TemplateMatch`、`OCR`、`ColorMatch`、`And`、`Or` 识别类型
- **`PipelineGraph`**：有向图，支持入口解析
- **`PipelineLoader`**：从 `assets/pipelines/` 和 MaaEnd 的 `resource/pipeline/nodes.json` 加载
- **`PipelineRunner`**：执行 Pipeline 图，支持限流、最大命中次数、前置/后置延迟、冻结等待
- **双路由模板匹配**：优先 MaaFramework 原生识别，失败则回退到 OpenCV

## 5. MaaEnd Pipeline FSM

MaaEnd 的 Pipeline 是 MaaFramework **Pipeline 协议**的扩展，核心是**有限状态机(FSM)**：

```json
{
    "NodeName": {
        "recognition": {"type": "TemplateMatch", "param": {...}},
        "action": {"type": "Click"},
        "next": ["NextNode", "[JumpBack]SceneManager"],
        "pre_delay": 0, "post_delay": 0
    }
}
```

**MaaEnd 编码规范（关键规则）**：
- **禁止硬延迟**：不用 `pre_delay`/`post_delay`，优先用中间识别节点
- **首轮命中**：扩充 `next` 列表，确保一次截图就命中
- **原子化操作**：每步操作都有独立识别节点
- **OCR 完整文本**：`expected` 必须写完整文本，禁止写片段

**万能场景跳转（SceneManager / [JumpBack]）**：
- `SceneAnyEnterWorld`：从任意界面进入任意大世界
- `SceneEnterMenuRegionalDevelopment`：从任意界面进入地区建设菜单
- `[JumpBack]` 语法：无法识别时回退到更基础场景
- 公开接口（`Interface/`）供任务使用，私有实现（`SceneManager/`）禁止直接引用

## 6. 任务定义方式

### IEA 动态构建

```python
# src/core/service/maa_end/runtime.py
class MaaEndRuntime:
    def load_tasks(self):
        # 递归扫描 MaaEnd/assets/tasks/**/*.json
        # 提取 task 列表和全局 option 定义
        # 构建 self._tasks: Dict[name, task_def]

    def build_pipeline_override(self, task_name, options):
        # 根据 option 定义（switch/checkbox/select/input）
        # 动态生成 pipeline_override
        # 支持嵌套选项和 {token} 替换
```

IEA 在 Python 中**动态构建** pipeline override，这意味着：
- 可以在运行时灵活调整选项
- 支持 IEA 特有的导航参数（如 `nav.to_coords`）
- 不依赖 MaaEnd 的编译流程
- IEA 自身也有精简版 `assets/tasks/` 和 `assets/pipelines/`（约 12 个模块），但核心执行已迁移到 MaaEnd

### MaaEnd 静态 JSON

```json
// assets/tasks/DailyRewards.json
{
    "task": [{
        "name": "DailyRewards",
        "entry": "DailyRewardStart",
        "option": ["DailyEmailRewards", "DailyTaskRewards", ...],
        "controller": ["Win32-Front", "ADB", "PlayCover", "Wlroots"],
        "group": ["other_menu"]
    }],
    "option": {
        "DailyEmailRewards": {
            "type": "switch",
            "cases": [{
                "name": "Yes",
                "pipeline_override": {"DailyEmailRewardSub": {"enabled": true}}
            }]
        }
    }
}
```

MaaEnd 的任务是**静态 JSON**，通过 MaaFramework 的 `Tasker.post_task()` 直接执行。option 系统支持：
- **switch**：布尔开关，启用/禁用 Pipeline 子节点
- **checkbox**：多选，激活多个 case
- **select**：单选，选择执行路径
- **input**：用户输入，支持 `{token}` 替换和正则校验

## 7. 预设（Preset）系统

MaaEnd 的预设是任务序列：

```json
// assets/tasks/preset/DailyFull.json
{
  "preset": [
    {"name": "VisitFriends", "option": {...}},
    {"name": "DijiangRewards", "option": {...}},
    {"name": "CreditShoppingN2", "option": {...}},
    {"name": "DeliveryJobs", "option": {...}},
    {"name": "SellProduct"},
    {"name": "AutoStockpile"},
    {"name": "AutoStockStaple"},
    {"name": "AutoSell"},
    {"name": "EnvironmentMonitoring"},
    // ... 20+ tasks
  ]
}
```

MaaEnd 提供 3 个预设：`DailyFull`（全套日常）、`QuickDaily`（快速日常）、`RealtimeAssist`（实时开荒辅助）。

## 8. 修复优先级建议

### P0 — 立即修复
- [ ] `PipelineRunner` 提取 `MaaFWMatcherAdapter` 并注入
- [ ] `TaskRunner` 支持注入 `maa_tasker`

### P1 — 本次迭代
- [ ] `SceneUnderstandingService` 移除或转发 `template_threshold` 死参数
- [ ] `_evaluate_and`/`_evaluate_or` 改为直接按名称查找图节点
- [ ] `_wait_for_freeze()` 实现或删除配置项

### P2 — 后续清理
- [ ] `ColorBackend.recognize_gameplay_scene()` 迁移到 `SceneGeometryAnalyzer`
- [ ] 修正模块 docstring 描述
- [ ] 统一 YOLO 默认值
- [ ] 删除 `OCRBackend.set_maa_tasker()` 死 API
- [ ] 删除或内部使用 `YOLOBackend.is_loaded()`
- [ ] `TemplateBackend._match_single()` SIFT 阈值添加常量或注释
