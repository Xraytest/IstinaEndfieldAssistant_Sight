# IEA 纯本地版本 - 快速开始

> 个人单用户版本，无需服务端，无需认证  
> 完整依赖清单见：[LOCAL_ONLY_DEPENDENCY_MAP.md](LOCAL_ONLY_DEPENDENCY_MAP.md)

## 一、改造完成清单

### 文档
- ✅ `LOCAL_ONLY_MIGRATION.md` - 改造方案总览
- ✅ `LOCAL_ONLY_IMPLEMENTATION.md` - 详细实施指南
- ✅ `LOCAL_ONLY_DEPENDENCY_MAP.md` - **83 处依赖完整清单**
- ✅ `client_config.local.json` - 本地配置文件模板

### 需创建的文件
- ⏳ `src/core/communication/local_vlm_client.py` - 本地 VLM 客户端
- ⏳ `src/core/cloud/managers/local_auth_manager.py` - 本地认证管理器
- ⏳ `scripts/tools/start_llama_server.py` - llama-server 启动脚本

### 需修改的文件
- ⏳ `src/core/local_inference/inference_manager.py` - 移除云端降级
- ⏳ `src/core/element_analysis/element_analyzer.py` - 使用 LocalVLMClient
- ⏳ `src/gui/pyqt6/main_window.py` - 移除认证页面
- ⏳ `src/gui/pyqt6/main.py` - 更新入口

---

## 二、快速实施（5 步完成）

### 步骤 1：创建本地 VLM 客户端

```bash
# 创建文件：src/core/communication/local_vlm_client.py
# 内容见 LOCAL_ONLY_IMPLEMENTATION.md 第一部分
```

### 步骤 2：创建本地认证管理器

```bash
# 创建文件：src/core/cloud/managers/local_auth_manager.py
# 内容见 LOCAL_ONLY_IMPLEMENTATION.md 第二部分
```

### 步骤 3：修改推理管理器

在 `src/core/local_inference/inference_manager.py` 中：

```python
# 添加导入
from ...communication.local_vlm_client import LocalVLMClient

# 修改 __init__
def __init__(self, config: dict, local_engine=None):
    self.llama_client = LocalVLMClient(
        config.get("inference", {}).get("local", {}).get(
            "llama_server_url", "http://127.0.0.1:8080"
        )
    )
    # 移除 self.communicator
```

### 步骤 4：修改元素分析器

在 `src/core/element_analysis/element_analyzer.py` 中：

```python
# 修改导入
from ...communication.local_vlm_client import LocalVLMClient

# 修改 __init__
def __init__(self, config: dict, llama_client: LocalVLMClient = None):
    self.llama_client = llama_client or LocalVLMClient(...)
    # 移除 self.communicator
```

### 步骤 5：修改 GUI

在 `src/gui/pyqt6/main_window.py` 中：

```python
# 添加导入
from ...core.communication.local_vlm_client import LocalVLMClient
from ...core.cloud.managers.local_auth_manager import LocalAuthManager

# 修改 __init__
def __init__(self, config: dict):
    self.llama_client = LocalVLMClient(...)
    self.auth_manager = LocalAuthManager()  # 免认证
    # 直接 _init_ui()，无需认证
```

---

## 三、启动使用

### 3.1 启动 llama-server

```bash
python scripts/tools/start_llama_server.py --model qwen3.5-2b
```

### 3.2 启动 GUI

```bash
# 使用本地配置
python src/gui/pyqt6/main.py --config config/client_config.local.json

# 或修改主配置为 local_only 模式后直接启动
python src/gui/pyqt6/main.py
```

### 3.3 运行标准流

```bash
python scripts/standard_flow_engine.py --flow daily_quest --local-only
```

---

## 四、验证清单

- [ ] llama-server 正常启动（http://127.0.0.1:8080）
- [ ] GUI 启动无认证页面
- [ ] 元素分析功能正常
- [ ] 标准流执行正常
- [ ] 截图记录正常

---

## 五、故障排查

### llama-server 未运行

**症状**: GUI 启动时弹出警告

**解决**:
```bash
python scripts/tools/start_llama_server.py
```

### 模型文件不存在

**症状**: "未找到模型文件"

**解决**:
```bash
# 下载 qwen3.5-2b-Q8_0.gguf 到 models/ 目录
# 参考：https://huggingface.co/Qwen
```

### 端口被占用

**症状**: "端口 8080 已被占用"

**解决**:
```bash
# 查找占用端口的进程
netstat -ano | findstr :8080

# 修改配置使用其他端口
# config/client_config.local.json: "llama_server_url": "http://127.0.0.1:8081"
```

---

## 六、回退到混合模式

如需切换回混合模式：

```bash
# 使用 Git 切换分支
git checkout main

# 或恢复原始文件
git checkout -- src/core/communication/communicator.py
git checkout -- src/core/cloud/managers/auth_manager.py
git checkout -- config/client_config.json
```

---

## 七、联系支持

如有问题，请查看：
- `LOCAL_ONLY_MIGRATION.md` - 完整方案
- `LOCAL_ONLY_IMPLEMENTATION.md` - 详细实施指南
