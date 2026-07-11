# 审计批次 77 — Pipeline / 导航 / LLM / 几何

**生成时间**: 2026-07-11 22:30+  
**覆盖文件**: pipeline_node.py, pipeline_loader.py, template_registry.py, client.py, gpu_check.py, scene_geometry.py, task_loader.py, map_data_loader.py, maa_end/runtime.py, runtime.py, entity_db.py  
**审计方法**: 静态代码逻辑分析，无测试执行

---

## 新增发现（6 项）

### PIPELINE-01 — `_loaded_modules` 集合有写入无读取

**等级**: BUG / 中  
**位置**: `pipeline_loader.py:23, 38-41`  
**依赖**: PipelineLoader

```python
self._loaded_modules: Set[str] = set()
self._load_lock = threading.Lock()
# ...
for path in candidates:
    if path.is_file():
        self._load_file(path, graph)
        loaded = True
        break
if not loaded:
    logger.debug(f"Pipeline module not found: {module_name}")
with self._load_lock:
    self._loaded_modules.add(module_name)
return graph
```

**问题**: `_loaded_modules` 受 `_load_lock` 保护并持续累加，但 **`load_module` 的入口处从不检查该集合**。这意味着：

1. 同一模块每次调用 `load_module` 都会重新打开文件、解析 JSON、构建 PipelineNode 对象；
2. 集合仅作为写入计数器，记录已尝试加载的模块名，但无实际功能价值；
3. 如果模块文件较大（如包含大量节点），重复解析会浪费 CPU 和内存。

**建议**: 在 `load_module` 入口添加早期返回：
```python
with self._load_lock:
    if module_name in self._loaded_modules:
        return PipelineGraph()
```

---

### PIPELINE-02 — 无效 recognition 类型静默回退到 DirectHit

**等级**: BUG / 中  
**位置**: `pipeline_node.py:62-64`

```python
raw = data.get("recognition", "DirectHit")
recognition = raw if isinstance(raw, RecognitionType) else RecognitionType(raw) if isinstance(raw, str) and raw in RecognitionType._value2member_map_ else RecognitionType.DirectHit
if recognition == RecognitionType.DirectHit and not raw:
    recognition = RecognitionType.DirectHit
```

**问题**: 当 `raw` 是字符串且不在枚举中时（如 `"InvalidType"`），第 62 行直接回退到 `RecognitionType.DirectHit`，**无任何日志告警**。

后果：
- 畸形的 pipeline JSON 配置（如手误输入 `"recognition": "TemplateMacth"`）会被静默转换为 `DirectHit`；
- `DirectHit` 的含义是"直接命中无需识别"，会导致节点在不匹配任何元素时仍触发 action，产生错误的点击/滑动操作；
- 游戏状态混乱，难以排查。

**建议**: 在 else 分支添加 warning 日志：
```python
else:
    logger.warning(f"Invalid recognition type '{raw}' for node '{name}', fallback to DirectHit")
```

---

### MDL-02 — MapDataLoader 层级条目键缺失导致级联失败

**等级**: 漏洞 / 中  
**位置**: `map_data_loader.py:121`

```python
for lid, lv in levels_raw.items():
    levels[lid] = MapLevel(x=lv["x"], y=lv["y"], width=lv["width"], height=lv["height"])
```

**问题**: 直接通过 `lv["x"]` 等访问 JSON 键值。若 JSON 中某条目缺少 `x` 或 `width` 字段，抛出 `KeyError`，被外层 `except Exception` 捕获后整个布局加载失败（返回 `None`）。

后果：
- 单个畸形的层级条目导致整个地图不可用；
- 导航功能对该地图完全失效，而非跳过问题条目继续加载其余正常条目；
- 与 `grid_tiers`、`bbox_data`、`scene_map` 的防御性写法不一致（它们做了顶层结构校验和条目级校验）。

**建议**: 添加单条目 try/except 或使用 `.get()` 提供默认值。

---

### PL-03 — 死代码 + 日志级别过低掩盖解析错误

**等级**: 代码质量 / 低  
**位置**: `pipeline_loader.py:90-91, 93`

```python
if not node.next and not node.all_of and not node.any_of:
    pass  # ← 死代码
# ...
except Exception as e:
    logger.debug(f"Failed to parse pipeline node '{name}' in {path}: {e}")
```

