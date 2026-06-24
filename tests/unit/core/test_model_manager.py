"""Tests for core/local_inference/model_manager.py"""

import json
import tempfile
from pathlib import Path
from typing import Dict, Any

import pytest

from core.capability.local_inference.model_manager import (
    ModelManager,
    ModelInfo,
    get_default_manager,
    download_model_with_progress,
)


class TestModelDiscovery:
    """测试模型发现功能（基于文件系统扫描）"""

    def test_discover_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            discovered = manager.discover_models()
            assert discovered == {}

    def test_discover_single_model_with_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)

            # 创建模型目录和 .gguf 文件
            model_dir = Path(tmpdir) / "qwen3.5-4b"
            model_dir.mkdir()

            gguf_file = model_dir / "Qwen3.5-4B-Q8_0.gguf"
            gguf_file.write_text("dummy model content")

            # 创建 model_info.json
            model_info = {
                "name": "qwen3.5-4b",
                "modelscope_id": "unsloth/Qwen3.5-4B-GGUF",
                "file_pattern": "Qwen3\\.5-4B-.*\\.gguf",
                "size_gb": 2.8,
                "description": "4B 参数，Q8 量化",
                "quantization": "Q8_0",
                "parameters": "4B",
                "recommended_gpu_memory_gb": 5.5,
                "local_path": str(gguf_file),
                "is_downloaded": True,
                "version": "latest"
            }
            info_file = model_dir / "model_info.json"
            with open(info_file, 'w') as f:
                json.dump(model_info, f)

            discovered = manager.discover_models()
            assert "qwen3.5-4b" in discovered
            info = discovered["qwen3.5-4b"]
            assert info.name == "qwen3.5-4b"
            assert info.modelscope_id == "unsloth/Qwen3.5-4B-GGUF"
            assert info.size_gb == 2.8
            assert info.local_path == str(gguf_file)
            assert info.is_downloaded is True

    def test_discover_model_without_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)

            # 创建模型目录和 .gguf 文件（无 model_info.json）
            model_dir = Path(tmpdir) / "test-model"
            model_dir.mkdir()
            gguf_file = model_dir / "model.gguf"
            gguf_file.write_text("dummy content")

            discovered = manager.discover_models()
            assert "test-model" in discovered
            info = discovered["test-model"]
            assert info.name == "test-model"
            assert info.modelscope_id == ""  # 未知
            assert info.is_downloaded is True
            assert info.local_path == str(gguf_file)

    def test_discover_multiple_models(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)

            # 创建多个模型目录
            for model_name in ["model-a", "model-b", "model-c"]:
                model_dir = Path(tmpdir) / model_name
                model_dir.mkdir()
                gguf_file = model_dir / f"{model_name}.gguf"
                gguf_file.write_text("dummy")

            discovered = manager.discover_models()
            assert len(discovered) == 3
            assert set(discovered.keys()) == {"model-a", "model-b", "model-c"}

    def test_discover_skips_non_gguf_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)

            # 创建只有非 .gguf 文件的目录
            model_dir = Path(tmpdir) / "empty-model"
            model_dir.mkdir()
            (model_dir / "readme.txt").write_text("no gguf here")

            discovered = manager.discover_models()
            assert "empty-model" not in discovered


class TestGetModelInfo:
    def test_get_existing_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)

            # 创建带元数据的模型
            model_dir = Path(tmpdir) / "qwen3.5-9b"
            model_dir.mkdir()
            gguf_file = model_dir / "model.gguf"
            gguf_file.write_text("dummy")

            model_info = {
                "name": "qwen3.5-9b",
                "modelscope_id": "unsloth/Qwen3.5-9B-GGUF",
                "file_pattern": "*.gguf",
                "size_gb": 4.5,
                "description": "9B 参数",
                "quantization": "Q8_0",
                "parameters": "9B",
                "recommended_gpu_memory_gb": 11.5,
                "local_path": str(gguf_file),
                "is_downloaded": True,
                "version": "latest"
            }
            with open(model_dir / "model_info.json", 'w') as f:
                json.dump(model_info, f)

            info = manager.get_model_info("qwen3.5-9b")
            assert info is not None
            assert info.name == "qwen3.5-9b"
            assert info.description == "9B 参数"
            assert info.size_gb == 4.5

    def test_get_nonexistent_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            assert manager.get_model_info("nonexistent") is None

    def test_model_info_to_dict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)

            model_dir = Path(tmpdir) / "test"
            model_dir.mkdir()
            gguf_file = model_dir / "test.gguf"
            gguf_file.write_text("dummy")

            info = ModelInfo(
                name="test",
                modelscope_id="test/repo",
                file_pattern="*.gguf",
                size_gb=1.0,
                description="Test model",
                quantization="Q8_0",
                parameters="2B",
                recommended_gpu_memory_gb=4,
                local_path=str(gguf_file),
                is_downloaded=True,
                version="latest"
            )
            d = info.to_dict()
            assert d["name"] == "test"
            assert d["size_gb"] == 1.0


