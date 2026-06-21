# IEA 纯本地版本实施指南

> 配合 `LOCAL_ONLY_MIGRATION.md` 使用  
> 提供详细的代码实现和修改步骤

---

## 一、创建本地 VLM 客户端

**文件**: `IstinaEndfieldAssistant/src/core/communication/local_vlm_client.py`

```python
"""
本地 VLM 客户端 - 替代服务端通信
直接调用本地 llama-server HTTP API

单用户模式，无需认证，无需 TCP 加密
"""
import requests
import json
from typing import Dict, Any, Optional


class LocalVLMClient:
    """本地 VLM 客户端 - 完全替代 ClientCommunicator"""
    
    def __init__(self, llama_url: str = "http://127.0.0.1:8080"):
        """
        初始化本地 VLM 客户端
        
        Args:
            llama_url: llama-server HTTP API 地址
        """
        self.llama_url = llama_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json"
        })
    
    def is_available(self) -> bool:
        """检查 llama-server 是否可用"""
        try:
            resp = self._session.get(
                f"{self.llama_url}/v1/models",
                timeout=2
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False
    
    def send_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送请求到本地 llama-server
        
        兼容原 ClientCommunicator API，统一路由到 llama-server
        
        Args:
            endpoint: 端点名称（如"agent_chat", "process_image"）
            data: 请求数据
            
        Returns:
            VLM 响应结果
        """
        # 路由到 llama-server 的端点
        if endpoint in ["agent_chat", "process_image", "element_analysis"]:
            return self._call_llama_server(data)
        elif endpoint == "get_available_models":
            return self.get_available_models()
        elif endpoint == "get_user_info":
            return self.get_user_info()
        else:
            return {
                "status": "error",
                "error": f"UnsupportedEndpoint",
                "message": f"不支持的端点：{endpoint}"
            }
    
    def _call_llama_server(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用本地 llama-server
        
        Args:
            data: 包含以下键的字典
                - image_base64 或 image: 图像数据
                - prompt 或 task_description: 提示词
                - temperature: 温度参数（默认 0.3）
                - max_tokens: 最大 token 数（默认 4096）
                - timeout: 超时时间（默认 120 秒）
        
        Returns:
            响应结果
        """
        prompt = data.get("prompt") or data.get("task_description", "")
        image_base64 = data.get("image") or data.get("image_base64")
        
        # 构建 Chat Completion 消息
        content = []
        
        # 添加文本提示
        if prompt:
            content.append({"type": "text", "text": prompt})
        
        # 添加图像
        if image_base64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
            })
        
        # 如果没有图像只有文本
        if not image_base64 and prompt:
            messages = [{"role": "user", "content": prompt}]
        else:
            messages = [{"role": "user", "content": content}]
        
        try:
            resp = self._session.post(
                f"{self.llama_url}/v1/chat/completions",
                json={
                    "model": "local",
                    "messages": messages,
                    "max_tokens": data.get("max_tokens", 4096),
                    "temperature": data.get("temperature", 0.3),
                    "stream": False
                },
                timeout=data.get("timeout", 120)
            )
            
            resp.raise_for_status()
            result = resp.json()
            
            # 解析响应
            choice = result["choices"][0]
            message = choice["message"]
            
            return {
                "status": "success",
                "result": message["content"],
                "usage": result.get("usage", {}),
                "finish_reason": choice.get("finish_reason")
            }
            
        except requests.Timeout:
            return {
                "status": "error",
                "error": "RequestTimeout",
                "message": f"llama-server 请求超时（{data.get('timeout', 120)}秒）"
            }
        except requests.ConnectionError:
            return {
                "status": "error",
                "error": "ConnectionError",
                "message": "无法连接到 llama-server，请检查服务是否运行"
            }
        except requests.RequestException as e:
            return {
                "status": "error",
                "error": "RequestError",
                "message": str(e)
            }
        except KeyError as e:
            return {
                "status": "error",
                "error": "ParseError",
                "message": f"解析响应失败：{str(e)}"
            }
    
    def get_available_models(self) -> Dict[str, Any]:
        """
        获取可用模型列表（兼容原 API）
        
        Returns:
            模型列表
        """
        return {
            "status": "success",
            "models": [
                {
                    "id": "qwen3.5-2b",
                    "name": "Qwen3.5-2B",
                    "provider": "local",
                    "enabled": True
                },
                {
                    "id": "qwen2.5-7b",
                    "name": "Qwen2.5-7B",
                    "provider": "local",
                    "enabled": True
                }
            ]
        }
    
    def get_user_info(self) -> Dict[str, Any]:
        """
        获取用户信息（兼容原 API）
        
        Returns:
            本地用户信息
        """
        return {
            "status": "success",
            "user_id": "local_user",
            "username": "local_user",
            "tier": "local",
            "quota_remaining": -1  # 无限
        }
    
    def close(self):
        """关闭会话"""
        self._session.close()
```

