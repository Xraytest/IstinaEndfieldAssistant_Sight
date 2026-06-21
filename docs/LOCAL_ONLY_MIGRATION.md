# IEA 纯本地版本改造方案

> 版本：1.0  
> 日期：2026-06-14  
> 目标：创建完全脱离 IstinaPlatform 服务端的个人本地版本

---

## 一、核心设计原则

### 1.1 设计理念

- **单用户模式**：移除多用户管理，无需认证系统
- **配置驱动**：通过配置文件控制行为，无需大量代码修改
- **零依赖服务端**：完全移除 TCP 通信、Fernet 加密等服务器相关代码
- **保持逻辑**：不改变现有核心功能实现，仅移除服务端依赖

### 1.2 依赖统计

根据完整扫描，共发现 **83 处** 服务端依赖：

| 类别 | 文件数 | 说明 |
|------|-------|------|
| **核心模块** | 6 | GUI 入口、通信器、认证、推理管理 |
| **主要功能** | 10 | 元素分析、设备状态、Agent 执行 |
| **辅助功能** | 8 | CLI 工具、ADB 工具 |
| **调试脚本** | 16+ | debug_*.py, check_models.py 等 |

详见：[LOCAL_ONLY_DEPENDENCY_MAP.md](LOCAL_ONLY_DEPENDENCY_MAP.md)

### 1.2 架构对比

#### 当前架构（客户端 - 服务器）

```
IEA Client → TCP(9999) → IstinaPlatform Server
              ↓
         Fernet 加密
              ↓
    login/register/process_image
```

#### 改造后架构（纯本地）

```
IEA Local → 本地 llama-server(8080) → GGUF 模型
              ↓
         HTTP/JSON
              ↓
    直接调用/v1/chat/completions
```

---

## 二、改造范围

### 2.1 需移除的依赖

| 模块 | 当前实现 | 改造方式 |
|------|---------|---------|
| **认证系统** | AuthManager + 服务端登录 | 移除认证，直接运行 |
| **通信层** | ClientCommunicator + TCP/Fernet | 移除，替换为本地 HTTP 调用 |
| **云端推理** | 降级到服务端 process_image | 移除云端降级 |
| **用户管理** | 多用户/会话/权限 | 移除，单用户模式 |

### 2.2 保留的功能

| 模块 | 说明 |
|------|------|
| **本地推理** | LocalInferenceEngine (llama-cpp-python) |
| **llama-server** | 直连本地 HTTP 服务 (127.0.0.1:8080) |
| **标准流引擎** | JSON 配置驱动，已支持纯本地 |
| **设备控制** | ADB + TouchManager |
| **画面分析** | OpenCV + VLM (本地) |

---

## 三、详细改造方案

### 3.1 通信层移除

**文件**: `IstinaEndfieldAssistant/src/core/communication/communicator.py`

#### 当前实现（简化版）

```python
class ClientCommunicator:
    def __init__(self, server_host, server_port, password):
        self._socket = socket.socket(...)
        self._fernet = Fernet(...derive_key_from_password(password))
    
    def send_request(self, endpoint, data):
        # 构建二进制协议：ARKS + version + length + fernet.encrypt(json)
        # 发送 TCP 请求到服务端
        # 等待响应并解密
```

#### 改造方案

**方案 A：完全移除（推荐）**

```python
# 直接删除 communicator.py
# 所有使用 ClientCommunicator 的地方替换为 LocalVLMClient
```

**方案 B：保留空实现（便于切换）**