class TestGetAllModels:
    def test_returns_all_discovered_models(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)

            # 创建两个模型
            for name in ["model1", "model2"]:
                model_dir = Path(tmpdir) / name
                model_dir.mkdir()
                (model_dir / f"{name}.gguf").write_text("dummy")

            models = manager.get_all_models()
            assert len(models) == 2
            names = [m.name for m in models]
            assert set(names) == {"model1", "model2"}


class TestGetAvailableModels:
    def test_returns_discovered_models(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)

            model_dir = Path(tmpdir) / "available"
            model_dir.mkdir()
            (model_dir / "model.gguf").write_text("dummy")

            available = manager.get_available_models()
            assert len(available) == 1
            assert available[0].name == "available"


class TestGetModelPath:
    def test_nonexistent_model_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            assert manager.get_model_path("nonexistent") is None

    def test_undownloaded_model_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            # 没有创建实际模型文件
            assert manager.get_model_path("not_downloaded") is None

    def test_downloaded_model_returns_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)

            model_dir = Path(tmpdir) / "test-model"
            model_dir.mkdir()
            gguf_file = model_dir / "model.gguf"
            gguf_file.write_text("dummy")

            # 创建元数据
            with open(model_dir / "model_info.json", 'w') as f:
                json.dump({
                    "name": "test-model",
                    "local_path": str(gguf_file),
                    "is_downloaded": True
                }, f)

            path = manager.get_model_path("test-model")
            assert path is not None
            assert path == gguf_file


class TestIsModelDownloaded:
    def test_downloaded_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)

            model_dir = Path(tmpdir) / "downloaded"
            model_dir.mkdir()
            (model_dir / "model.gguf").write_text("dummy")

            assert manager.is_model_downloaded("downloaded") is True

    def test_nonexistent_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            assert manager.is_model_downloaded("nonexistent") is False


class TestRecommendModel:
    def test_recommend_from_available_models(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)

            # 创建多个带不同推荐显存的模型
            models = [
                ("small", 4),
                ("medium", 8),
                ("large", 16)
            ]
            for name, mem in models:
                model_dir = Path(tmpdir) / name
                model_dir.mkdir()
                (model_dir / "model.gguf").write_text("dummy")
                # 提供完整的 ModelInfo 必需字段
                with open(model_dir / "model_info.json", 'w') as f:
                    json.dump({
                        "name": name,
                        "modelscope_id": f"test/{name}",
                        "file_pattern": "*.gguf",
                        "size_gb": 1.0,
                        "description": f"Test model {name}",
                        "quantization": "Q8_0",
                        "parameters": "2B",
                        "recommended_gpu_memory_gb": mem,
                        "local_path": str(model_dir / "model.gguf"),
                        "is_downloaded": True,
                        "version": "latest"
                    }, f)

            # 刷新缓存
            manager.discover_models()

            # 测试推荐
            assert manager.recommend_model(3) == "small"
            # 6GB 不够 medium (8GB)，所以返回 small
            assert manager.recommend_model(6) == "small"
            # 12GB 满足 medium (8GB) 但不满足 large (16GB)，所以返回 medium
            assert manager.recommend_model(12) == "medium"

    def test_recommend_no_available_models(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            assert manager.recommend_model(8) is None

    def test_recommend_insufficient_memory_returns_smallest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)

            # 只创建大模型
            model_dir = Path(tmpdir) / "large"
            model_dir.mkdir()
            (model_dir / "model.gguf").write_text("dummy")
            with open(model_dir / "model_info.json", 'w') as f:
                json.dump({
                    "name": "large",
                    "modelscope_id": "test/large",
                    "file_pattern": "*.gguf",
                    "size_gb": 1.0,
                    "description": "Large model",
                    "quantization": "Q8_0",
                    "parameters": "2B",
                    "recommended_gpu_memory_gb": 16,
                    "local_path": str(model_dir / "model.gguf"),
                    "is_downloaded": True,
                    "version": "latest"
                }, f)

            manager.discover_models()
            # 1GB 显存不够，应该返回唯一的可用模型（就是最小的，因为只有一个）
            assert manager.recommend_model(1) == "large"


