# LLM 推理模块性能说明

## 当前配置

- **模型**: `models/LLM/Qwen3.5-4B-UD-Q4_K_XL.gguf`
- **上下文长度**: 32768
- **Flash Attention**: 启用 (`-fa on`)
- **KV 量化**: q8_0 (`-ctk q8_0 -ctv q8_0`)
- **KV Cache**: GPU 显存（KV offload 开启）
- **GPU 层数**: 全 offload (`-ngl 999`)
- **推理模式**: CUDA
- **batch_size / ubatch_size**: 2048 / 1024
- **no_repack / no_cont_batching**: 启用

## 修复前后的性能对比

| 配置 | context | KV Cache 位置 | 实测 TPS | 显存占用 |
|------|---------|---------------|----------|----------|
| ❌ 修复前 | 64000 | CPU RAM (PCIe) | ~30 | ~2.5 GB (仅模型) |
| ✅ 修复后 | 32768 | GPU VRAM | ~75 | ~4.0 GB (模型 + KV) |

## 修复内容

### 根因：`--no-kv-offload` 导致 KV Cache 留在 CPU RAM

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

### 次要修复

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

## 显存占用明细（32768 context）

```
模型权重 (Q4_K_XL, 4B):      ≈ 2.5 GB
KV Cache (q8_0, 32k):        ≈ 2.7 GB
其他中间缓冲区:                ≈ 0.5 GB
─────────────────────────────────
总计:                         ≈ 5.7 GB  ← 8GB 显存可容纳
```

## 推荐配置

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

### 启动参数（等价）
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

## 注意事项

### 切换上下文长度
- **32k 以内**：KV Cache 放 GPU 显存，性能最佳（~75 TPS）
- **超过 32k**：需在配置中设置 `disable_kv_offload: true`，KV Cache 回退到 CPU RAM（TPS 降至 30-40）

### 显存不足处理
若显卡显存 < 8GB，建议进一步降低 context_size 或使用 Q4_0 KV 量化：
```json
"kv_cache_type": "q4_0",
"context_size": 16384
```