```python
"""
本地 VLM 客户端 - 替代服务端通信
直接调用本地 llama-server HTTP API
"""
import requests
from typing import Dict, Any

class LocalVLMClient:
    """本地 VLM 客户端 - 完全替代 ClientCommunicator"""
    
    def __init__(self, llama_url: str = "http://127.0.0.1:8080"):
        self.llama_url = llama_url
        self._session = requests.Session()
    
    def send_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送请求到本地 llama-server
        
        Args:
            endpoint: 端点名称（如"agent_chat", "process_image"）
            data: 请求数据，包含 image_base64, prompt 等
            
        Returns:
            VLM 响应结果
        """
        # 统一路由到 llama-server
        if endpoint in ["agent_chat", "process_image"]:
            return self._call_llama_server(data)
        else:
            return {
                "status": "error",
                "error": f"UnsupportedEndpoint: {endpoint}"
            }
    
    def _call_llama_server(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """调用本地 llama-server"""
        prompt = data.get("prompt", data.get("task_description", ""))
        image_base64 = data.get("image", data.get("image_base64"))
        
        # 构建 Chat Completion 请求
        messages = [{"role": "user", "content": []}]
        
        # 添加文本
        if prompt:
            messages[0]["content"].append({"type": "text", "text": prompt})
        
        # 添加图像
        if image_base64:
            messages[0]["content"].append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
            })
        
        try:
            resp = self._session.post(
                f"{self.llama_url}/v1/chat/completions",
                json={
                    "model": "local",
                    "messages": messages,
                    "max_tokens": data.get("max_tokens", 4096),
                    "temperature": data.get("temperature", 0.3)
                },
                timeout=data.get("timeout", 120)
            )
            
            resp.raise_for_status()
            result = resp.json()
            
            return {
                "status": "success",
                "result": result["choices"][0]["message"]["content"],
                "usage": result.get("usage", {})
            }
            
        except requests.RequestException as e:
            return {
                "status": "error",
                "error": f"LlamaServerUnavailable: {str(e)}",
                "message": "请确保 llama-server 正在运行"
            }
    
    # 兼容原有 API 的占位方法
    def get_available_models(self, session_id: str) -> Dict:
        """返回本地可用模型（兼容原 API）"""
        return {
            "status": "success",
            "models": ["qwen3.5-2b", "qwen2.5-7b"]  # 根据实际配置
        }
    
    def get_user_info(self, session_id: str) -> Dict:
        """返回本地用户信息（兼容原 API）"""
        return {
            "status": "success",
            "user_id": "local_user",
            "tier": "local"
        }
```

---

### 3.2 认证系统移除

**文件**: `IstinaEndfieldAssistant/src/core/cloud/managers/auth_manager.py`

#### 当前实现（简化版）

```python
class AuthManager:
    def __init__(self, communicator: ClientCommunicator):
        self.communicator = communicator
        self.session_id = None
    
    def login_with_arkpass(self, file_path):
        # 读取 .arkpass 文件
        # 调用 communicator.send_request("login", ...)
        # 保存 session_id
```

#### 改造方案

**方案：简化为单用户免认证**

```python
"""
本地认证管理器 - 单用户免认证模式
"""
from typing import Optional

class LocalAuthManager:
    """本地认证管理器 - 无需登录，直接使用"""
    
    def __init__(self):
        # 单用户模式，无需会话
        self.user_id = "local_user"
        self.is_authenticated = True  # 始终已认证
    
    def login(self, *args, **kwargs):
        """无需登录，直接返回成功"""
        return True, "本地模式无需登录"
    
    def logout(self):
        """无需登出"""
        pass
    
    def is_logged_in(self) -> bool:
        """始终返回 True"""
        return True
    
    def get_user_info(self) -> dict:
        """返回本地用户信息"""
        return {
            "user_id": self.user_id,
            "username": "local_user",
            "tier": "local"
        }
    
    def ensure_valid_session(self) -> bool:
        """始终有效"""
        return True
```

---

### 3.3 推理管理器改造

**文件**: `IstinaEndfieldAssistant/src/core/local_inference/inference_manager.py`

#### 当前实现（简化版）