---

## 二、创建本地认证管理器

**文件**: `IstinaEndfieldAssistant/src/core/cloud/managers/local_auth_manager.py`

```python
"""
本地认证管理器 - 单用户免认证模式

替代云端 AuthManager，无需登录，直接使用
"""
from typing import Optional, Tuple


class LocalAuthManager:
    """本地认证管理器 - 无需登录，直接使用"""
    
    def __init__(self):
        """初始化 - 单用户模式，始终已认证"""
        self.user_id = "local_user"
        self.username = "local_user"
        self.is_authenticated = True
        self._session_id = "local_session"
    
    def login(self, username: str = None, password: str = None) -> Tuple[bool, str]:
        """
        无需登录，直接返回成功
        
        Returns:
            (True, "本地模式无需登录")
        """
        return True, "本地模式无需登录"
    
    def login_with_arkpass(self, file_path: str) -> Tuple[bool, str]:
        """
        无需 .arkpass 文件
        
        Returns:
            (True, "本地模式无需凭证文件")
        """
        return True, "本地模式无需凭证文件"
    
    def register_user(self, username: str, password: str) -> Tuple[bool, str]:
        """
        无需注册
        
        Returns:
            (True, "本地模式无需注册")
        """
        return True, "本地模式无需注册"
    
    def logout(self) -> None:
        """无需登出"""
        self.is_authenticated = True  # 始终已认证
    
    def is_logged_in(self) -> bool:
        """
        始终返回 True
        
        Returns:
            True
        """
        return True
    
    def is_session_valid(self) -> bool:
        """
        会话始终有效
        
        Returns:
            True
        """
        return True
    
    def ensure_valid_session(self) -> bool:
        """
        确保会话有效（始终有效）
        
        Returns:
            True
        """
        return True
    
    def get_user_info(self) -> dict:
        """
        获取本地用户信息
        
        Returns:
            用户信息字典
        """
        return {
            "user_id": self.user_id,
            "username": self.username,
            "tier": "local",
            "quota_remaining": -1
        }
    
    def get_session_id(self) -> str:
        """
        获取会话 ID（兼容原 API）
        
        Returns:
            固定的本地会话 ID
        """
        return self._session_id
```

---

## 三、修改推理管理器

**文件**: `IstinaEndfieldAssistant/src/core/local_inference/inference_manager.py`

### 修改内容

在文件开头添加导入：

```python
# 添加新导入
from ...communication.local_vlm_client import LocalVLMClient
```

修改 `InferenceManager` 类：

