# IEA 纯本地版本 - 执行清单

> 完整执行步骤，确保改造成功

---

## 阶段 0：准备工作（10 分钟）

### 0.1 阅读文档

- [ ] 阅读 `LOCAL_ONLY_README.md` - 了解整体方案
- [ ] 阅读 `LOCAL_ONLY_DEPENDENCY_MAP.md` - 了解 83 处依赖
- [ ] 阅读 `LOCAL_ONLY_IMPLEMENTATION.md` - 了解详细实现

### 0.2 环境准备

- [ ] 确保 Git 已安装
- [ ] 确保 Python 3.10+ 已安装
- [ ] 确保 llama-server 已下载（可选，后续可添加）
- [ ] 确保 GGUF 模型已下载（可选，后续可添加）

### 0.3 备份当前状态

```bash
# 确保在主分支
git checkout main

# 拉取最新代码
git pull

# 创建备份分支
git checkout -b backup-before-local-only
```

---

## 阶段 1：创建分支（5 分钟）

### 方式 A：使用脚本（推荐）

```bash
# Windows
cd IstinaEndfieldAssistant
create_local_only_branch.bat

# Linux/Mac
cd IstinaEndfieldAssistant
chmod +x create_local_only_branch.sh
./create_local_only_branch.sh
```

### 方式 B：手动创建

```bash
# 创建分支
git checkout -b local-only

# 手动创建基础文件（见 LOCAL_ONLY_IMPLEMENTATION.md）
# - src/core/communication/local_vlm_client.py
# - src/core/cloud/managers/local_auth_manager.py
```

### 验证

- [ ] 分支 `local-only` 已创建
- [ ] `local_vlm_client.py` 已创建
- [ ] `local_auth_manager.py` 已创建

---

## 阶段 2：核心模块改造（2 小时）

### 2.1 修改推理管理器

**文件**: `src/core/local_inference/inference_manager.py`

```python
# 1. 添加导入
from ...communication.local_vlm_client import LocalVLMClient

# 2. 修改 __init__
def __init__(self, config: dict, local_engine=None):
    self.llama_client = LocalVLMClient(
        config.get("inference", {}).get("local", {}).get(
            "llama_server_url", "http://127.0.0.1:8080"
        )
    )
    # 移除 self._communicator

# 3. 修改 process_image
def process_image(self, image_base64: str, prompt: str) -> dict:
    # 优先使用 llama-server
    if self.llama_client and self.llama_client.is_available():
        result = self.llama_client.send_request("process_image", {...})
        if result.get("status") == "success":
            return result
    
    # 降级到本地引擎
    if self.local_engine:
        return self.local_engine.infer(image_base64, prompt)
    
    return {"status": "error", "error": "NoLocalInferenceAvailable"}

# 4. 删除 _process_image_cloud 方法
```

- [ ] 添加 LocalVLMClient 导入
- [ ] 修改 __init__ 方法
- [ ] 修改 process_image 方法
- [ ] 删除 _process_image_cloud 方法

### 2.2 修改元素分析器

**文件**: `src/core/element_analysis/element_analyzer.py`

```python
# 1. 修改导入
from ...communication.local_vlm_client import LocalVLMClient

# 2. 修改 __init__
def __init__(self, config: dict, llama_client: LocalVLMClient = None):
    self.llama_client = llama_client or LocalVLMClient(...)
    # 移除 self.communicator

# 3. 修改 analyze_full_page
def analyze_full_page(self, image_base64: str) -> dict:
    result = self.llama_client.send_request("agent_chat", {...})
    # 解析结果
```

- [ ] 修改导入
- [ ] 修改 __init__ 方法
- [ ] 修改 analyze_full_page 方法

### 2.3 修改设备状态管理器

**文件**: `src/core/device_state_manager.py`

```python
# 类似修改，使用 LocalVLMClient 替代 ClientCommunicator
```

- [ ] 修改导入
- [ ] 替换所有 communicator.send_request 调用

---

## 阶段 3：GUI 改造（1 小时）