```python
class InferenceManager:
    def process_image(self, image_base64, prompt):
        # 1. 尝试本地推理
        result = self._process_image_local(image_base64, prompt)
        if result.get("status") == "success":
            return result
        
        # 2. 降级到云端
        return self._process_image_cloud(image_base64, prompt)
    
    def _process_image_cloud(self, image_base64, prompt):
        # 调用 communicator.send_request("process_image", ...)
```

#### 改造方案

```python
class LocalInferenceManager:
    """纯本地推理管理器 - 移除云端降级"""
    
    def __init__(self, local_engine, llama_client):
        """
        Args:
            local_engine: LocalInferenceEngine (llama-cpp-python)
            llama_client: LocalVLMClient (llama-server HTTP)
        """
        self.local_engine = local_engine
        self.llama_client = llama_client
        # 移除 communicator 依赖
    
    def process_image(self, image_base64: str, prompt: str) -> dict:
        """处理图像 - 仅使用本地资源"""
        # 优先使用 llama-server（性能更好）
        if self.llama_client:
            result = self.llama_client.send_request("process_image", {
                "image_base64": image_base64,
                "prompt": prompt
            })
            if result.get("status") == "success":
                return result
        
        # 降级到 llama-cpp-python
        if self.local_engine:
            return self.local_engine.infer(image_base64, prompt)
        
        return {
            "status": "error",
            "error": "NoLocalInferenceAvailable",
            "message": "请启动 llama-server 或配置本地模型"
        }
    
    # 移除 _process_image_cloud 方法
```

---

### 3.4 元素分析器改造

**文件**: `IstinaEndfieldAssistant/src/core/element_analysis/element_analyzer.py`

#### 当前实现（简化版）

```python
class ElementAnalyzer:
    def __init__(self, communicator: ClientCommunicator):
        self.communicator = communicator
    
    def analyze_full_page(self, image_base64):
        # 调用 communicator.send_request("agent_chat", ...)
```

#### 改造方案

```python
class LocalElementAnalyzer:
    """本地元素分析器 - 直连 llama-server"""
    
    def __init__(self, llama_client: LocalVLMClient):
        """
        Args:
            llama_client: LocalVLMClient 实例
        """
        self.llama_client = llama_client
    
    def analyze_full_page(self, image_base64: str) -> dict:
        """分析完整页面"""
        prompt = self._build_element_analysis_prompt()
        
        result = self.llama_client.send_request("agent_chat", {
            "image_base64": image_base64,
            "prompt": prompt,
            "temperature": 0.1,
            "max_tokens": 4096
        })
        
        if result.get("status") != "success":
            return result
        
        # 解析 VLM 响应
        return {
            "status": "success",
            "elements": self._parse_elements(result["result"]),
            "raw_response": result["result"]
        }
    
    def _build_element_analysis_prompt(self) -> str:
        """构建元素分析提示词"""
        return """分析这个《明日方舟：终末地》游戏界面，返回 JSON 格式：
        {
          "page_type": "world/quest_panel/base/character/weapon/event",
          "elements": [
            {
              "name": "元素名称",
              "type": "button/icon/text/list",
              "coordinates": {"x": 100, "y": 200},
              "description": "元素描述",
              "actionable": true/false
            }
          ],
          "suggested_actions": ["可执行的动作列表"]
        }
        
        请详细分析界面中的所有 UI 元素。"""
    
    def _parse_elements(self, response_text: str) -> list:
        """解析 VLM 返回的元素列表"""
        import json
        try:
            # 尝试提取 JSON（VLM 可能返回带 Markdown 的响应）
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = response_text[start:end]
                return json.loads(json_str)
        except:
            pass
        return []
```

---

### 3.5 GUI 主窗口改造

**文件**: `IstinaEndfieldAssistant/src/gui/pyqt6/main_window.py`

#### 当前实现（简化版）

```python
class MainWindow(QMainWindow):
    def __init__(self):
        # 初始化通信器
        self.communicator = ClientCommunicator(...)
        
        # 初始化认证管理器
        self.auth_manager = AuthManager(self.communicator)
        
        # 显示认证页面
        self._auth_page = AuthPage(self)
        self._show_auth_page()
    
    def _auto_login(self):
        # 检查 .arkpass 文件
        # 自动登录
```

