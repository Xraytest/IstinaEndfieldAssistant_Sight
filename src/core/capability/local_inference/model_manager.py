"""
模型管理器 - 管理本地模型文件的加载和版本管理

设计原则：
1. 基于文件系统自动发现模型（扫描 models 目录）
2. 每个模型目录包含一个 model_info.json 元数据文件
3. 不再依赖 mmproj 文件（ multimodal 支持已移除）
4. 不再支持动态下载，只使用已存在的本地模型
"""
import os
import sys
import json
import fnmatch
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from core.foundation.paths import ensure_src_path

# 添加项目根目录到路径
ensure_src_path(__file__)

from core.foundation.logger import get_logger, LogCategory
logger = get_logger()


@dataclass
class ModelInfo:
    """模型信息数据类"""
    name: str
    modelscope_id: str = ""
    file_pattern: str = "*.gguf"
    size_gb: float = 0.0
    description: str = ""
    quantization: str = ""
    parameters: str = ""
    recommended_gpu_memory_gb: int = 0
    local_path: Optional[str] = None
    is_downloaded: bool = False
    version: str = "latest"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelInfo':
        """从字典创建 ModelInfo"""
        # 提供默认值处理缺失字段
        defaults = {
            'modelscope_id': "",
            'file_pattern': "*.gguf",
            'size_gb': 0.0,
            'description': "",
            'quantization': "",
            'parameters': "",
            'recommended_gpu_memory_gb': 0,
            'local_path': None,
            'is_downloaded': False,
            'version': "latest"
        }
        merged = {**defaults, **data}
        return cls(**merged)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class ModelManager:
    """
    模型管理器 - 管理本地模型文件

    职责:
    1. 自动发现已下载模型（扫描文件系统）
    2. 验证模型完整性
    3. 提供模型元数据
    4. 不再使用预编码的 MODEL_REGISTRY
    5. 不再支持动态下载
    """

    def __init__(self, models_dir: str = "models"):
        """
        初始化模型管理器

        Args:
            models_dir: 模型存储目录路径
        """
        self._models_dir = Path(models_dir)
        self._models_dir.mkdir(parents=True, exist_ok=True)

        # 模型元数据文件（存储已注册模型的目录名和基本信息）
        self._metadata_file = self._models_dir / "model_metadata.json"
        self._metadata = self._load_metadata()

        # 缓存已发现的模型列表
        self._discovered_models: Dict[str, ModelInfo] = {}

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

    def discover_models(self) -> Dict[str, ModelInfo]:
        """
        扫描文件系统，发现所有已下载的模型

        扫描策略:
        1. 遍历 models 目录下的所有一级子目录
        2. 每个子目录中查找 .gguf 文件
        3. 如果存在 model_info.json，读取元数据；否则使用默认元数据
        4. 构建 ModelInfo 对象并缓存
        5. 额外注册硬编码的固定模型路径（如果存在）

        Returns:
            模型名称到 ModelInfo 的映射
        """
        discovered = {}

        if not self._models_dir.exists():
            logger.warning(LogCategory.MAIN, "模型目录不存在", dir=str(self._models_dir))
            return discovered

        # 扫描 models 目录下的所有一级子目录
        for model_dir in self._models_dir.iterdir():
            if not model_dir.is_dir():
                continue

            # 查找 .gguf 文件（排除 mmproj - 虽然不应该存在）
            gguf_files = [f for f in model_dir.glob("*.gguf") if 'mmproj' not in f.name.lower()]
            if not gguf_files:
                continue

            # 选择主模型文件（第一个非 mmproj 的 .gguf）
            model_file = gguf_files[0]
            model_name = model_dir.name

            # 读取模型元数据（如果存在）
            model_info_path = model_dir / "model_info.json"
            if model_info_path.exists():
                try:
                    with open(model_info_path, 'r', encoding='utf-8') as f:
                        info_data = json.load(f)
                        # 确保 name 字段与目录名一致
                        info_data['name'] = model_name
                        info_data['local_path'] = str(model_file)
                        info_data['is_downloaded'] = True
                        model_info = ModelInfo.from_dict(info_data)
                except Exception as e:
                    logger.warning(LogCategory.MAIN, "读取模型元数据失败",
                                 model_dir=str(model_dir), error=str(e))
                    # 使用默认元数据
                    model_info = self._create_default_model_info(model_name, model_file)
            else:
                # 没有元数据文件，使用默认信息
                model_info = self._create_default_model_info(model_name, model_file)

            discovered[model_name] = model_info

        # 注册硬编码的固定模型路径（如果存在且尚未被扫描到）
        fixed_model_name = "qwen3.5-4b-ud-q6_k_xl"
        fixed_model_path = Path(
            r"C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight"
            r"\models\unsloth\Qwen3_5-4B-GGUF\Qwen3.5-4B-UD-Q6_K_XL.gguf"
        )
        if fixed_model_path.exists() and fixed_model_name not in discovered:
            try:
                size_gb = fixed_model_path.stat().st_size / (1024 ** 3)
            except Exception:
                size_gb = 0.0

            discovered[fixed_model_name] = ModelInfo(
                name=fixed_model_name,
                modelscope_id="",
                file_pattern="*.gguf",
                size_gb=round(size_gb, 2),
                description="固定使用的模型（硬编码路径）",
                quantization="Q6_K_XL",
                parameters="4B",
                recommended_gpu_memory_gb=8,
                local_path=str(fixed_model_path),
                is_downloaded=True,
                version="latest"
            )
            logger.info(LogCategory.MAIN, "已注册固定模型",
                       model_name=fixed_model_name, path=str(fixed_model_path))

        self._discovered_models = discovered
        logger.debug(LogCategory.MAIN, "模型发现完成", count=len(discovered))
        return discovered

    def _create_default_model_info(self, model_name: str, model_file: Path) -> ModelInfo:
        """创建默认的 ModelInfo（基于目录名和文件大小）"""
        try:
            size_gb = model_file.stat().st_size / (1024 ** 3)
        except Exception:
            size_gb = 0.0

        return ModelInfo(
            name=model_name,
            modelscope_id="",  # 未知
            file_pattern="*.gguf",
            size_gb=round(size_gb, 2),
            description="自动发现的模型（无元数据）",
            quantization="unknown",
            parameters="unknown",
            recommended_gpu_memory_gb=0,
            local_path=str(model_file),
            is_downloaded=True,
            version="unknown"
        )

    def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        """
        获取模型信息

        Args:
            model_name: 模型名称

        Returns:
            模型信息对象，如果不存在返回None
        """
        # 如果尚未发现模型，先执行发现
        if not self._discovered_models:
            self.discover_models()

        return self._discovered_models.get(model_name)

    def get_all_models(self) -> List[ModelInfo]:
        """获取所有已发现模型的信息"""
        if not self._discovered_models:
            self.discover_models()
        return list(self._discovered_models.values())

    def get_available_models(self) -> List[ModelInfo]:
        """获取已下载的可用模型列表（同 get_all_models）"""
        return self.get_all_models()

    def get_model_path(self, model_name: str) -> Optional[Path]:
        """
        获取模型文件路径

        Args:
            model_name: 模型名称

        Returns:
            模型文件路径，如果不存在返回None
        """
        model_info = self.get_model_info(model_name)
        if model_info and model_info.local_path:
            return Path(model_info.local_path)
        return None

    def is_model_downloaded(self, model_name: str) -> bool:
        """检查模型是否已下载"""
        return self.get_model_path(model_name) is not None

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

            # 更新元数据和缓存
            if model_name in self._metadata:
                del self._metadata[model_name]
                self._save_metadata()

            if model_name in self._discovered_models:
                del self._discovered_models[model_name]

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
            logger.debug(LogCategory.MAIN, "获取模型大小失败",
                        model_name=model_name, error=str(e))
            return None

    def get_disk_usage(self) -> Dict[str, Any]:
        """获取模型磁盘使用情况"""
        total_size = 0
        model_sizes = {}

        for model_info in self.get_all_models():
            if model_info.size_gb:
                model_sizes[model_info.name] = model_info.size_gb
                total_size += model_info.size_gb

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
            推荐的模型名称（基于已下载模型）
        """
        available_models = self.get_available_models()
        if not available_models:
            return None

        # 筛选出满足显存要求的模型
        suitable = [
            m for m in available_models
            if gpu_memory_gb >= m.recommended_gpu_memory_gb
        ]

        if suitable:
            # 返回满足条件中推荐显存最大的（性能最好的）
            suitable.sort(key=lambda m: m.recommended_gpu_memory_gb, reverse=True)
            return suitable[0].name

        # 如果没有满足的，返回已下载的最小模型（用户可能需要降低要求）
        available_models.sort(key=lambda m: m.recommended_gpu_memory_gb)
        return available_models[0].name if available_models else None

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


if __name__ == "__main__":
    # 测试模型管理器
    print("=" * 60)
    print("模型管理器测试（本地模型版本）")
    print("=" * 60)

    manager = ModelManager(models_dir="test_models")

    # 测试模型发现（扫描文件系统）
    print("\n1. 扫描已下载模型:")
    discovered = manager.discover_models()
    print(f"   发现 {len(discovered)} 个模型:")
    for name, info in discovered.items():
        print(f"     - {name}: {info.description} ({info.size_gb} GB)")

    # 测试获取所有模型
    print("\n2. 获取所有模型信息:")
    models = manager.get_all_models()
    for model in models:
        print(f"   {model.name}: {model.description}")

    # 测试磁盘使用
    print("\n3. 磁盘使用情况:")
    usage = manager.get_disk_usage()
    print(f"  总大小: {usage['total_size_gb']} GB")
    print(f"  模型数量: {usage['model_count']}")

    print("\n" + "=" * 60)