```python
class InferenceManager:
    """纯本地推理管理器 - 移除云端降级"""
    
    def __init__(self, config: dict, local_engine=None):
        """
        初始化
        
        Args:
            config: 配置字典
            local_engine: LocalInferenceEngine 实例（可选）
        """
        self.config = config
        self.local_engine = local_engine
        
        # 初始化本地 VLM 客户端
        llama_url = config.get("inference", {}).get("local", {}).get(
            "llama_server_url", "http://127.0.0.1:8080"
        )
        self.llama_client = LocalVLMClient(llama_url)
        
        # 移除 communicator 依赖
        # self.communicator = None
    
    def process_image(self, image_base64: str, prompt: str) -> dict:
        """
        处理图像 - 仅使用本地资源
        
        优先级：
        1. llama-server（性能更好）
        2. llama-cpp-python（降级）
        
        Args:
            image_base64: 图像数据
            prompt: 提示词
            
        Returns:
            推理结果
        """
        # 1. 优先使用 llama-server
        if self.llama_client and self.llama_client.is_available():
            result = self.llama_client.send_request("process_image", {
                "image_base64": image_base64,
                "prompt": prompt,
                "temperature": self.config.get("inference", {}).get("temperature", 0.3),
                "max_tokens": self.config.get("inference", {}).get("max_tokens", 4096)
            })
            
            if result.get("status") == "success":
                return result
        
        # 2. 降级到 llama-cpp-python
        if self.local_engine:
            try:
                result = self.local_engine.infer(image_base64, prompt)
                if result.get("status") == "success":
                    return result
            except Exception as e:
                return {
                    "status": "error",
                    "error": "LocalInferenceFailed",
                    "message": str(e)
                }
        
        # 3. 所有本地资源都失败
        return {
            "status": "error",
            "error": "NoLocalInferenceAvailable",
            "message": "所有本地推理资源不可用，请检查 llama-server 或本地模型配置"
        }
    
    def chat(self, messages: list, **kwargs) -> dict:
        """
        纯文本聊天（如果有需求）
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            响应结果
        """
        if self.llama_client and self.llama_client.is_available():
            return self.llama_client.send_request("agent_chat", {
                "prompt": messages[-1]["content"],
                "temperature": kwargs.get("temperature", 0.3)
            })
        
        return {
            "status": "error",
            "error": "NoLocalInferenceAvailable",
            "message": "本地推理不可用"
        }
    
    # 移除 _process_image_cloud 方法
    # 移除所有云端降级逻辑
```

---

## 四、修改元素分析器

**文件**: `IstinaEndfieldAssistant/src/core/element_analysis/element_analyzer.py`

### 修改内容

在文件开头添加导入：

```python
# 修改导入
# from ...communication.communicator import ClientCommunicator
from ...communication.local_vlm_client import LocalVLMClient
from typing import Optional
```

修改 `ElementAnalyzer` 类：

```python
class ElementAnalyzer:
    """本地元素分析器 - 直连 llama-server"""
    
    def __init__(self, config: dict, llama_client: LocalVLMClient = None):
        """
        初始化
        
        Args:
            config: 配置字典
            llama_client: LocalVLMClient 实例（可选，会自动创建）
        """
        self.config = config
        
        if llama_client is None:
            llama_url = config.get("inference", {}).get("local", {}).get(
                "llama_server_url", "http://127.0.0.1:8080"
            )
            self.llama_client = LocalVLMClient(llama_url)
        else:
            self.llama_client = llama_client
        
        # 移除 communicator 依赖
        # self.communicator = None
    
    def analyze_full_page(self, image_base64: str) -> dict:
        """
        分析完整页面
        
        Args:
            image_base64: 图像数据
            
        Returns:
            分析结果
        """
        prompt = self._build_element_analysis_prompt()
        
        result = self.llama_client.send_request("agent_chat", {
            "image_base64": image_base64,
            "prompt": prompt,
            "temperature": 0.1,
            "max_tokens": 4096,
            "timeout": 120
        })
        
        if result.get("status") != "success":
            return result
        
        # 解析 VLM 响应
        try:
            elements = self._parse_elements(result["result"])
            return {
                "status": "success",
                "elements": elements,
                "raw_response": result["result"],
                "usage": result.get("usage", {})
            }
        except Exception as e:
            return {
                "status": "error",
                "error": "ParseError",
                "message": f"解析元素失败：{str(e)}",
                "raw_response": result["result"]
            }
    
    def _build_element_analysis_prompt(self) -> str:
        """构建元素分析提示词"""
        return """你是一个《明日方舟：终末地》游戏助手。请分析这个游戏界面，返回 JSON 格式的分析结果：

{
  "page_type": "world/quest_panel/base/character/weapon/event/settings",
  "page_description": "页面描述",
  "elements": [
    {
      "name": "元素名称",
      "type": "button/icon/text/list/panel",
      "coordinates": {"x": 100, "y": 200},
      "size": {"width": 50, "height": 50},
      "description": "元素描述和功能",
      "actionable": true,
      "action_type": "tap/long_press/swipe"
    }
  ],
  "suggested_actions": [
    {
      "action": "动作描述",
      "target": "目标元素名称",
      "coordinates": {"x": 100, "y": 200}
    }
  ],
  "confidence": 0.95
}

请详细分析界面中的所有 UI 元素，包括按钮、图标、文本、列表等。
重点关注可交互元素的位置和功能。"""
    
    def _parse_elements(self, response_text: str) -> list:
        """
        解析 VLM 返回的元素列表
        
        Args:
            response_text: VLM 响应文本
            
        Returns:
            元素列表
        """
        try:
            # 尝试提取 JSON（VLM 可能返回带 Markdown 的响应）
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            
            if start >= 0 and end > start:
                json_str = response_text[start:end]
                data = json.loads(json_str)
                return data.get("elements", [])
        except json.JSONDecodeError as e:
            return [{"error": f"JSON 解析失败：{str(e)}"}]
        
        return []
    
    def analyze_task_list(self, image_base64: str) -> dict:
        """
        分析任务列表
        
        Args:
            image_base64: 图像数据
            
        Returns:
            任务列表
        """
        prompt = """分析这个任务列表界面，返回 JSON 格式：

{
  "tasks": [
    {
      "name": "任务名称",
      "description": "任务描述",
      "completed": false,
      "reward": "奖励描述",
      "coordinates": {"x": 100, "y": 200}
    }
  ],
  "total_count": 10,
  "completed_count": 3
}

请识别所有任务的状态和位置。"""
        
        result = self.llama_client.send_request("agent_chat", {
            "image_base64": image_base64,
            "prompt": prompt,
            "temperature": 0.1,
            "max_tokens": 4096
        })
        
        return result
```

