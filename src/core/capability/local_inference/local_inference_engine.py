"""
本地推理引擎 - 封装llamacpp调用，实现VLM推理功能

支持Qwen3.5系列模型，使用llama-cpp-python库
"""
import os
import sys
import json
import base64
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field, asdict
from core.foundation.paths import ensure_src_path

# 添加项目根目录到路径
ensure_src_path(__file__)

from core.foundation.logger import get_logger, LogCategory
logger = get_logger()

from .prompt_cache import PromptCache
from .model_manager import ModelManager


@dataclass
class GenerationParams:
    """生成参数数据类"""
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    max_tokens: int = 4096
    stop: List[str] = field(default_factory=lambda: ["<|im_end|>", "<|endoftext|>"])
    repeat_penalty: float = 1.1
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class InferenceResult:
    """推理结果数据类"""
    status: str = "success"
    text: str = ""
    reasoning: str = ""
    touch_actions: List[Dict[str, Any]] = field(default_factory=list)
    task_completed: bool = False
    error: Optional[str] = None
    inference_time_ms: float = 0.0
    tokens_generated: int = 0
    cached: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def to_vlm_response(self) -> Dict[str, Any]:
        """转换为服务端VLM响应格式"""
        if self.status != "success":
            return {
                "status": "error",
                "error": self.error or "Unknown error",
                "result": None
            }
        
        return {
            "status": "success",
            "result": {
                "touch_actions": self.touch_actions,
                "task_completed": self.task_completed,
                "reasoning": self.reasoning,
                "text": self.text,
                "inference_time_ms": self.inference_time_ms,
                "tokens_generated": self.tokens_generated,
                "cached": self.cached
            }
        }


