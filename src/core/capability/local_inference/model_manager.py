"""
模型管理器 - 管理本地模型文件的下载、加载和版本管理

支持从ModelScope下载GGUF格式模型
"""
import os
import sys
import json
import hashlib
import fnmatch
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field, asdict
from core.foundation.paths import ensure_src_path

# 添加项目根目录到路径
ensure_src_path(__file__)

from core.foundation.logger import get_logger, LogCategory
logger = get_logger()


@dataclass
class ModelInfo:
    """模型信息数据类"""
    name: str
    modelscope_id: str
    file_pattern: str
    size_gb: float
    description: str
    quantization: str
    parameters: str
    recommended_gpu_memory_gb: int
    local_path: Optional[str] = None
    is_downloaded: bool = False
    version: str = "latest"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class ModelManager:
    """
    模型管理器 - 管理本地模型文件
    
    职责:
    1. 从ModelScope下载模型
    2. 管理模型文件版本
    3. 验证模型完整性
    4. 提供模型元数据
    """
    
    # 模型注册表
    MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
        "qwen3.5-4b-ud-q4_k_xl": {
            "modelscope_id": "unsloth/Qwen3.5-4B-GGUF",
            "file_pattern": "*UD-Q4_K_XL*.gguf",
            "size_gb": 2.8,
            "description": "推荐模型，4B参数，Q4_K_XL量化，2.8GB，4GB显存可运行",
            "quantization": "Q4_K_XL",
            "parameters": "4B",
            "recommended_gpu_memory_gb": 4,
        },
        "qwen3.5-2b-qwen3.6-plus-distilled-f16": {
            "modelscope_id": "unsloth/Qwen3.5-2B-GGUF",
            "file_pattern": "*Q8_K_XL*.gguf",
            "size_gb": 2.8,
            "description": "Qwen3.5-2B高精度模型，Q8_K_XL量化，2.8GB",
            "quantization": "Q8_K_XL",
            "parameters": "2B",
            "recommended_gpu_memory_gb": 8,
        },
        "qwen3.5-9b-fp16": {
            "modelscope_id": "unsloth/Qwen3.5-9B-FP16-GGUF",
            "file_pattern": "*fp16*.gguf",
            "size_gb": 18.0,
            "description": "推荐模型，9B参数，FP16精度，16GB显存可运行",
            "quantization": "FP16",
            "parameters": "9B",
            "recommended_gpu_memory_gb": 16,
        },
        "qwen3.5-35b-a3b-fp16": {
            "modelscope_id": "unsloth/Qwen3.5-35B-A3B-FP16-GGUF",
            "file_pattern": "*fp16*.gguf",
            "size_gb": 70.0,
            "description": "高性能模型，35B参数，FP16精度，需要24GB+显存",
            "quantization": "FP16",
            "parameters": "35B",
            "recommended_gpu_memory_gb": 24,
        },
        "gemma4-2b-q8_0": {
            "modelscope_id": "unsloth/gemma-4-2b-it-GGUF",
            "file_pattern": "*Q8_0*.gguf",
            "size_gb": 2.5,
            "description": "轻量级备用实时控制模型，2B参数，Q8量化",
            "quantization": "Q8_0",
            "parameters": "2B",
            "recommended_gpu_memory_gb": 8,
        },
    }
    
    def __init__(self, models_dir: str = "models"):
        """
        初始化模型管理器
        
        Args:
            models_dir: 模型存储目录路径
        """
        self._models_dir = Path(models_dir)
        self._models_dir.mkdir(parents=True, exist_ok=True)
        
        # 模型元数据文件
        self._metadata_file = self._models_dir / "model_metadata.json"
        self._metadata = self._load_metadata()
        
        logger.info(LogCategory.MAIN, "模型管理器初始化完成", 
                   models_dir=str(self._models_dir))
    
    def _load_metadata(self) -> Dict[str, Any]:
        """加载模型元数据"""
        if self._metadata_file.exists():
            try:
                with open(self._metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(LogCategory.MAIN, "加载模型元数据失败", error=str(e))
        
        return {}
    
    def _save_metadata(self):
        """保存模型元数据"""
        try:
            with open(self._metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self._metadata, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(LogCategory.MAIN, "保存模型元数据失败", error=str(e))
    
    def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        """
        获取模型信息
        
        Args:
            model_name: 模型名称
            
        Returns:
            模型信息对象，如果不存在返回None
        """
        if model_name not in self.MODEL_REGISTRY:
            return None
        
        registry_info = self.MODEL_REGISTRY[model_name]
        local_path = self.get_model_path(model_name)
        
        return ModelInfo(
            name=model_name,
            modelscope_id=registry_info["modelscope_id"],
            file_pattern=registry_info["file_pattern"],
            size_gb=registry_info["size_gb"],
            description=registry_info["description"],
            quantization=registry_info["quantization"],
            parameters=registry_info["parameters"],
            recommended_gpu_memory_gb=registry_info["recommended_gpu_memory_gb"],
            local_path=str(local_path) if local_path else None,
            is_downloaded=self.is_model_downloaded(model_name),
            version=self._metadata.get(model_name, {}).get("version", "latest")
        )
    
    def get_all_models(self) -> List[ModelInfo]:
        """获取所有模型信息"""
        return [
            self.get_model_info(name) 
            for name in self.MODEL_REGISTRY.keys()
        ]
    
    def get_available_models(self) -> List[ModelInfo]:
        """获取已下载的可用模型列表"""
        return [
            model_info for model_info in self.get_all_models()
            if model_info and model_info.is_downloaded
        ]
    
    def get_model_path(self, model_name: str) -> Optional[Path]:
        """
        获取模型文件路径
        
        Args:
            model_name: 模型名称
            
        Returns:
            模型文件路径，如果不存在返回None
        """
        if model_name not in self.MODEL_REGISTRY:
            return None
        
        model_dir = self._models_dir / model_name
        if not model_dir.exists():
            return None
        
        # 查找匹配的.gguf文件
        file_pattern = self.MODEL_REGISTRY[model_name]["file_pattern"]
        
        for file_path in model_dir.iterdir():
            if file_path.is_file() and file_path.suffix == '.gguf':
                if fnmatch.fnmatch(file_path.name, file_pattern):
                    return file_path
        
        # 如果没有匹配到，返回第一个.gguf文件
        gguf_files = list(model_dir.glob("*.gguf"))
        if gguf_files:
            return gguf_files[0]
        
        return None
    
    def is_model_downloaded(self, model_name: str) -> bool:
        """检查模型是否已下载"""
        return self.get_model_path(model_name) is not None
    
    def download_model(
        self, 
        model_name: str,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Optional[str]:
        """
        下载指定模型
        
        Args:
            model_name: 模型名称
            progress_callback: 进度回调函数(percentage, message)
            
        Returns:
            下载的模型路径，失败返回None
        """
        if model_name not in self.MODEL_REGISTRY:
            logger.error(LogCategory.MAIN, "未知模型", model_name=model_name)
            raise ValueError(f"Unknown model: {model_name}")
        
        model_info = self.MODEL_REGISTRY[model_name]
        
        try:
            # 检查是否已下载
            if self.is_model_downloaded(model_name):
                logger.info(LogCategory.MAIN, "模型已存在，跳过下载", 
                           model_name=model_name)
                if progress_callback:
                    progress_callback(100, "模型已存在")
                return str(self.get_model_path(model_name))
            
            if progress_callback:
                progress_callback(0, "开始下载...")
            
            # 使用modelscope下载
            model_path = self._download_from_modelscope(
                model_name=model_name,
                modelscope_id=model_info["modelscope_id"],
                file_pattern=model_info["file_pattern"],
                progress_callback=progress_callback
            )
            
            if model_path:
                # 更新元数据
                self._metadata[model_name] = {
                    "version": "latest",
                    "download_time": self._get_timestamp(),
                    "modelscope_id": model_info["modelscope_id"]
                }
                self._save_metadata()
                
                logger.info(LogCategory.MAIN, "模型下载完成", 
                           model_name=model_name, path=model_path)
                return model_path
            
        except Exception as e:
            logger.exception(LogCategory.MAIN, "模型下载失败", 
                           model_name=model_name, error=str(e))
            if progress_callback:
                progress_callback(-1, f"下载失败: {str(e)}")
        
        return None
    
    def _download_from_modelscope(
        self,
        model_name: str,
        modelscope_id: str,
        file_pattern: str,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Optional[str]:
        """从ModelScope下载模型"""
        try:
            from modelscope import snapshot_download
            
            if progress_callback:
                progress_callback(10, "连接ModelScope...")
            
            # 创建模型目录
            model_dir = self._models_dir / model_name
            model_dir.mkdir(parents=True, exist_ok=True)
            
            if progress_callback:
                progress_callback(20, "开始下载...")
            
            # 下载模型
            downloaded_path = snapshot_download(
                modelscope_id,
                local_dir=str(model_dir),
                allow_file_pattern=file_pattern
            )
            
            if progress_callback:
                progress_callback(90, "验证模型...")
            
            # 验证下载
            model_path = self.get_model_path(model_name)
            if model_path and self.verify_model(str(model_path)):
                if progress_callback:
                    progress_callback(100, "下载完成")
                return str(model_path)
            else:
                logger.error(LogCategory.MAIN, "模型验证失败", 
                           model_name=model_name)
                return None
                
        except ImportError:
            logger.error(LogCategory.MAIN, "modelscope库未安装")
            if progress_callback:
                progress_callback(-1, "请先安装modelscope: pip install modelscope")
            raise ImportError("modelscope library is required for downloading models")
        
        except Exception as e:
            logger.exception(LogCategory.MAIN, "ModelScope下载失败", error=str(e))
            raise
    
    def verify_model(self, model_path: str) -> bool:
        """
        验证模型文件完整性
        
        Args:
            model_path: 模型文件路径
            
        Returns:
            是否验证通过
        """
        try:
            path = Path(model_path)
            
            # 检查文件是否存在
            if not path.exists():
                logger.warning(LogCategory.MAIN, "模型文件不存在", path=model_path)
                return False
            
            # 检查文件大小（至少1MB）
            file_size = path.stat().st_size
            if file_size < 1024 * 1024:  # 1MB
                logger.warning(LogCategory.MAIN, "模型文件过小", 
                             path=model_path, size_bytes=file_size)
                return False
            
            # 检查文件扩展名
            if path.suffix != '.gguf':
                logger.warning(LogCategory.MAIN, "模型文件格式不正确", 
                             path=model_path, suffix=path.suffix)
                return False
            
            logger.debug(LogCategory.MAIN, "模型验证通过", 
                        path=model_path, size_mb=round(file_size / (1024*1024), 2))
            return True
            
        except Exception as e:
            logger.exception(LogCategory.MAIN, "模型验证异常", 
                           path=model_path, error=str(e))
            return False
    
    def delete_model(self, model_name: str) -> bool:
        """
        删除模型
        
        Args:
            model_name: 模型名称
            
        Returns:
            是否删除成功
        """
        try:
            model_dir = self._models_dir / model_name
            
            if not model_dir.exists():
                logger.warning(LogCategory.MAIN, "模型目录不存在", 
                             model_name=model_name)
                return False
            
            # 删除目录
            import shutil
            shutil.rmtree(model_dir)
            
            # 更新元数据
            if model_name in self._metadata:
                del self._metadata[model_name]
                self._save_metadata()
            
            logger.info(LogCategory.MAIN, "模型已删除", model_name=model_name)
            return True
            
        except Exception as e:
            logger.exception(LogCategory.MAIN, "删除模型失败", 
                           model_name=model_name, error=str(e))
            return False
    
    def get_model_size(self, model_name: str) -> Optional[float]:
        """
        获取模型文件大小（GB）
        
        Args:
            model_name: 模型名称
            
        Returns:
            文件大小（GB），如果不存在返回None
        """
        model_path = self.get_model_path(model_name)
        if not model_path:
            return None
        
        try:
            size_bytes = model_path.stat().st_size
            return round(size_bytes / (1024**3), 2)
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"获取模型大小失败：{e}")
            return None
    
    def get_disk_usage(self) -> Dict[str, Any]:
        """获取模型磁盘使用情况"""
        total_size = 0
        model_sizes = {}
        
        for model_name in self.MODEL_REGISTRY.keys():
            size = self.get_model_size(model_name)
            if size:
                model_sizes[model_name] = size
                total_size += size
        
        return {
            "total_size_gb": round(total_size, 2),
            "model_count": len(model_sizes),
            "models": model_sizes
        }
    
    def recommend_model(self, gpu_memory_gb: int) -> Optional[str]:
        """
        根据GPU显存推荐模型
        
        Args:
            gpu_memory_gb: GPU显存大小（GB）
            
        Returns:
            推荐的模型名称
        """
        # 按推荐显存排序
        sorted_models = sorted(
            self.MODEL_REGISTRY.items(),
            key=lambda x: x[1]["recommended_gpu_memory_gb"],
            reverse=True
        )
        
        for model_name, info in sorted_models:
            if gpu_memory_gb >= info["recommended_gpu_memory_gb"]:
                return model_name
        
        # 如果都不满足，返回最小的模型
        return "qwen3.5-2b-qwen3.6-plus-distilled-f16"
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def get_models_dir(self) -> str:
        """获取模型目录路径"""
        return str(self._models_dir)


# 便捷函数
def get_default_manager() -> ModelManager:
    """获取默认模型管理器实例"""
    return ModelManager()


def download_model_with_progress(
    model_name: str,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> Optional[str]:
    """带进度回调的模型下载"""
    manager = ModelManager()
    return manager.download_model(model_name, progress_callback)


if __name__ == "__main__":
    # 测试模型管理器
    print("=" * 60)
    print("模型管理器测试")
    print("=" * 60)
    
    manager = ModelManager(models_dir="test_models")
    
    # 测试获取模型信息
    print("\n1. 获取所有模型信息:")
    for model_info in manager.get_all_models():
        print(f"  {model_info.name}:")
        print(f"    描述: {model_info.description}")
        print(f"    大小: {model_info.size_gb} GB")
        print(f"    推荐显存: {model_info.recommended_gpu_memory_gb} GB")
        print(f"    已下载: {model_info.is_downloaded}")
        print()
    
    # 测试模型推荐
    print("\n2. 模型推荐测试:")
    for memory in [8, 16, 24, 32]:
        recommended = manager.recommend_model(memory)
        print(f"  {memory}GB显存推荐: {recommended}")
    
    # 测试磁盘使用
    print("\n3. 磁盘使用情况:")
    usage = manager.get_disk_usage()
    print(f"  总大小: {usage['total_size_gb']} GB")
    print(f"  模型数量: {usage['model_count']}")
    
    print("\n" + "=" * 60)