---

## 五、修改 GUI 主窗口

**文件**: `IstinaEndfieldAssistant/src/gui/pyqt6/main_window.py`

### 修改内容

在文件开头添加导入：

```python
# 添加新导入
from ...core.communication.local_vlm_client import LocalVLMClient
from ...core.cloud.managers.local_auth_manager import LocalAuthManager
```

修改 `MainWindow` 类：

```python
class MainWindow(QMainWindow):
    def __init__(self, config: dict):
        """
        初始化主窗口
        
        Args:
            config: 配置字典
        """
        super().__init__()
        self.config = config
        
        # 初始化本地 VLM 客户端
        llama_url = config.get("inference", {}).get("local", {}).get(
            "llama_server_url", "http://127.0.0.1:8080"
        )
        self.llama_client = LocalVLMClient(llama_url)
        
        # 初始化本地认证管理器（免认证）
        self.auth_manager = LocalAuthManager()
        
        # 初始化推理管理器
        from ...core.local_inference.inference_manager import InferenceManager
        from ...core.local_inference.local_inference_engine import LocalInferenceEngine
        
        self.local_engine = LocalInferenceEngine(config)
        self.inference_manager = InferenceManager(config, self.local_engine)
        
        # 初始化元素分析器
        from ...core.element_analysis.element_analyzer import ElementAnalyzer
        self.element_analyzer = ElementAnalyzer(config, self.llama_client)
        
        # 直接初始化 UI，无需认证
        self._init_ui()
        
        # 检查 llama-server 状态
        self._check_llama_server_status()
    
    def _init_ui(self):
        """初始化 UI"""
        # 原有 UI 初始化逻辑...
        
        # 移除认证页面
        # self._auth_page = AuthPage(self)
        
        # 直接显示主页面
        self._show_main_page()
    
    def _check_llama_server_status(self):
        """检查 llama-server 状态"""
        if not self.llama_client.is_available():
            # 延迟显示提示，避免启动时阻塞
            QTimer.singleShot(2000, self._show_llama_server_warning)
    
    def _show_llama_server_warning(self):
        """显示 llama-server 未运行警告"""
        from PyQt6.QtWidgets import QMessageBox
        
        # 只在窗口激活时显示
        if self.isActiveWindow() or not self.isMinimized():
            QMessageBox.warning(
                self,
                "llama-server 未运行",
                "检测到 llama-server 未运行，VLM 功能将无法正常使用。\n\n"
                "请运行以下命令启动：\n"
                "python scripts/tools/start_llama_server.py\n\n"
                "或者检查配置中的 llama_server_url 设置。",
                QMessageBox.StandardButton.Ok
            )
    
    def _auto_login(self):
        """本地模式无需登录，直接初始化"""
        # 原有自动登录逻辑已移除
        # 直接显示主页面
        self._show_main_page()
    
    # 移除所有与云端认证相关的方法
    # - _on_login_success
    # - _on_login_failed
    # - _load_arkpass
    # - _save_arkpass
```

