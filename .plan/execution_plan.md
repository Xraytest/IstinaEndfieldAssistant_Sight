# IEA 执行修改报告 — 实施计划

> **范围**：`reports/iea_execution_algorithm_analysis.md` 中的 21 项建议
> **策略**：P0 → P1 → P2 三批执行，每批修改后运行测试
> **文件总数**：涉及 7 个源文件 + 1 个测试文件

---

## 第一批：P0 阻塞性 Bug（5 项，4 个文件）

### P0-1：PipelineRunner._evaluate_and/_evaluate_or 复合条件恒真
- **文件**：`src/core/capability/element_recognition/pipeline/pipeline_runner.py`
- **位置**：L281–L315
- **改动**：从 graph 查找 `sub_name` 对应的真实 `PipelineNode`，复用其 recognition 字段
- **影响**：`_evaluate` 调用点需传递 graph

### P0-2：TaskRunner 缺失 PipelineNode 导入
- **文件**：`src/core/capability/element_recognition/tasks/task_runner.py`
- **位置**：L10
- **改动**：`from ..pipeline import PipelineNode`

### P0-3：VlmWalkNavigator final_dist 恒 success
- **文件**：`src/core/service/navigation/vlm_walk_navigator.py`
- **位置**：L241–L250
- **改动**：`final_dist = -1.0` → `float('inf')`

### P0-4：VlmWalkNavigator JPEG 标记为 PNG
- **文件**：`src/core/service/navigation/vlm_walk_navigator.py`
- **位置**：L299–L301
- **改动**：`cv2.imencode(".jpg", ...)` → `cv2.imencode(".png", ...)`

### P0-5：MaaEndRuntime.connect() 未校验首次截图
- **文件**：`src/core/service/maa_end/runtime.py`
- **位置**：L210–L211
- **改动**：添加 `if not screencap_job.succeeded: ...`

---

## 第二批：P1 性能/稳定性（8 项，5 个文件）

### P1-1：IstinaRuntime LLM 懒加载
- **文件**：`src/core/service/runtime.py`
- **位置**：L130–L140
- **改动**：`_llm_runtime` / `_llm_client` 改为 property 懒加载

### P1-2：IstinaRuntime execute() 配置缓存
- **文件**：`src/core/service/runtime.py`
- **位置**：L269
- **改动**：增加配置缓存与显式 reload 方法

### P1-3：PipelineRunner.run_pipeline() 重试上限
- **文件**：`src/core/capability/element_recognition/pipeline/pipeline_runner.py`
- **位置**：L102–L115
- **改动**：添加最大重试次数与退避延迟

### P1-4：VlmWalkNavigator._is_stuck deque
- **文件**：`src/core/service/navigation/vlm_walk_navigator.py`
- **位置**：L303–L313
- **改动**：`list` → `collections.deque(maxlen=...)`

### P1-5：LlamaServerRuntime 线程安全
- **文件**：`src/core/capability/llm/runtime.py`
- **位置**：L61–L69
- **改动**：添加 `threading.Lock` 保护单例注册

### P1-6：NVML 泄漏修复
- **文件**：`src/cli/handlers.py`
- **位置**：L544–L562, L584–L602
- **改动**：添加 `try/finally` 调用 `pynvml.nvmlShutdown()`

### P1-7：_score_page 预计算 color
- **文件**：`src/core/capability/element_recognition/recognizer.py`
- **位置**：L260–L335
- **改动**：预计算 color signatures 结果

### P1-8：_deduplicate 空间索引
- **文件**：`src/core/capability/element_recognition/recognizer.py`
- **位置**：L341–L363
- **改动**：改用 grid 哈希分桶或 R-tree

---

## 第三批：P2 架构改进（8 项，4 个文件）

### P2-1：公共截图解码
- **文件**：`src/core/service/runtime.py`
- **位置**：L640–L732
- **改动**：抽取 `_decode_image()` 私有方法

### P2-2：统一 serial 解析
- **文件**：`src/core/service/runtime.py`
- **位置**：L88–L89, L154–L160, L174–L180
- **改动**：抽取 `_resolve_serial()` 方法

### P2-3：AndroidRuntimeProxy 代理
- **文件**：`src/core/service/runtime.py`
- **位置**：L96–L121
- **改动**：实现 `__getattr__` 自动转发

### P2-4：清理 Legacy 死代码
- **文件**：`src/core/service/runtime.py`
- **位置**：L148–L151, L243–L249, L396–L400
- **改动**：移除 `self._maaend` legacy 分支

### P2-5：_maaend_clients 缓存清理
- **文件**：`src/core/service/runtime.py`
- **位置**：L250–L258
- **改动**：`disconnect()` 后 `del self._maaend_clients[target]`

### P2-6：handlers.py 截图逻辑重复
- **文件**：`src/cli/handlers.py`
- **位置**：L265–L277, L356–L366, L431–L440
- **改动**：抽取 `_write_or_base64()` 公共函数

### P2-7：_handle_task_run 忽略 timeout
- **文件**：`src/cli/handlers.py`
- **位置**：L280–L293
- **改动**：`params["timeout"] = args.timeout`

### P2-8：Phase 2.5 元素未去重
- **文件**：`src/core/capability/element_recognition/recognizer.py`
- **位置**：L142–L170
- **改动**：3D 场景检测追加后再次调用 `_deduplicate()`

---

## 验证计划

每批修改后：
1. 运行 `pytest tests/ -x` 验证不回归
2. 运行 `python -m py_compile <修改文件>` 检查语法

全部完成后生成 `reports/modification_implementation_report.md`。