class TestVerifyModel:
    def test_nonexistent_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            assert manager.verify_model("C:\\nonexistent_file.gguf") is False

    def test_file_exists_but_small(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / "model.gguf"
            fpath.write_text("small")
            manager = ModelManager(models_dir=str(tmpdir))
            assert manager.verify_model(str(fpath)) is False

    def test_file_wrong_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / "model.bin"
            fpath.write_text("x" * (1024 * 1024 + 1))
            manager = ModelManager(models_dir=str(tmpdir))
            assert manager.verify_model(str(fpath)) is False

    def test_valid_model_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = Path(tmpdir) / "model.gguf"
            # 写入 10MB 内容
            fpath.write_bytes(b"x" * (10 * 1024 * 1024))
            manager = ModelManager(models_dir=str(tmpdir))
            assert manager.verify_model(str(fpath)) is True


class TestDiskUsage:
    def test_no_downloaded_models(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            usage = manager.get_disk_usage()
            assert usage["total_size_gb"] == 0.0
            assert usage["model_count"] == 0

    def test_multiple_models(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)

            # 创建两个模型，各 10MB
            for name in ["model1", "model2"]:
                model_dir = Path(tmpdir) / name
                model_dir.mkdir()
                gguf_file = model_dir / "model.gguf"
                gguf_file.write_bytes(b"x" * (10 * 1024 * 1024))
                with open(model_dir / "model_info.json", 'w') as f:
                    json.dump({
                        "name": name,
                        "size_gb": 0.01,
                        "local_path": str(gguf_file),
                        "is_downloaded": True
                    }, f)

            manager.discover_models()
            usage = manager.get_disk_usage()
            assert usage["model_count"] == 2
            # 两个 10MB 文件约 0.02 GB
            assert usage["total_size_gb"] > 0.01


class TestGetModelsDir:
    def test_returns_path_string(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            assert manager.get_models_dir() == tmpdir


class TestDeleteModel:
    def test_delete_nonexistent_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            assert manager.delete_model("nonexistent_model") is False

    def test_delete_existing_model_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            model_dir = Path(tmpdir) / "test_model"
            model_dir.mkdir()
            (model_dir / "file.txt").write_text("data")
            assert manager.delete_model("test_model") is True
            assert not model_dir.exists()

    def test_delete_updates_metadata_and_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            model_dir = Path(tmpdir) / "test_model"
            model_dir.mkdir()
            (model_dir / "model.gguf").write_text("dummy")

            # 先发现
            manager.discover_models()
            assert "test_model" in manager._discovered_models

            # 删除
            assert manager.delete_model("test_model") is True
            assert "test_model" not in manager._discovered_models
            assert "test_model" not in manager._metadata


class TestConvenienceFunctions:
    def test_get_default_manager(self):
        mgr = get_default_manager()
        assert isinstance(mgr, ModelManager)
        assert mgr.get_models_dir() is not None

    def test_download_model_with_progress_requires_params(self):
        # 现在需要 modelscope_id 参数
        with pytest.raises(TypeError):
            download_model_with_progress("nonexistent_model")


class TestModelInfoFromDict:
    def test_from_dict_creates_valid_model_info(self):
        data = {
            "name": "test-model",
            "modelscope_id": "test/repo",
            "file_pattern": "*.gguf",
            "size_gb": 1.5,
            "description": "Test",
            "quantization": "Q8_0",
            "parameters": "2B",
            "recommended_gpu_memory_gb": 4,
            "local_path": "/path/to/model.gguf",
            "is_downloaded": True,
            "version": "v1"
        }
        info = ModelInfo.from_dict(data)
        assert info.name == "test-model"
        assert info.size_gb == 1.5
        assert info.is_downloaded is True
