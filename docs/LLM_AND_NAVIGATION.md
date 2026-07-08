# LLM 与导航

## 1. LLM 性能调优

### 1.1 当前配置

- **模型**: `models/LLM/Qwen3.5-4B-UD-Q4_K_XL.gguf`
- **上下文长度**: 32768
- **Flash Attention**: 启用 (`-fa on`)
- **KV 量化**: q8_0 (`-ctk q8_0 -ctv q8_0`)
- **KV Cache**: GPU 显存（KV offload 开启）
- **GPU 层数**: 全 offload (`-ngl 999`)
- **推理模式**: CUDA
- **batch_size / ubatch_size**: 2048 / 1024
- **no_repack / no_cont_batching**: 启用

### 1.2 修复前后的性能对比

| 配置 | context | KV Cache 位置 | 实测 TPS | 显存占用 |
|------|---------|---------------|----------|----------|
| ❌ 修复前 | 64000 | CPU RAM (PCIe) | ~30 | ~2.5 GB (仅模型) |
| ✅ 修复后 | 32768 | GPU VRAM | ~75 | ~4.0 GB (模型 + KV) |

### 1.3 修复内容

#### 根因：`--no-kv-offload` 导致 KV Cache 留在 CPU RAM

修复前配置 `disable_kv_offload: true`，等价于传递 `--no-kv-offload`：

```
每 token 推理:
  for each layer:
    K/V: CPU RAM → PCIe → GPU VRAM  ← 12 GB/s 瓶颈
    计算 Attention
    新 K/V: GPU VRAM → PCIe → CPU RAM
  40 层 → 大量 PCIe 传输 → TPS 被压制到 ~30
```

修复后移除了 `--no-kv-offload`，KV Cache 分配在 GPU VRAM（~400-900 GB/s 带宽），消除 PCIe 瓶颈。

#### 次要修复

| 修改 | 原因 |
|------|------|
| `context_size`: 64000 → 32768 | 32k q8_0 KV Cache ≈ 2.7GB，适配 8GB 显存 |
| `cache_ram_mb: 0` → 移除 | `-cram 0` 与 KV offload 冲突 |
| 新增 `batch_size: 2048` | 增大 prompt 处理批大小，加速 prefill |
| 新增 `ubatch_size: 1024` | 增大内部推理微批大小 |
| 新增 `no_repack: true` | 避免 KV cache 重排开销 |
| 新增 `no_cont_batching: true` | 单请求场景禁用 continuous batching |
| `threads`: 8 → 12 | 提升 CPU 侧 prompt 处理并行度 |
| `flash_attention`: "auto" → "on" | 显式启用，降低显存带宽需求 |

### 1.4 显存占用明细（32768 context）

```
模型权重 (Q4_K_XL, 4B):      ≈ 2.5 GB
KV Cache (q8_0, 32k):        ≈ 2.7 GB
其他中间缓冲区:                ≈ 0.5 GB
─────────────────────────────────
总计:                         ≈ 5.7 GB  ← 8GB 显存可容纳
```

### 1.5 推荐配置

```json
{
  "llm": {
    "enabled": true,
    "model_path": "models/LLM/Qwen3.5-4B-UD-Q4_K_XL.gguf",
    "port": 9998,
    "n_gpu_layers": 999,
    "context_size": 32768,
    "threads": 12,
    "temperature": 0.3,
    "flash_attention": "on",
    "kv_cache_type": "q8_0",
    "batch_size": 2048,
    "ubatch_size": 1024,
    "no_repack": true,
    "no_cont_batching": true
  }
}
```

#### 启动参数（等价）
```bash
llama-server.exe \
  -m models/LLM/Qwen3.5-4B-UD-Q4_K_XL.gguf \
  --port 9998 \
  -c 32768 \
  -b 2048 -ub 1024 \
  --threads 12 \
  --temp 0.3 \
  -ngl 999 --n-gpu-layers 999 \
  -fa on \
  -ctk q8_0 -ctv q8_0 \
  --no-repack \
  --no-cont-batching \
  -np 1
```

### 1.6 注意事项

