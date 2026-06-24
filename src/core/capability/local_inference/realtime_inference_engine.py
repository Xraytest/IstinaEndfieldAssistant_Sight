"""实时推理引擎 - 独立于标准推理的小尺寸VLM用于即时控制"""
import os
import sys
import time
import json
import base64
import hashlib
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from core.foundation.paths import ensure_src_path

ensure_src_path(__file__)

from core.foundation.logger import get_logger, LogCategory
logger = get_logger()


@dataclass
class RealtimeGenParams:
    temperature: float = 0.3
    top_p: float = 0.85
    top_k: int = 20
    max_tokens: int = 256
    stop: List[str] = None

    def __post_init__(self):
        if self.stop is None:
            self.stop = ["<|im_end|>", "<|endoftext|>"]


class TPSMonitor:
    """每秒令牌数监控器"""
    def __init__(self, warn_threshold: float = 60.0):
        self._warn_threshold = warn_threshold
        self._token_counts: List[float] = []
        self._timestamps: List[float] = []
        self._lock = threading.Lock()
        self._current_tps = 0.0

    def record_tokens(self, count: int):
        with self._lock:
            now = time.time()
            self._token_counts.append(count)
            self._timestamps.append(now)
            cutoff = now - 5.0
            while self._timestamps and self._timestamps[0] < cutoff:
                self._token_counts.pop(0)
                self._timestamps.pop(0)
            if len(self._timestamps) > 1:
                total_tokens = sum(self._token_counts)
                time_span = self._timestamps[-1] - self._timestamps[0]
                self._current_tps = total_tokens / time_span if time_span > 0 else 0.0
            else:
                self._current_tps = 0.0

    @property
    def tps(self) -> float:
        with self._lock:
            return self._current_tps

    def check_and_warn(self):
        tps = self.tps
        if 0 < tps < self._warn_threshold:
            logger.warning(LogCategory.INFERENCE,
                          f"实时推理TPS低于阈值: {tps:.1f} < {self._warn_threshold}")
        return tps


class RealtimeInferenceEngine:
    """独立于标准推理的小尺寸VLM引擎，专用于实时控制"""
    
    def __init__(self, models_dir: str = "models"):
        self._models_dir = Path(models_dir)
        self._models_dir.mkdir(parents=True, exist_ok=True)
        self._llm = None
        self._model_path: Optional[str] = None
        self._model_name: Optional[str] = None
        self._initialized = False
        self._gpu_layers = -1
        self._n_ctx = 2048
        self._params = RealtimeGenParams()
        self._tps_monitor = TPSMonitor(warn_threshold=60.0)

    def initialize(self, model_path: str, model_name: Optional[str] = None,
                   gpu_layers: int = -1, n_ctx: int = 2048) -> bool:
        try:
            from llama_cpp import Llama
            if not os.path.exists(model_path):
                logger.error(LogCategory.INFERENCE, "实时模型文件不存在", path=model_path)
                return False
            self._llm = Llama(
                model_path=model_path,
                n_gpu_layers=gpu_layers,
                n_ctx=n_ctx,
                verbose=False,
            )
            self._model_path = model_path
            self._model_name = model_name or os.path.basename(model_path)
            self._gpu_layers = gpu_layers
            self._n_ctx = n_ctx
            self._initialized = True
            logger.info(LogCategory.INFERENCE, "实时推理引擎初始化成功",
                       model_name=self._model_name)
            return True
        except ImportError:
            logger.error(LogCategory.INFERENCE, "llama-cpp-python未安装，实时推理不可用")
            return False
        except Exception as e:
            logger.exception(LogCategory.INFERENCE, "实时推理引擎初始化失败", error=str(e))
            return False

    def is_available(self) -> bool:
        return self._initialized and self._llm is not None

    def process(self, image_base64: str, prompt: str) -> Dict[str, Any]:
        """快速推理，用于实时控制场景，自动监控TPS"""
        if not self.is_available():
            return {"status": "error", "error": "实时推理引擎未初始化"}
        start = time.time()
        try:
            multimodal_prompt = f"<|im_start|>user\n<image>\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
            output = self._llm(
                multimodal_prompt,
                temperature=self._params.temperature,
                top_p=self._params.top_p,
                top_k=self._params.top_k,
                max_tokens=self._params.max_tokens,
                stop=self._params.stop
            )
            text = output["choices"][0]["text"]
            tokens = output.get("usage", {}).get("completion_tokens", 0)
            elapsed = (time.time() - start) * 1000
            self._tps_monitor.record_tokens(tokens)
            self._tps_monitor.check_and_warn()
            return {
                "status": "success",
                "text": text,
                "tokens": tokens,
                "elapsed_ms": elapsed,
                "tps": self._tps_monitor.tps
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @property
    def tps(self) -> float:
        return self._tps_monitor.tps

    def unload(self):
        if self._llm:
            del self._llm
            self._llm = None
            self._initialized = False

    def set_params(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self._params, k):
                setattr(self._params, k, v)