#### 改造方案

```python
class MainWindow(QMainWindow):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        
        # 初始化本地 VLM 客户端
        llama_url = config.get("inference", {}).get("local", {}).get(
            "llama_server_url", "http://127.0.0.1:8080"
        )
        self.llama_client = LocalVLMClient(llama_url)
        
        # 初始化本地认证管理器（免认证）
        self.auth_manager = LocalAuthManager()
        
        # 初始化本地推理管理器
        self.inference_manager = LocalInferenceManager(
            local_engine=self._create_local_engine(),
            llama_client=self.llama_client
        )
        
        # 直接显示主界面，无需认证
        self._init_ui()
        self._show_main_page()
    
    def _init_ui(self):
        """初始化 UI"""
        # 原有逻辑...
        
        # 移除认证页面导航
        # 保留：设备、任务、设置、IEA 等页面
    
    def _auto_login(self):
        """本地模式无需登录，直接初始化"""
        # 检查 llama-server 是否运行
        if not self._check_llama_server():
            self._show_llama_server_not_running()
        
        # 直接显示主页面
        self._show_main_page()
    
    def _check_llama_server(self) -> bool:
        """检查 llama-server 是否运行"""
        import requests
        try:
            resp = requests.get(
                f"{self.llama_client.llama_url}/v1/models",
                timeout=2
            )
            return resp.status_code == 200
        except:
            return False
    
    def _show_llama_server_not_running(self):
        """显示 llama-server 未运行提示"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(
            self,
            "llama-server 未运行",
            "检测到 llama-server 未运行，VLM 功能将无法使用。\n\n"
            "请运行：python scripts/tools/start_llama_server.py",
            QMessageBox.StandardButton.Ok
        )
```

---

### 3.6 配置文件改造

**新建文件**: `IstinaEndfieldAssistant/config/client_config.local.json`

```json
{
  "version": "1.0",
  "mode": "local_only",
  
  "inference": {
    "mode": "local_only",
    "local": {
      "enabled": true,
      "model_name": "qwen3.5-2b",
      "model_path": "../../models/qwen3.5-2b-Q8_0.gguf",
      "llama_server_url": "http://127.0.0.1:8080",
      "llama_server_exe": "../../3rd-party/llama-server/llama-server.exe",
      "gpu_layers": 40,
      "context_size": 8192,
      "threads": 8
    }
  },
  
  "device": {
    "adb_path": "../../3rd-party/adb/adb.exe",
    "default_host": "localhost:16512",
    "screenshot_method": "maa"
  },
  
  "logging": {
    "level": "INFO",
    "file": "logs/iea_local.log"
  }
}
```

**修改文件**: `IstinaEndfieldAssistant/config/client_config.json`

```json
{
  "version": "1.0",
  "mode": "local_only",  // 改为 local_only
  
  "inference": {
    "mode": "local_only",  // 改为 local_only
    "local": {
      "enabled": true,
      "model_name": "qwen3.5-2b",
      "model_path": "../../models/qwen3.5-2b-Q8_0.gguf",
      "llama_server_url": "http://127.0.0.1:8080",
      "llama_server_exe": "../../3rd-party/llama-server/llama-server.exe",
      "gpu_layers": 40,
      "context_size": 8192,
      "threads": 8
    }
  },
  
  "device": {
    "adb_path": "../../3rd-party/adb/adb.exe",
    "default_host": "localhost:16512",
    "screenshot_method": "maa"
  },
  
  "logging": {
    "level": "INFO",
    "file": "logs/iea_local.log"
  }
}
```

---

## 四、文件修改清单

### 4.1 新建文件

