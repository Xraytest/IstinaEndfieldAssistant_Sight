# IEA 纯本地版本改造方案

> 版本：1.0  
> 日期：2026-06-14  
> 目标：为 IEA 创建完全脱离 IstinaPlatform 服务端的个人本地版本

---

## 📋 文档导航

| 文档 | 用途 | 读者 |
|------|------|------|
| **本文档** | 改造方案总览 | 所有人 |
| [LOCAL_ONLY_MIGRATION.md](LOCAL_ONLY_MIGRATION.md) | 架构设计和改造范围 | 架构师/开发者 |
| [LOCAL_ONLY_IMPLEMENTATION.md](LOCAL_ONLY_IMPLEMENTATION.md) | 详细代码实现 | 开发者 |
| [LOCAL_ONLY_DEPENDENCY_MAP.md](LOCAL_ONLY_DEPENDENCY_MAP.md) | 83 处依赖完整清单 | 开发者 |
| [LOCAL_ONLY_QUICKSTART.md](LOCAL_ONLY_QUICKSTART.md) | 快速开始指南 | 所有人 |
| **[LOCAL_ONLY_CHECKLIST.md](LOCAL_ONLY_CHECKLIST.md)** | **📝 执行清单** - 7 阶段完整执行步骤 | **执行者** |
| `config/client_config.local.json` | 本地配置文件模板 | 所有人 |
| `create_local_only_branch.bat/sh` | 一键分支创建脚本 | 所有人 |

---

## 🎯 核心目标

### 改造前（混合模式）

```
IEA Client → TCP(9999) → IstinaPlatform Server
              ↓              ↓
         Fernet 加密    用户管理/认证
              ↓              ↓
         83 处依赖        VLM 推理/限流
```

### 改造后（纯本地）

```
IEA Local → HTTP(8080) → llama-server
              ↓              ↓
         JSON 直连      GGUF 模型推理
              ↓              ↓
         0 服务端依赖    完全本地运行
```

---

## 📊 依赖统计

根据完整代码扫描，共发现 **83 处** 服务端依赖：

| 类别 | 文件数 | 依赖数 | 改造优先级 |
|------|-------|--------|-----------|
| **核心模块** | 6 | 15 | P0 - 必须 |
| **主要功能** | 10 | 25 | P1 - 建议 |
| **辅助功能** | 8 | 18 | P2 - 可选 |
| **调试脚本** | 16+ | 25+ | P3 - 可删除 |

详见：[LOCAL_ONLY_DEPENDENCY_MAP.md](LOCAL_ONLY_DEPENDENCY_MAP.md)

---

## 🔧 改造策略

### 策略 A：完全移除（推荐用于独立分支）

```bash
# 删除服务端相关代码
rm src/core/communication/communicator.py
rm src/core/cloud/managers/auth_manager.py
rm src/gui/pyqt6/pages/auth_page.py

# 替换为本地实现
# ClientCommunicator → LocalVLMClient
# AuthManager → LocalAuthManager
```

**优点**：代码干净，无冗余  
**缺点**：无法快速切换回混合模式

### 策略 B：条件化保留（推荐用于主分支）

```python
# 在 communicator.py 中添加模式检测
class ClientCommunicator:
    def __init__(self, config):
        self.mode = config.get("mode", "local_only")
        if self.mode == "local_only":
            self._client = LocalVLMClient()  # 本地实现
        else:
            self._socket = socket.socket()   # 云端实现
```

**优点**：可灵活切换模式  
**缺点**：保留冗余代码

### 策略 C：Git 分支管理（最推荐）

```bash
# 创建独立分支
git checkout -b local-only

# 在分支上进行完全改造
# - 删除服务端代码
# - 添加本地实现

# 主分支保持不变
git checkout main
```

**优点**：干净分离，便于维护  
**缺点**：需要管理多个分支

---

## 📝 改造步骤（5 步完成）

### 步骤 1：创建本地组件（30 分钟）

```bash
# 创建本地 VLM 客户端
# 文件：src/core/communication/local_vlm_client.py
# 内容：见 LOCAL_ONLY_IMPLEMENTATION.md 第一部分

# 创建本地认证管理器
# 文件：src/core/cloud/managers/local_auth_manager.py
# 内容：见 LOCAL_ONLY_IMPLEMENTATION.md 第二部分
```

### 步骤 2：修改核心模块（1 小时）

```python
# 修改推理管理器
# 文件：src/core/local_inference/inference_manager.py
# - 移除 _process_image_cloud 方法
# - 添加 LocalVLMClient 支持

# 修改元素分析器
# 文件：src/core/element_analysis/element_analyzer.py
# - 替换 ClientCommunicator 为 LocalVLMClient
```

### 步骤 3：修改 GUI（1 小时）

```python
# 修改 GUI 入口
# 文件：src/gui/pyqt6/main.py
# - 替换导入：LocalVLMClient, LocalAuthManager
# - 移除认证逻辑

# 修改主窗口
# 文件：src/gui/pyqt6/main_window.py
# - 移除认证页面
# - 直接显示主界面
```

### 步骤 4：修改脚本（1 小时）

```bash
# 批量替换脚本中的依赖
# scripts/*.py
# - ClientCommunicator(...) → LocalVLMClient(config)
# - communicator.send_request(...) → llama_client.send_request(...)
```