### 3.1 修改 GUI 入口

**文件**: `src/gui/pyqt6/main.py`

```python
# 1. 修改导入
from core.communication.local_vlm_client import LocalVLMClient
from core.cloud.managers.local_auth_manager import LocalAuthManager

# 2. 修改 main 函数
def main():
    config = load_config()
    
    # 创建本地组件
    llama_client = LocalVLMClient(config)
    auth_manager = LocalAuthManager()
    
    # 创建主窗口
    window = MainWindow(config, llama_client, auth_manager)
```

- [ ] 修改导入
- [ ] 修改 main 函数

### 3.2 修改主窗口

**文件**: `src/gui/pyqt6/main_window.py`

```python
# 1. 修改 __init__
def __init__(self, config: dict, llama_client=None, auth_manager=None):
    self.llama_client = llama_client
    self.auth_manager = auth_manager
    # 直接初始化 UI，无需认证
    self._init_ui()
    self._show_main_page()

# 2. 删除认证相关方法
# - _auto_login
# - _on_login_success
# - _on_login_failed
```

- [ ] 修改 __init__ 方法
- [ ] 删除认证相关方法
- [ ] 添加 llama-server 检测

### 3.3 禁用认证页面

**选项 A**: 删除文件
```bash
rm src/gui/pyqt6/pages/auth_page.py
rm src/gui/pyqt6/pages/cloud_page.py
```

**选项 B**: 重命名备份
```bash
mv src/gui/pyqt6/pages/auth_page.py src/gui/pyqt6/pages/auth_page.py.bak
mv src/gui/pyqt6/pages/cloud_page.py src/gui/pyqt6/pages/cloud_page.py.bak
```

- [ ] 删除或禁用认证页面
- [ ] 更新相关导入

---

## 阶段 4：CLI 和脚本改造（1 小时）

### 4.1 修改 CLI 入口

**文件**: `scripts/istina.py`

```python
# 1. 移除认证相关命令
# - auth login
# - auth register
# - auth status

# 2. 修改其他命令使用 LocalVLMClient
```

- [ ] 移除认证命令
- [ ] 修改其他命令

### 4.2 批量修改脚本

**文件列表**:
- `scripts/daily_pipeline.py`
- `scripts/explore_game.py`
- `scripts/explore_tasks.py`
- `scripts/analyze_tasks.py`
- ...

**替换模式**:
```python
# 原代码
from core.communication import ClientCommunicator
communicator = ClientCommunicator(...)
communicator.send_request("agent_chat", {...})

# 新代码
from core.communication.local_vlm_client import LocalVLMClient
llama_client = LocalVLMClient(config)
llama_client.send_request("agent_chat", {...})
```

- [ ] 修改 daily_pipeline.py
- [ ] 修改 explore_game.py
- [ ] 修改其他脚本

### 4.3 清理调试脚本

```bash
# 删除或移动
mv scripts/debug_vlm.py scripts/debug_archived/
mv scripts/debug_vlm2.py scripts/debug_archived/
mv scripts/debug_models.py scripts/debug_archived/
mv scripts/discover_models.py scripts/debug_archived/
```

- [ ] 清理调试脚本

---

## 阶段 5：配置和测试（1 小时）

### 5.1 更新配置文件

**文件**: `config/client_config.json`

```json
{
  "mode": "local_only",
  "inference": {
    "mode": "local_only",
    "local": {
      "llama_server_url": "http://127.0.0.1:8080",
      "model_name": "qwen3.5-2b"
    }
  }
}
```

- [ ] 更新 mode 为 local_only
- [ ] 更新 inference 配置

### 5.2 启动 llama-server

```bash
# 方式 1: 使用脚本
python scripts/tools/start_llama_server.py --model qwen3.5-2b

# 方式 2: 手动启动
./3rd-party/llama-server/llama-server.exe \
  --model ./models/qwen3.5-2b-Q8_0.gguf \
  --host 127.0.0.1 --port 8080 \
  --n-gpu-layers 40
```