| 文件路径 | 说明 |
|---------|------|
| `src/core/communication/local_vlm_client.py` | 本地 VLM 客户端（替代 ClientCommunicator） |
| `src/core/cloud/managers/local_auth_manager.py` | 本地认证管理器（免认证） |
| `config/client_config.local.json` | 纯本地配置文件 |
| `scripts/tools/start_llama_server.py` | llama-server 启动脚本 |

### 4.2 修改文件

| 文件路径 | 修改内容 |
|---------|---------|
| `src/core/local_inference/inference_manager.py` | 移除云端降级，改为 `LocalInferenceManager` |
| `src/core/element_analysis/element_analyzer.py` | 使用 `LocalVLMClient` 替代 `ClientCommunicator` |
| `src/gui/pyqt6/main_window.py` | 移除认证页面，直接显示主界面 |
| `src/gui/pyqt6/main.py` | 更新初始化逻辑 |
| `scripts/istina.py` | 移除认证相关命令 |
| `config/client_config.json` | 更新为本地模式配置 |

### 4.3 删除文件

| 文件路径 | 说明 |
|---------|------|
| `src/core/communication/communicator.py` | TCP 通信器（可选，可保留为空实现） |
| `src/core/cloud/managers/auth_manager.py` | 云端认证管理器（或改为空实现） |

---

## 五、实施步骤

### 步骤 1：创建本地 VLM 客户端

```bash
# 创建文件：src/core/communication/local_vlm_client.py
# 实现 LocalVLMClient 类
```

### 步骤 2：创建本地认证管理器

```bash
# 创建文件：src/core/cloud/managers/local_auth_manager.py
# 实现 LocalAuthManager 类
```

### 步骤 3：修改推理管理器

```bash
# 修改：src/core/local_inference/inference_manager.py
# 移除云端降级逻辑
```

### 步骤 4：修改元素分析器

```bash
# 修改：src/core/element_analysis/element_analyzer.py
# 使用 LocalVLMClient
```

### 步骤 5：修改 GUI

```bash
# 修改：src/gui/pyqt6/main_window.py
# 移除认证页面，直接显示主界面
```

### 步骤 6：更新配置文件

```bash
# 修改：config/client_config.json
# 设置为 local_only 模式
```

### 步骤 7：测试

```bash
# 启动 llama-server
python scripts/tools/start_llama_server.py

# 启动 GUI
python src/gui/pyqt6/main.py

# 测试标准流
python scripts/standard_flow_engine.py --flow daily_quest --local-only
```

---

## 六、使用说明

### 6.1 启动 llama-server

```bash
# 方式一：自动启动（GUI 检测未运行时会提示）
python src/gui/pyqt6/main.py

# 方式二：手动启动
python scripts/tools/start_llama_server.py --model qwen3.5-2b
```

### 6.2 启动 GUI

```bash
# 直接运行，无需登录
python src/gui/pyqt6/main.py
```

### 6.3 运行标准流

```bash
# 执行每日任务
python scripts/standard_flow_engine.py --flow daily_quest --local-only

# 执行所有流程
python scripts/standard_flow_engine.py --flow all
```

---

## 七、注意事项

1. **llama-server 必须运行**：所有 VLM 功能依赖本地 llama-server (127.0.0.1:8080)
2. **模型文件**：确保 `models/qwen3.5-2b-Q8_0.gguf` 存在
3. **无认证**：本地模式无需登录，直接可用
4. **无多用户**：单用户模式，所有配置为全局
5. **无云端降级**：llama-server 不可用时 VLM 功能将失败

---

## 八、回退到混合模式

如需切换回混合模式（支持云端降级）：

1. 恢复 `config/client_config.json` 原始配置
2. 恢复 `communicator.py` 和 `auth_manager.py` 原始实现
3. 修改 `main_window.py` 重新启用认证页面

建议使用 Git 分支管理：
- `main`: 原始混合模式
- `local-only`: 纯本地版本

```bash
# 切换到纯本地版本
git checkout local-only

# 切换回混合模式
git checkout main
```