### 步骤 5：测试验证（1 小时）

```bash
# 启动 llama-server
python scripts/tools/start_llama_server.py

# 启动 GUI
python src/gui/pyqt6/main.py

# 运行标准流
python scripts/standard_flow_engine.py --flow daily_quest --local-only
```

**总预计时间**：4-5 小时

---

## 📦 文件清单

### 新建文件（3 个）

| 文件 | 说明 | 行数 |
|------|------|------|
| `src/core/communication/local_vlm_client.py` | 本地 VLM 客户端 | ~200 |
| `src/core/cloud/managers/local_auth_manager.py` | 本地认证管理器 | ~100 |
| `scripts/tools/start_llama_server.py` | llama-server 启动脚本 | ~200 |

### 修改文件（20+ 个）

| 文件 | 修改内容 | 行数变化 |
|------|---------|---------|
| `src/core/local_inference/inference_manager.py` | 移除云端降级 | -50 |
| `src/core/element_analysis/element_analyzer.py` | 使用 LocalVLMClient | -20 |
| `src/gui/pyqt6/main.py` | 替换通信器和认证 | -30 |
| `src/gui/pyqt6/main_window.py` | 移除认证页面 | -100 |
| `scripts/istina.py` | 移除认证命令 | -50 |
| ... | ... | ... |

### 删除文件（5+ 个）

| 文件 | 说明 |
|------|------|
| `src/gui/pyqt6/pages/auth_page.py` | 认证页面 |
| `src/gui/pyqt6/pages/cloud_page.py` | 云端推理页面 |
| `scripts/debug_*.py` | 调试脚本 |
| `scripts/tools/check_models.py` | 模型检查脚本 |
| `._vlm_helper.py` | VLM 辅助脚本 |

---

## ✅ 验证清单

### 启动测试

- [ ] GUI 正常启动，无认证页面
- [ ] llama-server 检测正常（或提示未运行）
- [ ] 所有页面可正常访问

### 功能测试

- [ ] 元素分析功能正常
- [ ] 任务识别功能正常
- [ ] 标准流执行正常
- [ ] ADB 设备控制正常
- [ ] 截图功能正常

### 集成测试

- [ ] `standard_flow_engine.py --flow daily_quest` 正常
- [ ] `istina.py device status` 正常
- [ ] `istina.py analyze` 正常

---

## 🚀 快速开始

### 1. 启动 llama-server

```bash
python scripts/tools/start_llama_server.py --model qwen3.5-2b
```

### 2. 启动 GUI

```bash
# 使用本地配置
python src/gui/pyqt6/main.py --config config/client_config.local.json

# 或修改主配置后直接启动
python src/gui/pyqt6/main.py
```

### 3. 运行标准流

```bash
python scripts/standard_flow_engine.py --flow daily_quest --local-only
```

详见：[LOCAL_ONLY_QUICKSTART.md](LOCAL_ONLY_QUICKSTART.md)

---

## ⚠️ 注意事项

1. **llama-server 必须运行**：所有 VLM 功能依赖本地 llama-server (127.0.0.1:8080)
2. **模型文件**：确保 `models/qwen3.5-2b-Q8_0.gguf` 存在
3. **无认证**：本地模式无需登录，直接可用
4. **无多用户**：单用户模式，所有配置为全局
5. **无云端降级**：llama-server 不可用时 VLM 功能将失败

---

## 🔄 回退方案

### Git 分支管理

```bash
# 切换到主分支（混合模式）
git checkout main

# 切换回本地版本
git checkout local-only
```

### 配置文件切换

```bash
# 使用混合模式配置
cp config/client_config.hybrid.json config/client_config.json

# 使用本地模式配置
cp config/client_config.local.json config/client_config.json
```

---

## 📚 相关文档

- [LOCAL_ONLY_MIGRATION.md](LOCAL_ONLY_MIGRATION.md) - 架构设计和改造范围
- [LOCAL_ONLY_IMPLEMENTATION.md](LOCAL_ONLY_IMPLEMENTATION.md) - 详细代码实现
- [LOCAL_ONLY_DEPENDENCY_MAP.md](LOCAL_ONLY_DEPENDENCY_MAP.md) - 83 处依赖完整清单
- [LOCAL_ONLY_QUICKSTART.md](LOCAL_ONLY_QUICKSTART.md) - 快速开始指南

---

## 📊 改造工作量

| 阶段 | 预计时间 | 说明 |
|------|---------|------|
| **准备** | 30 分钟 | 阅读文档，准备环境 |
| **实施** | 4 小时 | 创建/修改文件 |
| **测试** | 1 小时 | 功能验证 |
| **总计** | 5-6 小时 | 含调试时间 |

---

## 🎉 总结

本方案提供了完整的 IEA 纯本地版本改造指南：

- **83 处依赖** 完整清单
- **3 种策略** 可选（完全移除/条件化/分支管理）
- **5 步流程** 快速实施
- **详细代码** 即拷即用

**推荐方案**：使用 Git 分支管理，在 `local-only` 分支上进行完全改造，主分支保持不变。

**优势**：
- ✅ 无需服务端，独立运行
- ✅ 配置简单，开箱即用
- ✅ 性能更好，无网络延迟
- ✅ 隐私更好，数据本地处理