**问题 1**: `pass` 语句无任何逻辑作用，属于死代码。

**问题 2**: 解析失败仅记录 `debug` 级别日志。正常情况下 debug 日志不可见，意味着：
- 畸形节点被静默跳过；
- 用户不知道哪些节点加载失败；
- 可能期望的自动化步骤未执行，却无任何线索。

**建议**: 删除 `pass` 块（或改为更实质性的检查如是否设置了 max_hit）；将 `logger.debug` 改为 `logger.warning`。

---

### NAV-05 — `find_by_name` 模糊匹配预编译正则无缓存

**等级**: 代码质量 / 低  
**位置**: `entity_db.py:150-157`

```python
def find_by_name(self, name: str, exact: bool = False, limit: int = 50) -> List[Entity]:
    self._ensure_loaded()
    if exact:
        return list(self._by_name.get(name, []))[:limit]
    pattern = re.compile(re.escape(name), re.IGNORECASE)
    results = []
    for key, entities in self._by_name.items():
        if pattern.search(key):
            results.extend(entities)
            if len(results) >= limit:
                break
    return results[:limit]
```

**问题**: 模糊匹配模式下，每次调用都重新编译正则表达式（`re.compile`）。若导航系统高频调用此方法（如遍历附近实体做名称匹配），会造成不必要的性能开销。且对空字符串 `name=""` 时，`re.compile("")` 匹配所有字符串，返回全部实体。

**建议**: 
1. 添加 `if not name.strip(): return []` 前置检查；
2. 若高频调用场景多，考虑缓存编译后的正则。

---

### LLM-01 — health_check 对无 `/v1` 后缀 URL 破坏性拆分

**等级**: 代码质量 / 低  
**位置**: `client.py:74`

```python
url = f"{self._base_url.split('/v1', 1)[0]}/health"
```

**问题**: `health_check` 从 base_url 中剥离 `/v1` 后缀来构建 `/health` 路径。但如果 `base_url` 为 `"http://127.0.0.1:9998"`（无 `/v1`），`split` 返回原字符串，结果是 `"http://127.0.0.1:9998/health"`——这本身没问题。但若 base_url 是 `"http://127.0.0.1:9998/"`（末尾斜杠），`split` 返回 `"http://127.0.0.1:9998/"`，最终 URL 为 `"http://127.0.0.1:9998//health"`（双斜杠）。

此外，`_post` 方法内部使用 `f"{self._base_url}{path}"` 拼接 URL，如果 `base_url` 末尾有斜杠而 path 以 `/` 开头（虽然当前不会），会产生双斜杠。

**建议**: 统一 URL 拼接方式，在 `__init__` 中规范化 `base_url`（去除尾部斜杠），或在拼接时使用 `urllib.parse.urljoin`。

---

## 审计结论（批次 75 / 76）

| 批次 | 审计对象 | 结论 |
|------|---------|------|
| 批次 75 | GUI-05 (tray quit), GUI-04 (硬编码页面名), SEC-03 (非原子写入), GUI-07 (LLM timeout), I18N-04 (硬编码语言), I18N-05 (logger bypass), SEC-04 (models.py), REC-02 (路径错误), GUI-06 (LLM auto-start) | **全部 9 项结论正确，无需修正** |
| 批次 76 | MAA-04 (daemon thread race), MAA-05 (daemon thread race), RUNTIME-01 (save_config), GUI-08 (LLM duplicate), TOKEN-01 (cascading replacement), MAA-06 (redundant cleanup) | **全部 6 项结论正确，无需修正** |

---

## 风险摘要

| 级别 | 数量 | 涉及项 |
|------|------|--------|
| BUG（中） | 2 | PIPELINE-01, PIPELINE-02 |
| 漏洞（中） | 1 | MDL-02 |
| 代码质量（低） | 3 | PL-03, NAV-05, LLM-01 |

**无新发现高风险项。**

本轮审计重点覆盖了 pipeline 引擎、导航数据层、LLM 客户端和几何分析模块。pipeline 加载器存在明显的重复加载和无错误回退问题，map_data_loader 的防御性校验有遗漏区域，这些是功能性 BUG。其余为代码质量改进项。

---

*批次 77 报告 | 仅分析，无文件修改*