---

## 六、修改 GUI 入口

**文件**: `IstinaEndfieldAssistant/src/gui/pyqt6/main.py`

### 修改内容

```python
"""
IEA 纯本地版本入口

单用户模式，无需认证，直接启动
"""
import sys
import os
import json
from pathlib import Path

# 路径设置
project_root = Path(__file__).parent.parent.parent
src_dir = project_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from .main_window import MainWindow
from ...core.logger import init_logger, get_logger

logger = get_logger(__name__)


def load_config(config_path: str = None) -> dict:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径（可选）
        
    Returns:
        配置字典
    """
    if config_path is None:
        # 默认配置文件
        config_path = project_root / "config" / "client_config.json"
    else:
        config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在：{config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 检查模式
    mode = config.get("mode", "local_only")
    if mode == "local_only":
        print("[LocalMode] 纯本地模式启动")
    else:
        print(f"[Warning] 配置模式为 {mode}，但本地版本仅支持 local_only")
    
    return config


def main():
    """主入口函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="IEA 纯本地版本")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="配置文件路径"
    )
    args = parser.parse_args()
    
    # 初始化日志
    logging_config = project_root / "config" / "logging_config.json"
    init_logger(logging_config)
    
    # 加载配置
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(f"错误：{e}")
        sys.exit(1)
    
    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("IstinaEndfieldAssistant Local")
    app.setOrganizationName("IstinaAI")
    
    # 应用样式
    app.setStyle("Fusion")
    
    # 创建主窗口
    window = MainWindow(config)
    window.show()
    
    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

---

## 七、创建 llama-server 启动脚本

**文件**: `IstinaEndfieldAssistant/scripts/tools/start_llama_server.py`

```python
"""
llama-server 启动脚本

自动检测并启动本地 llama-server
"""
import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from typing import Optional

# 路径设置
project_root = Path(__file__).parent.parent.parent
config_dir = project_root / "config"


