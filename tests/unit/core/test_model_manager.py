"""Tests for core/local_inference/model_manager.py"""

import json
import tempfile
from pathlib import Path
from typing import Dict, Any

import pytest

from core.local_inference.model_manager import (
    ModelManager,
    ModelInfo,
    get_default_manager,
    download_model_with_progress,
)


class TestModelRegistry:
    def test_registry_has_expected_models(self):
        manager = ModelManager(models_dir="C:\\nonexistent_test_models")
        assert "qwen3.5-2b-qwen3.6-plus-distilled-f16" in manager.MODEL_REGISTRY
        assert "qwen3.5-9b-fp16" in manager.MODEL_REGISTRY
        assert "qwen3.5-35b-a3b-fp16" in manager.MODEL_REGISTRY
        assert "gemma4-2b-q8_0" in manager.MODEL_REGISTRY

    def test_registry_contains_required_keys(self):
        manager = ModelManager(models_dir="C:\\nonexistent_test_models")
        for name, info in manager.MODEL_REGISTRY.items():
            assert "modelscope_id" in info
            assert "file_pattern" in info
            assert "size_gb" in info
            assert "description" in info
            assert "quantization" in info
            assert "parameters" in info
            assert "recommended_gpu_memory_gb" in info

    def test_model_count(self):
        manager = ModelManager(models_dir="C:\\nonexistent_test_models")
        assert len(manager.MODEL_REGISTRY) == 4


class TestGetModelInfo:
    def test_get_existing_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            info = manager.get_model_info("qwen3.5-9b-fp16")
            assert info is not None
            assert info.name == "qwen3.5-9b-fp16"
            assert info.size_gb == 18.0
            assert info.parameters == "9B"
            assert info.recommended_gpu_memory_gb == 16
            assert info.is_downloaded is False

    def test_get_nonexistent_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            assert manager.get_model_info("nonexistent") is None

    def test_model_info_to_dict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            info = manager.get_model_info("qwen3.5-2b-qwen3.6-plus-distilled-f16")
            assert info is not None
            d = info.to_dict()
            assert d["name"] == "qwen3.5-2b-qwen3.6-plus-distilled-f16"
            assert d["size_gb"] == 2.8
            assert d["is_downloaded"] is False


class TestGetAllModels:
    def test_returns_all_models(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            models = manager.get_all_models()
            assert len(models) == 4
            assert all(isinstance(m, ModelInfo) for m in models)

    def test_none_for_missing_registry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            # Temporarily clear registry
            original = dict(manager.MODEL_REGISTRY)
            manager.MODEL_REGISTRY.clear()
            models = manager.get_all_models()
            # All entries will be None because get_model_info returns None for unregistered
            assert models == []
            manager.MODEL_REGISTRY.update(original)


class TestGetAvailableModels:
    def test_no_downloaded_models(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            available = manager.get_available_models()
            assert available == []

    def test_is_downloaded_checks_model_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            assert manager.is_model_downloaded("qwen3.5-2b-qwen3.6-plus-distilled-f16") is False

    def test_is_downloaded_nonexistent_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            assert manager.is_model_downloaded("nonexistent") is False


class TestGetModelPath:
    def test_nonexistent_model_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            assert manager.get_model_path("nonexistent") is None

    def test_undownloaded_model_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            assert manager.get_model_path("qwen3.5-2b-qwen3.6-plus-distilled-f16") is None


class TestRecommendModel:
    def test_recommend_high_memory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            result = manager.recommend_model(gpu_memory_gb=32)
            assert result == "qwen3.5-35b-a3b-fp16"

    def test_recommend_medium_memory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            result = manager.recommend_model(gpu_memory_gb=16)
            assert result == "qwen3.5-9b-fp16"

    def test_recommend_low_memory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            result = manager.recommend_model(gpu_memory_gb=8)
            assert result == "qwen3.5-2b-qwen3.6-plus-distilled-f16"

    def test_recommend_insufficient_memory_returns_smallest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            result = manager.recommend_model(gpu_memory_gb=1)
            assert result == "qwen3.5-2b-qwen3.6-plus-distilled-f16"

    def test_recommend_exact_boundary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            result = manager.recommend_model(gpu_memory_gb=24)
            assert result == "qwen3.5-35b-a3b-fp16"

    def test_recommend_16gb_boundary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            result = manager.recommend_model(gpu_memory_gb=24)
            assert result != "qwen3.5-9b-fp16"


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


class TestDiskUsage:
    def test_no_downloaded_models(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            usage = manager.get_disk_usage()
            assert usage["total_size_gb"] == 0.0
            assert usage["model_count"] == 0


class TestGetModelsDir:
    def test_returns_path_string(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelManager(models_dir=tmpdir)
            assert manager.get_models_dir() == tmpdir


class TestConvenienceFunctions:
    def test_get_default_manager(self):
        mgr = get_default_manager()
        assert isinstance(mgr, ModelManager)
        assert mgr.get_models_dir() is not None

    def test_download_model_with_progress_unknown_model(self):
        with pytest.raises(ValueError, match="Unknown model"):
            download_model_with_progress("nonexistent_model")


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