- [ ] llama-server 成功启动
- [ ] 访问 http://127.0.0.1:8080/v1/models 返回 200

### 5.3 启动 GUI

```bash
python src/gui/pyqt6/main.py
```

**验证**:
- [ ] GUI 正常启动
- [ ] 无认证页面
- [ ] llama-server 检测通过
- [ ] 所有页面可访问

### 5.4 运行标准流

```bash
python scripts/standard_flow_engine.py --flow daily_quest --local-only
```

**验证**:
- [ ] 流程正常执行
- [ ] 截图正常记录
- [ ] VLM 分析正常

---

## 阶段 6：最终验证（30 分钟）

### 6.1 功能测试清单

- [ ] **设备连接**: `istina.py device status`
- [ ] **截图功能**: `istina.py device screenshot`
- [ ] **画面分析**: `istina.py analyze`
- [ ] **标准流**: `standard_flow_engine.py --flow daily_quest`
- [ ] **GPU 检测**: `istina.py gpu status`

### 6.2 集成测试

- [ ] 完整执行 daily_quest 流程
- [ ] 检查截图序列完整性
- [ ] 检查执行报告生成

### 6.3 性能测试

- [ ] VLM 响应时间 < 30 秒
- [ ] 画面分析时间 < 5 秒
- [ ] 无内存泄漏

---

## 阶段 7：文档和提交（15 分钟）

### 7.1 更新文档

- [ ] 更新 README.md 说明本地模式
- [ ] 记录任何特殊配置或注意事项

### 7.2 Git 提交

```bash
# 添加所有修改
git add .

# 提交
git commit -m "feat: 完成 IEA 纯本地版本改造

- 移除所有服务端依赖（83 处）
- 实现 LocalVLMClient 和 LocalAuthManager
- 修改 GUI 移除认证页面
- 更新所有脚本使用本地 VLM
- 添加完整测试和文档

详见 docs/LOCAL_ONLY_README.md"

# 推送分支
git push origin local-only
```

---

## 故障排查

### 问题 1: 导入错误

**症状**: `ModuleNotFoundError: No module named '...local_vlm_client'`

**解决**:
```python
# 检查导入路径
from core.communication.local_vlm_client import LocalVLMClient
```

### 问题 2: llama-server 连接失败

**症状**: `ConnectionError: 无法连接到 llama-server`

**解决**:
```bash
# 检查 llama-server 是否运行
netstat -ano | findstr :8080

# 检查配置中的 URL
# config/client_config.json: "llama_server_url": "http://127.0.0.1:8080"
```

### 问题 3: 认证页面仍然显示

**症状**: GUI 启动后仍然显示认证页面

**解决**:
```python
# 检查 main_window.py 的 __init__ 方法
# 确保调用了 _show_main_page() 而不是 _show_auth_page()
```

---

## 回退方案

### 如果遇到问题

```bash
# 切换回主分支
git checkout main

# 或切换到备份分支
git checkout backup-before-local-only
```

### 选择性回退

```bash
# 回退单个文件
git checkout main -- src/core/local_inference/inference_manager.py

# 回退所有修改
git reset --hard main
```

---

## 完成清单

- [x] 阶段 0: 准备工作
- [x] 阶段 1: 创建分支
- [x] 阶段 2: 核心模块改造
- [x] 阶段 3: GUI 改造
- [x] 阶段 4: CLI 和脚本改造
- [x] 阶段 5: 配置和测试
- [x] 阶段 6: 最终验证
- [x] 阶段 7: 文档和提交

**总预计时间**: 6-8 小时

---

## 下一步

改造完成后，你可以：

1. **日常使用**: 直接在 `local-only` 分支上开发和测试
2. **功能增强**: 添加更多本地功能
3. **性能优化**: 优化本地推理性能
4. **同步主分支**: 定期将主分支的改进合并到本地版本

```bash
# 同步主分支的改进
git checkout main
git pull
git checkout local-only
git merge main
```

---

**祝你改造顺利！** 🎉