def load_config() -> dict:
    """加载配置文件"""
    config_path = config_dir / "client_config.json"
    
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在：{config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_model_file(model_name: str) -> Optional[Path]:
    """
    查找模型文件
    
    Args:
        model_name: 模型名称
        
    Returns:
        模型文件路径
    """
    models_dir = project_root / "models"
    
    # 查找匹配的 GGUF 文件
    for file in models_dir.glob("*.gguf"):
        if model_name.lower() in file.stem.lower():
            return file
    
    return None


def is_port_in_use(port: int) -> bool:
    """
    检查端口是否被占用
    
    Args:
        port: 端口号
        
    Returns:
        是否被占用
    """
    import socket
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def start_llama_server(
    model_path: Path,
    host: str = "127.0.0.1",
    port: int = 8080,
    gpu_layers: int = 40,
    threads: int = 8,
    context_size: int = 8192
):
    """
    启动 llama-server
    
    Args:
        model_path: 模型文件路径
        host: 监听地址
        port: 监听端口
        gpu_layers: GPU 层数
        threads: 线程数
        context_size: 上下文大小
    """
    # 查找 llama-server 可执行文件
    llama_server_exe = (
        project_root / "3rd-party" / "llama-server" / "llama-server.exe"
    )
    
    if not llama_server_exe.exists():
        print(f"错误：llama-server 可执行文件不存在：{llama_server_exe}")
        print("请将其下载到上述路径")
        return False
    
    # 构建命令
    cmd = [
        str(llama_server_exe),
        "--model", str(model_path),
        "--host", host,
        "--port", str(port),
        "--n-gpu-layers", str(gpu_layers),
        "--threads", str(threads),
        "--ctx-size", str(context_size),
        "--embedding",  # 启用嵌入支持
        "--verbose"     # 详细输出
    ]
    
    print(f"启动 llama-server...")
    print(f"命令：{' '.join(cmd)}")
    print(f"模型：{model_path}")
    print(f"地址：http://{host}:{port}")
    print("-" * 60)
    
    # 启动进程
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # 等待启动
    import time
    max_wait = 30  # 最多等待 30 秒
    
    for i in range(max_wait):
        if is_port_in_use(port):
            print(f"\nllama-server 已成功启动（{i+1}秒）")
            print(f"访问地址：http://{host}:{port}")
            
            # 持续输出日志
            try:
                for line in process.stdout:
                    print(line, end='')
            except KeyboardInterrupt:
                print("\n停止 llama-server...")
                process.terminate()
                process.wait()
            
            return True
    
    print(f"\n错误：llama-server 启动超时（等待{max_wait}秒）")
    process.terminate()
    process.wait()
    return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="启动 llama-server")
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="模型名称（如 qwen3.5-2b）"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="监听地址"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="监听端口"
    )
    args = parser.parse_args()
    
    # 加载配置
    try:
        config = load_config()
    except FileNotFoundError as e:
        print(f"错误：{e}")
        sys.exit(1)
    
    # 获取模型配置
    inference_config = config.get("inference", {}).get("local", {})
    model_name = args.model or inference_config.get("model_name", "qwen3.5-2b")
    
    # 查找模型文件
    model_path = find_model_file(model_name)
    
    if not model_path:
        print(f"错误：未找到模型文件：{model_name}")
        print(f"请在 {project_root / 'models'} 目录下放置 GGUF 模型文件")
        sys.exit(1)
    
    print(f"找到模型：{model_path}")
    
    # 检查端口
    port = args.port or inference_config.get("port", 8080)
    
    if is_port_in_use(port):
        print(f"警告：端口 {port} 已被占用")
        response = input("是否强制启动？(y/n): ")
        if response.lower() != 'y':
            sys.exit(0)
    
    # 启动 llama-server
    success = start_llama_server(
        model_path=model_path,
        host=args.host,
        port=port,
        gpu_layers=inference_config.get("gpu_layers", 40),
        threads=inference_config.get("threads", 8),
        context_size=inference_config.get("context_size", 8192)
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

---

## 八、测试清单

### 8.1 单元测试

```bash
# 测试本地 VLM 客户端
python -m pytest tests/unit/test_local_vlm_client.py -v

# 测试本地认证管理器
python -m pytest tests/unit/test_local_auth_manager.py -v
```

### 8.2 集成测试

```bash
# 启动 llama-server
python scripts/tools/start_llama_server.py

# 在另一个终端测试 GUI
python src/gui/pyqt6/main.py

# 测试标准流
python scripts/standard_flow_engine.py --flow daily_quest --local-only
```

### 8.3 手动测试

1. **启动测试**
   - [ ] GUI 正常启动，无认证页面
   - [ ] llama-server 检测正常
   - [ ] 所有页面可正常访问

2. **VLM 功能测试**
   - [ ] 元素分析正常
   - [ ] 任务识别正常
   - [ ] 决策建议正常

3. **标准流测试**
   - [ ] daily_quest 流程正常
   - [ ] 截图记录正常
   - [ ] 执行报告正常

---

## 九、故障排查

### 问题 1: llama-server 启动失败

**症状**: 启动脚本报错 "llama-server 可执行文件不存在"

**解决**:
```bash
# 下载 llama-server
# 参考：https://github.com/ggerganov/llama.cpp

# 放到指定路径
copy llama-server.exe 3rd-party/llama-server/
```

### 问题 2: VLM 请求超时

**症状**: "llama-server 请求超时"

**解决**:
1. 检查 llama-server 是否运行：`netstat -ano | findstr :8080`
2. 检查模型是否加载成功
3. 增加超时时间配置

### 问题 3: 元素分析失败

**症状**: "解析元素失败"

**解决**:
1. 检查 VLM 响应格式
2. 调整提示词
3. 查看原始响应调试

---

## 十、总结

本实施指南提供了详细的代码实现，配合 `LOCAL_ONLY_MIGRATION.md` 使用，可快速完成 IEA 纯本地版本改造。

**核心改动**:
1. 移除 TCP 通信，使用 HTTP 直连 llama-server
2. 移除认证系统，单用户免登录
3. 移除云端降级，纯本地推理
4. 简化 GUI，直接显示主界面

**优势**:
- 无需服务端，独立运行
- 配置简单，开箱即用
- 性能更好，无网络延迟
- 隐私更好，数据本地处理