#### 切换上下文长度
- **32k 以内**：KV Cache 放 GPU 显存，性能最佳（~75 TPS）
- **超过 32k**：需在配置中设置 `disable_kv_offload: true`，KV Cache 回退到 CPU RAM（TPS 降至 30-40）

#### 显存不足处理
若显卡显存 < 8GB，建议进一步降低 context_size 或使用 Q4_0 KV 量化：
```json
"kv_cache_type": "q4_0",
"context_size": 16384
```

---

## 2. LLM & Navigation 层问题

### High

1. **`LlamaServerRuntime` atexit 清理硬编码端口**
   `runtime.py:42` 固定 `[9998]`，若配置改端口则失效。
   **修复**：实例级维护端口列表。

### Medium

3. **`model` 硬编码为 `"local"`**
   `client.py:50`。若服务端启用严格模型校验会 400。
   **修复**：从配置或 `/v1/models` 动态获取。

4. **`subprocess.Popen` 使用 `PIPE` 死锁风险**
   `runtime.py:279` 长时间运行进程未消费 stdout/stderr。
   **修复**：重定向到 `DEVNULL` 或文件。

5. **`to_coords_vlm` 的 `level_id` 回退策略不一致**
   `navigator.py:233,243` 硬编码 `"lv001"`，而 `to_coords` 使用 `_resolve_current_level`。
   **修复**：VLM 路径复用当前层级推断。

### Low

6. **重复 GPU 参数**
   `runtime.py:231-232` 同时传 `-ngl` 与 `--n-gpu-layers`。
   **修复**：保留其一。

7. **`_resolve_current_level` 对空字符串过于保守**
   `navigator.py:325-330` 空字符串返回 `None`。
   **修复**：明确空字符串与 `None` 的语义。

8. **截图/解码逻辑重复**
   `Navigator._get_frame` 与 `VlmWalkNavigator._grab_frame` 完全相同。
   **修复**：提取为公共函数。

9. **`import time` 在循环内部**
   `runtime.py:588`。
   **修复**：移到模块顶部。

---

## 3. 导航系统差异（详细）

### IEA — 三层导航

| 层级 | 名称 | 技术 | 文件 |
|------|------|------|------|
| **Nav1** | MaaEnd 原生导航 | MaaEnd `MapTracker` 任务 | `MaaEndRuntime.run_task()` |
| **Nav2** | scrcpy 视觉导航 | 小地图识别 + navmesh | `navigation/minimap_locator.py`, `navigator.py`, `entity_db.py`, `map_data_loader.py` |
| **Nav3** | VLM 驱动行走 | llama-server 视觉推理 | `navigation/vlm_walk_navigator.py` |

IEA 的导航更偏向**研究与探索**（VLM 理解、实体查询、坐标导航）。

### MaaEnd — C++ 算法导航

MaaEnd 的导航主要由 C++ 实现：

| 组件 | 职责 |
|------|------|
| `cpp-algo/source/MapLocator/` | AI+CV 小地图定位（YOLO 预测器、运动追踪、匹配策略） |
| `cpp-algo/source/MapNavigator/` | 高精度自动导航（A* 寻路、动作执行器、采集扫描器） |
| `cpp-algo/source/EssenceGridScan/` | 基质网格识别与滚动扫描 |
| `cpp-algo/source/RecoGrid/` | 网格识别与滚动累计扫描引擎 |
| `cpp-algo/source/Navmesh/` | 导航网格 |

MaaEnd 的导航更偏向**游戏内自动化**（自动寻路、自动战斗、自动采集）。

---

## 4. 修复优先级建议

### P0 — 立即修复
- [ ] `LlamaServerRuntime` atexit 清理改为实例级端口列表

### P1 — 本次迭代
- [ ] `model` 从配置动态获取
- [ ] `subprocess.Popen` 重定向到 DEVNULL
- [ ] `to_coords_vlm` 复用 `_resolve_current_level`

### P2 — 后续清理
- [ ] 删除重复 GPU 参数
- [ ] 明确 `_resolve_current_level` 空字符串语义
- [ ] 提取公共截图解码函数
- [ ] `import time` 移到模块顶部