class LocalInferenceEngine:
    """
    本地推理引擎 - 封装llamacpp调用
    
    职责:
    1. 加载和管理GGUF模型
    2. 处理图像和prompt
    3. 管理prompt缓存
    4. 生成VLM响应
    """
    
    DEFAULT_GENERATION_PARAMS = GenerationParams()
    
    def __init__(
        self,
        model_manager: Optional[ModelManager] = None,
        prompt_cache: Optional[PromptCache] = None,
        generation_params: Optional[GenerationParams] = None
    ):
        """
        初始化本地推理引擎
        
        Args:
            model_manager: 模型管理器实例
            prompt_cache: Prompt缓存实例
            generation_params: 生成参数
        """
        self._model_manager = model_manager or ModelManager()
        self._prompt_cache = prompt_cache or PromptCache(max_size=100)
        self._generation_params = generation_params or self.DEFAULT_GENERATION_PARAMS
        
        self._llm = None
        self._model_path: Optional[str] = None
        self._model_name: Optional[str] = None
        self._initialized = False
        self._gpu_layers = -1  # -1表示全部使用GPU
        self._n_ctx = 8192  # 上下文长度
        
        logger.info(LogCategory.MAIN, "本地推理引擎初始化完成")
    
    def initialize(
        self,
        model_path: str,
        model_name: Optional[str] = None,
        gpu_layers: int = -1,
        n_ctx: int = 8192,
        verbose: bool = False
    ) -> bool:
        """
        初始化本地推理引擎
        
        Args:
            model_path: GGUF模型文件路径
            model_name: 模型名称
            gpu_layers: GPU层数，-1表示全部使用GPU
            n_ctx: 上下文长度
            verbose: 是否输出详细日志
            
        Returns:
            是否初始化成功
        """
        try:
            from llama_cpp import Llama
            
            logger.info(LogCategory.MAIN, "开始初始化本地推理引擎",
                       model_path=model_path, gpu_layers=gpu_layers)
            
            # 验证模型文件
            if not os.path.exists(model_path):
                logger.error(LogCategory.MAIN, "模型文件不存在", path=model_path)
                return False
            
            # 加载模型
            # 自动检测 clip 模型文件（mmproj-*.gguf）
            clip_path = self._find_clip_model(model_path)
            self._llm = Llama(
                model_path=model_path,
                n_gpu_layers=gpu_layers,
                n_ctx=n_ctx,
                verbose=verbose,
                clip_model_path=clip_path,
            )
            
            self._model_path = model_path
            self._model_name = model_name or os.path.basename(model_path)
            self._gpu_layers = gpu_layers
            self._n_ctx = n_ctx
            self._initialized = True
            
            logger.info(LogCategory.MAIN, "本地推理引擎初始化成功",
                       model_name=self._model_name,
                       gpu_layers=gpu_layers,
                       n_ctx=n_ctx)
            
            return True
            
        except ImportError:
            logger.error(LogCategory.MAIN, "llama-cpp-python未安装")
            return False
        except Exception as e:
            logger.exception(LogCategory.MAIN, "本地推理引擎初始化失败", error=str(e))
            return False
    
    def _find_clip_model(self, model_path: str) -> Optional[str]:
        """自动检测与主模型同目录的 clip 模型文件（mmproj-*.gguf）

        Args:
            model_path: 主模型文件路径

        Returns:
            clip 模型文件路径，未找到则返回 None
        """
        model_dir = os.path.dirname(model_path)
        if not os.path.isdir(model_dir):
            return None
        for fname in os.listdir(model_dir):
            if fname.startswith("mmproj-") and fname.endswith(".gguf"):
                clip_path = os.path.join(model_dir, fname)
                logger.info(LogCategory.MAIN, "检测到 clip 模型文件", path=clip_path)
                return clip_path
        logger.warning(LogCategory.MAIN, "未检测到 clip 模型文件（mmproj-*.gguf），多模态支持可能受限")
        return None

    def initialize_with_model(
        self,
        model_name: str,
        gpu_layers: int = -1,
        n_ctx: int = 8192,
        verbose: bool = False
    ) -> bool:
        """
        使用模型名称初始化
        
        Args:
            model_name: 模型名称（如"qwen3.5-9b-fp16"）
            gpu_layers: GPU层数
            n_ctx: 上下文长度
            verbose: 是否输出详细日志
            
        Returns:
            是否初始化成功
        """
        # 获取模型路径
        model_path = self._model_manager.get_model_path(model_name)
        
        if not model_path:
            logger.error(LogCategory.MAIN, "模型未下载", model_name=model_name)
            return False
        
        return self.initialize(
            model_path=str(model_path),
            model_name=model_name,
            gpu_layers=gpu_layers,
            n_ctx=n_ctx,
            verbose=verbose
        )
    
    def is_available(self) -> bool:
        """检查引擎是否可用"""
        return self._initialized and self._llm is not None
    
    def process_image(
        self,
        image_base64: str,
        prompt: str,
        use_cache: bool = True,
        generation_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理图像并返回推理结果
        
        Args:
            image_base64: Base64编码的图像数据
            prompt: 提示词
            use_cache: 是否使用缓存
            generation_params: 覆盖默认生成参数
            
        Returns:
            标准VLM响应格式
        """
        import time
        
        start_time = time.time()
        
        if not self.is_available():
            return InferenceResult(
                status="error",
                error="本地推理引擎未初始化"
            ).to_vlm_response()
        
        try:
            # 构建多模态prompt
            multimodal_prompt = self._build_multimodal_prompt(image_base64, prompt)
            
            # 生成缓存键
            cache_key = self._generate_cache_key(multimodal_prompt)
            
            # 检查缓存
            if use_cache:
                cached_result = self._prompt_cache.get(cache_key)
                if cached_result:
                    logger.debug(LogCategory.MAIN, "使用缓存的推理结果")
                    cached_result["result"]["cached"] = True
                    return cached_result
            
            # 执行推理
            params = generation_params or self._generation_params.to_dict()
            
            logger.debug(LogCategory.MAIN, "开始本地推理",
                        prompt_length=len(prompt))
            
            output = self._llm(
                multimodal_prompt,
                **params
            )
            
            # 解析响应
            generated_text = output["choices"][0]["text"]
            tokens_generated = output.get("usage", {}).get("completion_tokens", 0)
            
            # 解析VLM响应
            result = self._parse_vlm_response(generated_text)
            result.inference_time_ms = (time.time() - start_time) * 1000
            result.tokens_generated = tokens_generated
            
            # 缓存结果
            if use_cache:
                response_dict = result.to_vlm_response()
                self._prompt_cache.set(cache_key, response_dict)
            
            logger.debug(LogCategory.MAIN, "本地推理完成",
                        inference_time_ms=result.inference_time_ms,
                        tokens_generated=tokens_generated)
            
            return result.to_vlm_response()
            
        except Exception as e:
            logger.exception(LogCategory.MAIN, "本地推理失败", error=str(e))
            return InferenceResult(
                status="error",
                error=f"推理失败: {str(e)}"
            ).to_vlm_response()
    
    def _build_multimodal_prompt(self, image_base64: str, prompt: str) -> str:
        """
        构建多模态prompt（Qwen-VL格式）
        
        Args:
            image_base64: Base64编码的图像
            prompt: 文本提示
            
        Returns:
            格式化后的prompt
        """
        # Qwen-VL格式
        # <|im_start|>user
        # <image>
        # {prompt}<|im_end|>
        # <|im_start|>assistant
        
        return f"<|im_start|>user\n<image>\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
    
    def _generate_cache_key(self, prompt: str) -> str:
        """生成缓存键"""
        return hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:32]
    
    def _parse_vlm_response(self, text: str) -> InferenceResult:
        """
        解析VLM文本响应为结构化数据
        
        Args:
            text: VLM生成的文本
            
        Returns:
            解析后的推理结果
        """
        result = InferenceResult()
        result.text = text
        
        try:
            # 尝试解析JSON响应
            # 查找JSON块
            json_start = text.find('{')
            json_end = text.rfind('}')
            
            if json_start != -1 and json_end != -1:
                json_str = text[json_start:json_end + 1]
                parsed = json.loads(json_str)
                
                # 提取动作
                if "actions" in parsed:
                    result.touch_actions = parsed["actions"]
                elif "touch_actions" in parsed:
                    result.touch_actions = parsed["touch_actions"]
                
                # 提取完成状态
                if "completed" in parsed:
                    result.task_completed = parsed["completed"]
                elif "task_completed" in parsed:
                    result.task_completed = parsed["task_completed"]
                
                # 提取推理过程
                if "reasoning" in parsed:
                    result.reasoning = parsed["reasoning"]
                elif "thought" in parsed:
                    result.reasoning = parsed["thought"]
            else:
                # 非JSON响应，尝试从文本中提取信息
                result.reasoning = text
                
                # 简单的启发式解析
                if "click" in text.lower() or "点击" in text:
                    # 尝试提取坐标
                    import re
                    coords = re.findall(r'\((\d+),\s*(\d+)\)', text)
                    if coords:
                        for x, y in coords:
                            result.touch_actions.append({
                                "action": "click",
                                "x": int(x),
                                "y": int(y)
                            })
                
                if "complete" in text.lower() or "完成" in text:
                    result.task_completed = True
            
            result.status = "success"
            
        except json.JSONDecodeError as e:
            logger.warning(LogCategory.MAIN, "JSON解析失败", error=str(e))
            result.reasoning = text
            result.status = "success"  # 仍然返回成功，但可能没有结构化数据
        
        return result
    
    def clear_cache(self):
        """清除prompt缓存"""
        self._prompt_cache.clear()
        logger.info(LogCategory.MAIN, "Prompt缓存已清除")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return self._prompt_cache.get_cache_stats()
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取当前模型信息"""
        if not self.is_available():
            return {
                "initialized": False,
                "model_name": None,
                "model_path": None
            }
        
        return {
            "initialized": True,
            "model_name": self._model_name,
            "model_path": self._model_path,
            "gpu_layers": self._gpu_layers,
            "n_ctx": self._n_ctx
        }
    
    def unload_model(self):
        """卸载模型释放内存"""
        if self._llm:
            del self._llm
            self._llm = None
            self._initialized = False
            logger.info(LogCategory.MAIN, "模型已卸载")
    
    def reload_model(self) -> bool:
        """重新加载模型"""
        if self._model_path:
            return self.initialize(
                model_path=self._model_path,
                model_name=self._model_name,
                gpu_layers=self._gpu_layers,
                n_ctx=self._n_ctx
            )
        return False
    
    def update_generation_params(self, params: Dict[str, Any]):
        """更新生成参数"""
        for key, value in params.items():
            if hasattr(self._generation_params, key):
                setattr(self._generation_params, key, value)
        logger.info(LogCategory.MAIN, "生成参数已更新", params=params)


# 便捷函数
def create_engine(
    model_path: str,
    gpu_layers: int = -1,
    n_ctx: int = 8192
) -> Optional[LocalInferenceEngine]:
    """创建并初始化推理引擎"""
    engine = LocalInferenceEngine()
    if engine.initialize(model_path, gpu_layers=gpu_layers, n_ctx=n_ctx):
        return engine
    return None


if __name__ == "__main__":
    # 测试本地推理引擎
    print("=" * 60)
    print("本地推理引擎测试")
    print("=" * 60)
    
    engine = LocalInferenceEngine()
    
    # 测试未初始化状态
    print("\n1. 测试未初始化状态:")
    print(f"  可用: {engine.is_available()}")
    
    # 测试模型信息
    print("\n2. 模型信息:")
    info = engine.get_model_info()
    print(f"  初始化状态: {info['initialized']}")
    
    # 测试缓存统计
    print("\n3. 缓存统计:")
    stats = engine.get_cache_stats()
    print(f"  缓存大小: {stats['size']}")
    print(f"  最大缓存: {stats['max_size']}")
    
    print("\n" + "=" * 60)
