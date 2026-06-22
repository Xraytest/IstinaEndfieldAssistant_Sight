"""
推理管理器 - 统一管理本地和云端推理模式

提供统一的推理接口，自动处理模式切换和降级
支持同步和异步两种推理方式
"""
import os
import sys
import json
import time
import base64
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from core.foundation.utils.paths import ensure_src_path

# 添加项目根目录到路径
ensure_src_path(__file__)

try:
    from PyQt6.QtCore import QObject, pyqtSignal
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False
    # 创建模拟的QObject和pyqtSignal用于非PyQt环境
    class QObject:
        def __init__(self, parent=None):
            self._parent = parent
    
    def pyqtSignal(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from core.foundation.logger import get_logger, LogCategory
logger = get_logger()

from .gpu_checker import GPUChecker
from .model_manager import ModelManager, ModelInfo
from .local_inference_engine import LocalInferenceEngine, GenerationParams
from .prompt_cache import PromptCache, TaskChainCacheManager

# 导入异步推理管理器
try:
    from .async_inference_worker import AsyncInferenceManager, TaskPriority
    HAS_ASYNC_WORKER = True
except ImportError:
    HAS_ASYNC_WORKER = False
    # 定义TaskPriority用于非异步环境
    class TaskPriority(Enum):
        CRITICAL = 0
        HIGH = 1
        NORMAL = 2
        LOW = 3
        BACKGROUND = 4


class InferenceMode(Enum):
    """推理模式枚举（纯本地）"""
    LOCAL = "local"


@dataclass
class InferenceConfig:
    """推理配置数据类"""
    mode: str = "local"
    local_enabled: bool = False
    model_name: str = ""
    model_path: str = ""
    gpu_layers: int = -1
    use_cache: bool = True
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    max_tokens: int = 4096
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InferenceConfig":
        return cls(**data)


class InferenceManager(QObject):
    """
    推理管理器 - 统一管理本地和云端推理模式
    
    职责:
    1. 初始化时检测本地推理可用性
    2. 提供统一的推理接口（同步和异步）
    3. 管理推理模式切换
    4. 处理首次询问逻辑
    5. 自动降级机制
    6. 支持异步推理（通过AsyncInferenceWorker）
    
    信号:
    - inference_complete: 异步推理完成，返回(task_id, result)
    - inference_error: 异步推理出错，返回(task_id, error)
    - inference_progress: 异步推理进度更新，返回(task_id, progress)
    """
    
    # 信号定义
    inference_complete = pyqtSignal(str, dict)  # task_id, result
    inference_error = pyqtSignal(str, str)  # task_id, error
    inference_progress = pyqtSignal(str, int)  # task_id, progress
    
    MODE_LOCAL = InferenceMode.LOCAL.value
    
    def __init__(
        self,
        config: Dict[str, Any],
        models_dir: str = "models",
        parent: Optional[QObject] = None
    ):
        """
        初始化推理管理器（纯本地版）

        Args:
            config: 配置字典
            models_dir: 模型存储目录
            parent: 父QObject（用于PyQt信号机制）
        """
        super().__init__(parent)

        self._config = config

        # 初始化组件
        # [修复] 不在主线程创建 GPUChecker，避免 NVML 初始化导致栈损坏
        # GPUChecker 将在需要时由 LocalInferenceDialog 的 GPUCheckWorker 在工作线程中创建
        self._gpu_checker: Optional[GPUChecker] = None
        self._model_manager = ModelManager(models_dir=models_dir)
        self._local_engine: Optional[LocalInferenceEngine] = None
        self._prompt_cache = PromptCache(max_size=100)
        self._task_chain_cache = TaskChainCacheManager(max_size_per_chain=50)
        
        # 推理配置
        self._inference_config = self._load_inference_config()
        self._current_mode = self._inference_config.mode
        
        # GPU信息
        self._gpu_info: Optional[Dict[str, Any]] = None
        self._gpu_checked = False
        
        # 状态
        self._initialized = False
        self._local_available = False
        self._first_run = self._check_first_run()
        
        # 异步推理管理器
        self._async_manager: Optional[Any] = None
        self._async_tasks: Dict[str, Dict[str, Any]] = {}  # task_id -> task_info

        # Agent 执行器（由 create_agent_executor 创建）
        self._agent_executor: Optional[Any] = None
        
        logger.info(LogCategory.MAIN, "推理管理器初始化完成",
                   mode=self._current_mode)
    
    def _load_inference_config(self) -> InferenceConfig:
        """从配置加载推理设置"""
        inference_config = self._config.get("inference", {})
        local_config = inference_config.get("local", {})
        
        return InferenceConfig(
            mode=inference_config.get("mode", "local"),
            local_enabled=local_config.get("enabled", False),
            model_name=local_config.get("model_name", ""),
            model_path=local_config.get("model_path", ""),
            gpu_layers=local_config.get("gpu_layers", -1),
            use_cache=local_config.get("use_cache", True),
            temperature=local_config.get("temperature", 0.7),
            top_p=local_config.get("top_p", 0.9),
            top_k=local_config.get("top_k", 40),
            max_tokens=local_config.get("max_tokens", 4096),
        )
    
    def _check_first_run(self) -> bool:
        """检查是否是首次运行"""
        first_run_config = self._config.get("first_run", {})
        return not first_run_config.get("local_inference_prompt_shown", False)
    
    def initialize(self) -> bool:
        """
        初始化推理管理器
        
        Returns:
            是否初始化成功
        """
        try:
            logger.info(LogCategory.MAIN, "开始初始化推理管理器")
            logger.debug(LogCategory.MAIN, "初始化条件检查",
                        has_pyqt=HAS_PYQT,
                        has_async_worker=HAS_ASYNC_WORKER,
                        local_enabled=self._inference_config.local_enabled)
            
            # 检查GPU可用性
            self._check_gpu()
            
            # 根据配置初始化本地推理
            if self._inference_config.local_enabled:
                logger.info(LogCategory.MAIN, "配置启用了本地推理，开始初始化")
                self._initialize_local_engine()
            else:
                logger.info(LogCategory.MAIN, "本地推理未启用")
            
            # 初始化异步推理管理器（如果本地推理可用且支持PyQt）
            if self._local_available:
                logger.info(LogCategory.MAIN, "本地推理可用，检查异步管理器初始化条件",
                           has_pyqt=HAS_PYQT,
                           has_async_worker=HAS_ASYNC_WORKER)
                if HAS_PYQT and HAS_ASYNC_WORKER:
                    self._initialize_async_manager()
                else:
                    logger.warning(LogCategory.MAIN, "异步管理器初始化条件不满足",
                                 has_pyqt=HAS_PYQT,
                                 has_async_worker=HAS_ASYNC_WORKER)
            else:
                logger.info(LogCategory.MAIN, "本地推理不可用，跳过异步管理器初始化")
            
            self._initialized = True
            logger.info(LogCategory.MAIN, "推理管理器初始化完成",
                       mode=self._current_mode,
                       local_available=self._local_available,
                       async_available=self._async_manager is not None)
            
            return True
            
        except Exception as e:
            logger.exception(LogCategory.MAIN, "推理管理器初始化失败", error=str(e))
            return False
    
    def _initialize_async_manager(self) -> bool:
        """初始化异步推理管理器"""
        logger.info(LogCategory.MAIN, "开始初始化异步推理管理器")
        
        if not HAS_PYQT:
            logger.warning(LogCategory.MAIN, "PyQt不可用，跳过异步管理器初始化")
            return False
        
        if not HAS_ASYNC_WORKER:
            logger.warning(LogCategory.MAIN, "异步工作器模块不可用，跳过异步管理器初始化")
            return False
        
        if not self._local_engine:
            logger.warning(LogCategory.MAIN, "本地推理引擎未初始化，跳过异步管理器初始化")
            return False
        
        if not self._local_engine.is_available():
            logger.warning(LogCategory.MAIN, "本地推理引擎不可用，跳过异步管理器初始化")
            return False
        
        try:
            logger.info(LogCategory.MAIN, "创建异步推理管理器实例")
            self._async_manager = AsyncInferenceManager(
                local_engine=self._local_engine,
                parent=self
            )
            
            # 连接信号
            logger.debug(LogCategory.MAIN, "连接异步管理器信号")
            self._async_manager.result_ready.connect(self._on_async_result)
            self._async_manager.error_occurred.connect(self._on_async_error)
            self._async_manager.progress_updated.connect(self._on_async_progress)
            self._async_manager.task_started.connect(self._on_async_task_started)
            self._async_manager.task_cancelled.connect(self._on_async_task_cancelled)
            
            # 启动工作线程
            logger.debug(LogCategory.MAIN, "启动异步工作线程")
            self._async_manager.start()
            
            logger.info(LogCategory.MAIN, "异步推理管理器初始化成功")
            return True

        except Exception as e:
            logger.exception(LogCategory.MAIN, "异步推理管理器初始化失败", error=str(e))
            self._async_manager = None
            return False

    # ═══════════════════════════════════════════════════════
    # Agent 执行器管理
    # ═══════════════════════════════════════════════════════

    def create_agent_executor(
        self,
        screen_capture: Any,
        touch_executor: Any,
        config: Optional[Dict[str, Any]] = None,
        device_serial: str = "",
    ) -> Any:
        """
        创建 Agent 执行器

        AgentExecutor 通过 InferenceManager 进行推理，
        不再直接创建 GUIClient/VLMClient。

        Args:
            screen_capture: ScreenCapture 实例
            touch_executor: TouchManager 实例
            config: 配置字典
            device_serial: 设备序列号

        Returns:
            AgentExecutor 实例
        """
        # 延迟导入避免循环引用
        from core.service.cloud.agent_executor import AgentExecutor

        self._agent_executor = AgentExecutor(
            screen_capture=screen_capture,
            touch_executor=touch_executor,
            config=config,
            device_serial=device_serial,
            inference_manager=self,
        )

        logger.info(LogCategory.MAIN, "Agent 执行器已创建",
                   device_serial=device_serial or "(none)")

        return self._agent_executor

    def get_agent_executor(self) -> Optional[Any]:
        """获取已创建的 Agent 执行器"""
        return self._agent_executor

    def _on_async_result(self, task_id: str, result: Dict[str, Any]):
        """异步推理结果回调"""
        logger.info(LogCategory.INFERENCE, "异步推理完成", task_id=task_id)
        
        # 更新任务信息
        if task_id in self._async_tasks:
            self._async_tasks[task_id]["status"] = "completed"
            self._async_tasks[task_id]["result"] = result
            self._async_tasks[task_id]["completed_at"] = time.time()
        
        # 转发信号
        self.inference_complete.emit(task_id, result)
    
    def _on_async_error(self, task_id: str, error: str):
        """异步推理错误回调"""
        logger.error(LogCategory.INFERENCE, "异步推理出错", task_id=task_id, error=error)
        
        # 更新任务信息
        if task_id in self._async_tasks:
            self._async_tasks[task_id]["status"] = "error"
            self._async_tasks[task_id]["error"] = error
            self._async_tasks[task_id]["completed_at"] = time.time()
        
        # 转发信号
        self.inference_error.emit(task_id, error)
    
    def _on_async_progress(self, task_id: str, progress: int):
        """异步推理进度回调"""
        # 更新任务信息
        if task_id in self._async_tasks:
            self._async_tasks[task_id]["progress"] = progress
        
        # 转发信号
        self.inference_progress.emit(task_id, progress)
    
    def _on_async_task_started(self, task_id: str):
        """异步任务开始回调"""
        logger.info(LogCategory.INFERENCE, "异步任务开始", task_id=task_id)
        
        if task_id in self._async_tasks:
            self._async_tasks[task_id]["status"] = "running"
            self._async_tasks[task_id]["started_at"] = time.time()
    
    def _on_async_task_cancelled(self, task_id: str):
        """异步任务取消回调"""
        logger.info(LogCategory.INFERENCE, "异步任务取消", task_id=task_id)
        
        if task_id in self._async_tasks:
            self._async_tasks[task_id]["status"] = "cancelled"
            self._async_tasks[task_id]["completed_at"] = time.time()
    
    def _check_gpu(self) -> Dict[str, Any]:
        """检查GPU可用性
        
        [修复] 延迟创建 GPUChecker，避免主线程 NVML 初始化导致栈损坏。
        如果 GPUChecker 尚未创建，返回默认的 GPU 信息，不进行实际检测。
        实际的 GPU 检测应该通过 GPUCheckWorker 在工作线程中完成。
        """
        # 如果 GPUChecker 尚未创建，返回默认信息，不进行实际检测
        if self._gpu_checker is None:
            logger.warning(LogCategory.MAIN,
                          "GPUChecker 未初始化，返回默认 GPU 信息")
            self._gpu_info = {
                "available": False,
                "cuda_available": False,
                "gpu_count": 0,
                "gpus": [],
                "meets_requirements": False,
                "error": "GPUChecker 未初始化 - 请通过 GPUCheckWorker 进行检测"
            }
            self._gpu_checked = True
            return self._gpu_info
        
        # GPUChecker 已创建（通常由 GPUCheckWorker 在工作线程中创建）
        # 此时可以进行检测
        self._gpu_info = self._gpu_checker.check_gpu_availability()
        self._gpu_checked = True
        
        # 更新配置
        gpu_config = self._config.get("gpu", {})
        gpu_config.update({
            "checked": True,
            "cuda_available": self._gpu_info.get("cuda_available", False),
            "gpu_count": self._gpu_info.get("gpu_count", 0),
            "gpus": self._gpu_info.get("gpus", []),
            "meets_requirements": self._gpu_info.get("meets_requirements", False)
        })
        self._config["gpu"] = gpu_config
        
        logger.info(LogCategory.MAIN, "GPU检测完成",
                   available=self._gpu_info.get("available", False),
                   meets_requirements=self._gpu_info.get("meets_requirements", False))
        
        return self._gpu_info
    
    def _initialize_local_engine(self) -> bool:
        """初始化本地推理引擎"""
        if not self._gpu_info or not self._gpu_info.get("meets_requirements"):
            logger.warning(LogCategory.MAIN, "GPU不满足要求，跳过本地推理初始化")
            return False
        
        model_name = self._inference_config.model_name
        if not model_name:
            # 使用推荐模型
            model_name = self._gpu_info.get("recommended_model")
            if not model_name:
                logger.warning(LogCategory.MAIN, "无法确定推荐模型")
                return False
            self._inference_config.model_name = model_name
        
        # 检查模型是否已下载
        if not self._model_manager.is_model_downloaded(model_name):
            logger.warning(LogCategory.MAIN, "模型未下载", model_name=model_name)
            return False
        
        # 初始化本地引擎
        self._local_engine = LocalInferenceEngine(
            model_manager=self._model_manager,
            prompt_cache=self._prompt_cache
        )
        
        success = self._local_engine.initialize_with_model(
            model_name=model_name,
            gpu_layers=self._inference_config.gpu_layers
        )
        
        if success:
            self._local_available = True
            self._current_mode = self.MODE_LOCAL
            logger.info(LogCategory.MAIN, "本地推理引擎初始化成功",
                       model_name=model_name)
        else:
            logger.error(LogCategory.MAIN, "本地推理引擎初始化失败")
        
        return success
    
    def should_prompt_for_local_inference(self) -> bool:
        """是否应该显示首次询问对话框
        
        [修复] 不在此处进行 GPU 检查，避免主线程 NVML 初始化导致栈损坏。
        实际的 GPU 检查由 LocalInferenceDialog 的 GPUCheckWorker 在工作线程中完成。
        此方法仅返回是否是首次运行状态，让对话框显示后由工作线程检测 GPU。
        """
        # 仅返回首次运行状态，不在此处检查 GPU
        # GPU 检查将在 LocalInferenceDialog._start_gpu_check() 中通过 GPUCheckWorker 完成
        return self._first_run
    
    def process_image(
        self,
        image_data: Union[bytes, str],
        task_context: Dict[str, Any],
        use_cache: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        统一推理接口 - 处理图像（同步方式）
        
        Args:
            image_data: 图像数据（bytes或base64字符串）
            task_context: 任务上下文，包含task_id, prompt等
            use_cache: 是否使用缓存（默认使用配置）
            
        Returns:
            标准VLM响应格式
        """
        if not self._initialized:
            self.initialize()

        if use_cache is None:
            use_cache = self._inference_config.use_cache

        # 纯本地推理
        if self._local_available:
            try:
                result = self._process_image_local(image_data, task_context, use_cache)
                if result.get("status") == "success":
                    return result
                return result
            except Exception as e:
                logger.exception(LogCategory.MAIN, "本地推理异常", error=str(e))
                return {
                    "status": "error",
                    "error": f"本地推理失败: {str(e)}"
                }

        return {
            "status": "error",
            "error": "本地推理不可用"
        }
    
    def process_image_async(
        self,
        image_data: Union[bytes, str],
        task_context: Dict[str, Any],
        task_id: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout_seconds: float = 60.0,
        use_cache: Optional[bool] = None
    ) -> str:
        """
        异步处理图像
        
        使用AsyncInferenceWorker在后台线程中执行推理，
        通过信号通知推理结果。
        
        Args:
            image_data: 图像数据（bytes或base64字符串）
            task_context: 任务上下文，包含prompt等
            task_id: 任务ID（可选，自动生成）
            priority: 任务优先级
            timeout_seconds: 超时时间（秒）
            use_cache: 是否使用缓存
            
        Returns:
            task_id: 任务唯一标识，用于跟踪任务状态和接收结果
            
        Raises:
            RuntimeError: 异步推理管理器未初始化
        """
        if not self._initialized:
            logger.info(LogCategory.INFERENCE, "推理管理器未初始化，开始初始化")
            self.initialize()
        
        # 检查异步管理器是否可用
        if not self._async_manager:
            logger.info(LogCategory.INFERENCE, "异步管理器不可用，尝试初始化")
            # 尝试初始化
            if self._local_available and HAS_PYQT and HAS_ASYNC_WORKER:
                success = self._initialize_async_manager()
                logger.info(LogCategory.INFERENCE, "异步管理器初始化尝试结果", success=success)
            else:
                logger.warning(LogCategory.INFERENCE, "异步管理器初始化条件不满足",
                             local_available=self._local_available,
                             has_pyqt=HAS_PYQT,
                             has_async_worker=HAS_ASYNC_WORKER)
            
            if not self._async_manager:
                raise RuntimeError("异步推理管理器未初始化，本地推理可能不可用")
        
        # 生成任务ID
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        # 转换图像为base64
        if isinstance(image_data, bytes):
            image_base64 = base64.b64encode(image_data).decode('utf-8')
        else:
            image_base64 = image_data
        
        # 确定使用缓存
        if use_cache is None:
            use_cache = self._inference_config.use_cache
        
        # 准备任务上下文
        async_context = {
            "prompt": task_context.get("prompt", ""),
            "generation_params": {
                "temperature": task_context.get("temperature", self._inference_config.temperature),
                "top_p": task_context.get("top_p", self._inference_config.top_p),
                "top_k": task_context.get("top_k", self._inference_config.top_k),
                "max_tokens": task_context.get("max_tokens", self._inference_config.max_tokens)
            },
            "use_cache": use_cache,
            "original_context": task_context
        }
        
        # 记录任务信息
        # 确保priority是TaskPriority枚举类型
        if isinstance(priority, TaskPriority):
            priority_name = priority.name
        else:
            try:
                if isinstance(priority, str):
                    priority_name = TaskPriority[priority.upper()].name
                else:
                    priority_name = TaskPriority(priority).name
            except (KeyError, ValueError):
                priority_name = TaskPriority.NORMAL.name
        
        self._async_tasks[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "created_at": time.time(),
            "priority": priority_name,
            "progress": 0
        }
        
        # 添加任务到异步管理器
        success = self._async_manager.add_task(
            task_id=task_id,
            image_data=image_base64,
            task_context=async_context,
            priority=priority,
            timeout_seconds=timeout_seconds
        )
        
        if not success:
            del self._async_tasks[task_id]
            raise RuntimeError(f"添加异步任务失败: {task_id}")
        
        logger.info(LogCategory.INFERENCE, "异步推理任务已添加",
                   task_id=task_id,
                   priority=priority_name)
        
        return task_id
    
    def cancel_async_task(self, task_id: str) -> bool:
        """
        取消异步推理任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否取消成功
        """
        if not self._async_manager:
            logger.warning(LogCategory.INFERENCE, "异步管理器未初始化，无法取消任务")
            return False
        
        return self._async_manager.cancel_task(task_id)
    
    def get_async_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取异步任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态字典，任务不存在返回None
        """
        if task_id in self._async_tasks:
            return self._async_tasks[task_id].copy()
        
        if self._async_manager:
            return self._async_manager.get_task_status(task_id)
        
        return None
    
    def get_all_async_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有异步任务状态
        
        Returns:
            任务状态列表
        """
        if self._async_manager:
            return self._async_manager.get_all_tasks()
        
        return list(self._async_tasks.values())
    
    def is_async_available(self) -> bool:
        """异步推理是否可用"""
        return self._async_manager is not None and self._local_available
    
    def _get_effective_mode(self) -> str:
        """获取有效的推理模式（纯本地，始终返回 local）"""
        return self.MODE_LOCAL
    
    def _process_image_local(
        self,
        image_data: Union[bytes, str],
        task_context: Dict[str, Any],
        use_cache: bool
    ) -> Dict[str, Any]:
        """使用本地引擎处理图像"""
        # 转换图像为base64
        if isinstance(image_data, bytes):
            image_base64 = base64.b64encode(image_data).decode('utf-8')
        else:
            image_base64 = image_data
        
        # 获取prompt
        prompt = task_context.get("prompt", "")
        if not prompt:
            # 使用默认prompt
            prompt = "分析当前屏幕状态，决定下一步操作。"
        
        # 执行任务链缓存管理
        task_id = task_context.get("task_id", "default")
        cache = self._task_chain_cache.get_cache(task_id)
        
        # 处理图像
        result = self._local_engine.process_image(
            image_base64=image_base64,
            prompt=prompt,
            use_cache=use_cache
        )
        
        return result

    def switch_mode(self, mode: str) -> bool:
        """
        切换推理模式（纯本地，仅支持 local）

        Args:
            mode: 推理模式（仅 local）

        Returns:
            是否切换成功
        """
        if mode != self.MODE_LOCAL:
            logger.error(LogCategory.MAIN, "纯本地模式仅支持 local", mode=mode)
            return False

        if not self._local_available:
            if not self._initialize_local_engine():
                logger.error(LogCategory.MAIN, "本地推理不可用，无法切换")
                return False
            
            # 确保异步管理器已初始化
            if not self._async_manager and HAS_PYQT and HAS_ASYNC_WORKER:
                self._initialize_async_manager()
        
        self._current_mode = mode
        self._inference_config.mode = mode
        self._save_config()
        
        logger.info(LogCategory.MAIN, "推理模式已切换", mode=mode)
        return True
    
    def get_current_mode(self) -> str:
        """获取当前推理模式"""
        return self._get_effective_mode()
    
    def get_available_modes(self) -> List[str]:
        """获取可用推理模式列表（纯本地版仅支持 local）"""
        modes = [self.MODE_LOCAL]
        return modes
    
    def is_local_available(self) -> bool:
        """本地推理是否可用"""
        return self._local_available
    
    def get_gpu_info(self) -> Optional[Dict[str, Any]]:
        """获取GPU信息"""
        if not self._gpu_checked:
            self._check_gpu()
        return self._gpu_info
    
    def get_available_models(self) -> List[ModelInfo]:
        """获取可用模型列表"""
        return self._model_manager.get_all_models()
    
    def download_model(
        self,
        model_name: str,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> bool:
        """
        下载模型
        
        Args:
            model_name: 模型名称
            progress_callback: 进度回调
            
        Returns:
            是否下载成功
        """
        try:
            result = self._model_manager.download_model(model_name, progress_callback)
            return result is not None
        except Exception as e:
            logger.exception(LogCategory.MAIN, "模型下载失败", 
                           model_name=model_name, error=str(e))
            return False
    
    def clear_prompt_cache(self):
        """清除prompt缓存"""
        if self._local_engine:
            self._local_engine.clear_cache()
        self._prompt_cache.clear()
        logger.info(LogCategory.MAIN, "Prompt缓存已清除")
    
    def clear_task_chain_cache(self, task_id: str):
        """清除任务链缓存"""
        self._task_chain_cache.clear_chain_cache(task_id)
        logger.debug(LogCategory.MAIN, "任务链缓存已清除", task_id=task_id)
    
    def clear_completed_async_tasks(self) -> int:
        """
        清理已完成的异步任务
        
        Returns:
            清理的任务数量
        """
        if self._async_manager:
            return self._async_manager.clear_completed_tasks()
        
        # 手动清理
        to_remove = []
        for task_id, task in self._async_tasks.items():
            if task.get("status") in ["completed", "error", "cancelled"]:
                to_remove.append(task_id)
        
        for task_id in to_remove:
            del self._async_tasks[task_id]
        
        return len(to_remove)
    
    def shutdown(self):
        """
        关闭推理管理器，释放资源
        
        清理所有资源，包括：
        1. 停止异步推理管理器
        2. 清理本地推理引擎
        3. 清理缓存
        """
        logger.info(LogCategory.MAIN, "开始关闭推理管理器")

        # 清理 Agent 执行器
        if self._agent_executor:
            try:
                logger.info(LogCategory.MAIN, "清理 Agent 执行器")
                self._agent_executor = None
            except Exception as e:
                logger.exception(LogCategory.MAIN, "清理 Agent 执行器失败", error=str(e))

        # 停止异步管理器
        if self._async_manager:
            try:
                logger.info(LogCategory.MAIN, "停止异步推理管理器")
                self._async_manager.stop()
                self._async_manager = None
            except Exception as e:
                logger.exception(LogCategory.MAIN, "停止异步管理器失败", error=str(e))
        
        # 清理本地引擎
        if self._local_engine:
            try:
                logger.info(LogCategory.MAIN, "清理本地推理引擎")
                self._local_engine.unload_model()
                self._local_engine = None
            except Exception as e:
                logger.exception(LogCategory.MAIN, "清理本地引擎失败", error=str(e))
        
        # 清理缓存
        try:
            self._prompt_cache.clear()
            self._task_chain_cache.clear_all()
            logger.info(LogCategory.MAIN, "缓存已清理")
        except Exception as e:
            logger.exception(LogCategory.MAIN, "清理缓存失败", error=str(e))
        
        # 清理任务记录
        self._async_tasks.clear()
        
        self._initialized = False
        self._local_available = False
        
        logger.info(LogCategory.MAIN, "推理管理器已关闭")
    
    def _save_config(self):
        """保存配置到磁盘"""
        # 更新配置字典
        self._config["inference"] = {
            "mode": self._inference_config.mode,
            "local": {
                "enabled": self._inference_config.local_enabled,
                "model_name": self._inference_config.model_name,
                "model_path": self._inference_config.model_path,
                "gpu_layers": self._inference_config.gpu_layers,
                "use_cache": self._inference_config.use_cache,
                "temperature": self._inference_config.temperature,
                "top_p": self._inference_config.top_p,
                "top_k": self._inference_config.top_k,
                "max_tokens": self._inference_config.max_tokens,
                "auto_fallback": getattr(self._inference_config, 'auto_fallback', False)
            }
        }

        # 实际保存到文件的逻辑
        try:
            # 确定项目根目录
            current = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current)))
            config_path = os.path.join(project_root, "config", "client_config.json")

            # 读取现有配置
            existing = {}
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        existing = json.load(f)
                except Exception as e:
                    logger.warning(LogCategory.MAIN, "读取配置文件失败", error=str(e))
                    existing = {}

            # 合并更新后的 inference 配置
            def _merge(a, b):
                for k, v in (b or {}).items():
                    if isinstance(v, dict) and isinstance(a.get(k), dict):
                        _merge(a[k], v)
                    else:
                        a[k] = v

            _merge(existing, self._config)

            # 原子写入
            import tempfile
            fd, tmp_path = tempfile.mkstemp(prefix="client_config_", suffix=".tmp", dir=os.path.dirname(config_path))
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, config_path)
            logger.info(LogCategory.MAIN, "推理配置已保存", path=config_path)
        except Exception as e:
            logger.exception(LogCategory.MAIN, "保存推理配置失败", error=str(e))
    
    def mark_first_run_complete(self, user_choice: str):
        """
        标记首次运行完成
        
        Args:
            user_choice: 用户选择（local/cloud）
        """
        self._first_run = False
        
        # 更新配置
        first_run_config = self._config.get("first_run", {})
        first_run_config["local_inference_prompt_shown"] = True
        first_run_config["user_choice"] = user_choice
        self._config["first_run"] = first_run_config
        
        # 根据用户选择设置模式
        if user_choice == "local":
            self._inference_config.local_enabled = True
            self.switch_mode(self.MODE_LOCAL)
        else:
            self._inference_config.local_enabled = False
            # 纯本地版：local 不可用时保持 local 模式
            self.switch_mode(self.MODE_LOCAL)
        
        self._save_config()
        logger.info(LogCategory.MAIN, "首次运行配置已保存", choice=user_choice)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取推理管理器统计信息"""
        stats = {
            "mode": self._current_mode,
            "effective_mode": self._get_effective_mode(),
            "local_available": self._local_available,
            "async_available": self.is_async_available(),
            "initialized": self._initialized,
            "first_run": self._first_run,
            "gpu_info": self._gpu_info,
            "config": self._inference_config.to_dict(),
            "async_tasks_count": len(self._async_tasks)
        }
        
        if self._local_engine:
            stats["local_engine"] = self._local_engine.get_model_info()
            stats["cache"] = self._local_engine.get_cache_stats()
        
        if self._async_manager:
            stats["async_stats"] = self._async_manager.get_stats()
        
        return stats


# 便捷函数
def create_inference_manager(
    config: Dict[str, Any],
    parent: Optional[QObject] = None
) -> InferenceManager:
    """创建推理管理器（纯本地版）"""
    return InferenceManager(config, parent=parent)


