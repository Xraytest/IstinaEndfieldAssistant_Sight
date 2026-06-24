"""Tests for core/local_inference/gpu_checker.py"""

from typing import Dict, Any, Optional
from unittest.mock import patch, MagicMock

import pytest

from core.local_inference.gpu_checker import (
    GPUChecker,
    GPUInfo,
    check_gpu,
    is_gpu_sufficient,
)


class TestGPUInfo:
    def test_default_creation(self):
        info = GPUInfo()
        assert info.name == ""
        assert info.total_memory_gb == 0.0
        assert info.free_memory_gb == 0.0
        assert info.compute_capability == ""
        assert info.driver_version == ""
        assert info.cuda_version == ""

    def test_to_dict(self):
        info = GPUInfo(
            name="RTX 4090",
            total_memory_gb=24.0,
            free_memory_gb=20.0,
            compute_capability="8.9",
            driver_version="545.84",
            cuda_version="12.1",
        )
        d = info.to_dict()
        assert d["name"] == "RTX 4090"
        assert d["total_memory_gb"] == 24.0
        assert d["free_memory_gb"] == 20.0


class TestGetRecommendedModel:
    def test_high_memory_recommends_top(self):
        checker = GPUChecker()
        result = checker._get_recommended_model(24.0)
        assert result == "qwen3.5-35b-a3b-fp16"

    def test_medium_memory(self):
        checker = GPUChecker()
        result = checker._get_recommended_model(16.0)
        assert result == "qwen3.5-9b-fp16"

    def test_low_memory(self):
        checker = GPUChecker()
        result = checker._get_recommended_model(8.0)
        assert result == "qwen3.5-0.6b-q8_0"

    def test_memory_below_all_thresholds(self):
        checker = GPUChecker()
        result = checker._get_recommended_model(4.0)
        assert result is None

    def test_exact_boundary(self):
        checker = GPUChecker()
        assert checker._get_recommended_model(24.0) == "qwen3.5-35b-a3b-fp16"
        assert checker._get_recommended_model(16.0) == "qwen3.5-9b-fp16"
        assert checker._get_recommended_model(8.0) == "qwen3.5-0.6b-q8_0"

    def test_negative_memory(self):
        checker = GPUChecker()
        result = checker._get_recommended_model(-1.0)
        assert result is None


class TestCheckMeetsRequirements:
    @patch.object(GPUChecker, "_get_total_ram_gb", return_value=16.0)
    def test_vram_sufficient(self, mock_ram):
        checker = GPUChecker()
        assert checker._check_meets_requirements(vram_gb=8.0) is True

    @patch.object(GPUChecker, "_get_total_ram_gb", return_value=16.0)
    def test_vram_insufficient_but_combined_sufficient(self, mock_ram):
        checker = GPUChecker()
        # VRAM=4, RAM=16, total=20 < 48 => not sufficient
        assert checker._check_meets_requirements(vram_gb=4.0) is False

    @patch.object(GPUChecker, "_get_total_ram_gb", return_value=44.0)
    def test_combined_sufficient(self, mock_ram):
        checker = GPUChecker()
        # VRAM=4, RAM=44, total=48 >= 48 => sufficient
        assert checker._check_meets_requirements(vram_gb=4.0) is True

    @patch.object(GPUChecker, "_get_total_ram_gb", return_value=8.0)
    def test_both_insufficient(self, mock_ram):
        checker = GPUChecker()
        assert checker._check_meets_requirements(vram_gb=2.0) is False

    @patch.object(GPUChecker, "_get_total_ram_gb", return_value=16.0)
    def test_exact_vram_threshold(self, mock_ram):
        checker = GPUChecker()
        assert checker._check_meets_requirements(vram_gb=6.0) is True
        assert checker._check_meets_requirements(vram_gb=5.9) is False


class TestGetTotalRam:
    @patch("core.local_inference.gpu_checker.psutil", None)
    def test_no_psutil_returns_zero(self):
        checker = GPUChecker()
        assert checker._get_total_ram_gb() == 0.0

    def test_with_psutil_returns_value(self):
        checker = GPUChecker()
        ram = checker._get_total_ram_gb()
        # On any real system this should be > 0
        # But CI may not have psutil, so just check type
        assert isinstance(ram, float)


class TestCheckGpuAvailability:
    @patch.object(GPUChecker, "_check_via_nvml", return_value={"available": False})
    @patch.object(GPUChecker, "_check_via_torch", return_value={"available": False})
    @patch.object(GPUChecker, "_check_via_nvidia_smi", return_value={"available": False})
    def test_all_methods_fail(self, mock_nvml, mock_torch, mock_smi):
        checker = GPUChecker()
        result = checker.check_gpu_availability()
        assert result["available"] is False
        assert result["error"] is not None

    def test_checked_flag_set(self):
        checker = GPUChecker()
        checker.check_gpu_availability()
        assert checker._checked is True


class TestConvenienceFunctions:
    def test_check_gpu(self):
        result = check_gpu()
        assert isinstance(result, dict)
        assert "available" in result

    def test_is_gpu_sufficient(self):
        result = is_gpu_sufficient()
        assert isinstance(result, bool)


class TestMeetsRequirements:
    def test_not_checked_no_gpu_info(self):
        checker = GPUChecker()
        assert checker.meets_requirements() is False

    def test_checked_and_no_gpu(self):
        checker = GPUChecker()
        checker._checked = True
        checker._gpu_info = []
        assert checker.meets_requirements() is False


class TestGetRecommendedModelPublic:
    @patch.object(GPUChecker, "check_gpu_availability", return_value={"available": False, "recommended_model": None, "error": "no GPU"})
    def test_not_checked_no_gpu(self, mock_check):
        checker = GPUChecker()
        assert checker.get_recommended_model() is None

    def test_checked_no_gpu(self):
        checker = GPUChecker()
        checker._checked = True
        checker._gpu_info = []
        assert checker.get_recommended_model() is None


class TestNvidiaSmiDetection:
    @patch("subprocess.check_output")
    def test_parse_nvidia_smi_output(self, mock_check_output):
        mock_check_output.side_effect = [
            "NVIDIA GeForce RTX 4090, 24564 MiB, 20000 MiB, 4564 MiB, 8.9\n",
            "545.84\n",
        ]
        checker = GPUChecker()
        result = checker._check_via_nvidia_smi()
        assert result["available"] is True
        assert result["gpu_count"] == 1
        assert result["gpus"][0]["name"] == "NVIDIA GeForce RTX 4090"

    @patch("subprocess.check_output")
    def test_nvidia_smi_no_file(self, mock_check_output):
        mock_check_output.side_effect = FileNotFoundError()
        checker = GPUChecker()
        result = checker._check_via_nvidia_smi()
        assert result["available"] is False