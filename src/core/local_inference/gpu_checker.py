"""
GPU 检测模块 - 检测 NVIDIA 显卡配置和 CUDA 可用性
"""
import os
import sys
import subprocess
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
from utils.paths import ensure_src_path

try:
    import psutil
except ImportError:
    psutil = None

# 添加项目根目录到路径
ensure_src_path(__file__)

from core.logger import get_logger, LogCategory
logger = get_logger()


@dataclass
class GPUInfo:
    """GPU 信息数据类"""
    name: str = ""
    total_memory_gb: float = 0.0
    free_memory_gb: float = 0.0
    compute_capability: str = ""
    driver_version: str = ""
    cuda_version: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "total_memory_gb": self.total_memory_gb,
            "free_memory_gb": self.free_memory_gb,
            "compute_capability": self.compute_capability,
            "driver_version": self.driver_version,
            "cuda_version": self.cuda_version,
        }


class GPUChecker:
    """
    显卡检测器 - 检测 NVIDIA 显卡配置
    
    职责:
    1. 检测 CUDA 可用性
    2. 获取显卡显存信息
    3. 判断是否满足本地推理要求（VRAM>=6GB 或 VRAM+RAM>=48GB）
    4. 推荐合适的模型
    """
    
    MIN_VRAM_GB = 6  # 最低显存要求 (GB) - VRAM>=6GB
    MIN_TOTAL_MEMORY_GB = 48  # 最低总内存要求 (GB) - VRAM+RAM>=48GB
    MIN_CUDA_VERSION = "12.0"  # 最低 CUDA 版本要求
    
    # 模型推荐配置
    MODEL_RECOMMENDATIONS = {
        24: "qwen3.5-35b-a3b-fp16",
        16: "qwen3.5-9b-fp16",
        8: "qwen3.5-0.6b-q8_0",
    }
    
    def __init__(self):
        self._gpu_info: List[GPUInfo] = []
        self._cuda_available: bool = False
        self._cuda_version: str = ""
        self._driver_version: str = ""
        self._checked: bool = False
        
    def check_gpu_availability(self) -> Dict[str, Any]:
        result = {
            "available": False,
            "cuda_available": False,
            "cuda_version": "",
            "driver_version": "",
            "gpu_count": 0,
            "gpus": [],
            "meets_requirements": False,
            "recommended_model": None,
            "error": None
        }
        
        try:
            nvml_result = self._check_via_nvml()
            if nvml_result["available"]:
                result.update(nvml_result)
                self._checked = True
                return result
                
            torch_result = self._check_via_torch()
            if torch_result["available"]:
                result.update(torch_result)
                self._checked = True
                return result
                
            nvidia_smi_result = self._check_via_nvidia_smi()
            if nvidia_smi_result["available"]:
                result.update(nvidia_smi_result)
                self._checked = True
                return result
                
            result["error"] = "未检测到 NVIDIA GPU 或 CUDA 环境"
            logger.warning("GPU 检测：未检测到 NVIDIA GPU")
            
        except Exception as e:
            result["error"] = f"GPU 检测失败：{str(e)}"
            logger.exception("GPU 检测异常：%s", str(e))
        
        self._checked = True
        return result
    
    def _get_total_ram_gb(self) -> float:
        """获取系统总内存 (GB)"""
        if psutil is not None:
            return psutil.virtual_memory().total / (1024**3)
        return 0.0
    
    def _check_meets_requirements(self, vram_gb: float) -> bool:
        """检查是否满足要求：VRAM>=6GB 或 VRAM+RAM>=48GB"""
        total_ram = self._get_total_ram_gb()
        return vram_gb >= self.MIN_VRAM_GB or (vram_gb + total_ram) >= self.MIN_TOTAL_MEMORY_GB
    
    def _check_via_nvml(self) -> Dict[str, Any]:
        result = {
            "available": False,
            "cuda_available": False,
            "cuda_version": "",
            "driver_version": "",
            "gpu_count": 0,
            "gpus": [],
            "meets_requirements": False,
            "recommended_model": None,
        }
        
        try:
            from pynvml import nvmlInit, nvmlShutdown, nvmlDeviceGetCount, \
                nvmlDeviceGetHandleByIndex, nvmlDeviceGetName, nvmlDeviceGetMemoryInfo, \
                nvmlDeviceGetCudaComputeCapability, nvmlSystemGetDriverVersion
            
            nvmlInit()
            result["cuda_available"] = True
            
            try:
                result["driver_version"] = nvmlSystemGetDriverVersion().decode('utf-8')
            except Exception as e:
                logger.debug(LogCategory.MAIN, f"获取驱动版本失败：{e}")
                pass

            gpu_count = nvmlDeviceGetCount()
            result["gpu_count"] = gpu_count

            gpus = []
            max_memory = 0

            for i in range(gpu_count):
                handle = nvmlDeviceGetHandleByIndex(i)

                try:
                    name = nvmlDeviceGetName(handle).decode('utf-8')
                except Exception as e:
                    logger.debug(LogCategory.MAIN, f"获取 GPU {i} 名称失败：{e}")
                    name = f"GPU {i}"

                try:
                    mem_info = nvmlDeviceGetMemoryInfo(handle)
                    total_gb = mem_info.total / (1024**3)
                    free_gb = (mem_info.total - mem_info.used) / (1024**3)
                except Exception as e:
                    logger.debug(LogCategory.MAIN, f"获取 GPU {i} 显存信息失败：{e}")
                    total_gb = 0
                    free_gb = 0

                try:
                    major, minor = nvmlDeviceGetCudaComputeCapability(handle)
                    compute_capability = f"{major}.{minor}"
                except Exception as e:
                    logger.debug(LogCategory.MAIN, f"获取 GPU {i} 计算能力失败：{e}")
                    compute_capability = ""
                
                gpu_info = GPUInfo(
                    name=name,
                    total_memory_gb=round(total_gb, 2),
                    free_memory_gb=round(free_gb, 2),
                    compute_capability=compute_capability,
                    driver_version=result["driver_version"],
                    cuda_version=result["cuda_version"]
                )
                gpus.append(gpu_info)
                
                if total_gb > max_memory:
                    max_memory = total_gb
            
            nvmlShutdown()
            
            result["gpus"] = [g.to_dict() for g in gpus]
            result["available"] = True
            result["meets_requirements"] = self._check_meets_requirements(max_memory)
            result["recommended_model"] = self._get_recommended_model(max_memory)
            
            logger.info("GPU 检测 (NVML) 成功：gpu_count=%d, max_memory=%.2fGB", 
                       gpu_count, max_memory)
            
        except ImportError:
            logger.debug(LogCategory.MAIN, "pynvml 未安装，跳过 NVML 检测")
        except Exception as e:
            logger.debug(LogCategory.MAIN, f"NVML 检测失败：{str(e)}")
        
        return result
    
    def _check_via_torch(self) -> Dict[str, Any]:
        result = {
            "available": False,
            "cuda_available": False,
            "cuda_version": "",
            "driver_version": "",
            "gpu_count": 0,
            "gpus": [],
            "meets_requirements": False,
            "recommended_model": None,
        }
        
        try:
            import torch
            
            if not torch.cuda.is_available():
                logger.debug(LogCategory.MAIN, "PyTorch CUDA 不可用")
                return result
            
            result["cuda_available"] = True
            
            try:
                result["cuda_version"] = torch.version.cuda or ""
            except Exception as e:
                logger.debug(LogCategory.MAIN, f"获取 CUDA 版本失败：{e}")
                pass
            
            gpu_count = torch.cuda.device_count()
            result["gpu_count"] = gpu_count
            
            gpus = []
            max_memory = 0
            
            for i in range(gpu_count):
                props = torch.cuda.get_device_properties(i)
                
                total_bytes = props.total_memory
                allocated_bytes = torch.cuda.memory_allocated(i)
                
                total_gb = total_bytes / (1024**3)
                free_gb = (total_bytes - allocated_bytes) / (1024**3)
                
                gpu_info = GPUInfo(
                    name=props.name,
                    total_memory_gb=round(total_gb, 2),
                    free_memory_gb=round(free_gb, 2),
                    compute_capability=f"{props.major}.{props.minor}",
                    driver_version=result["driver_version"],
                    cuda_version=result["cuda_version"]
                )
                gpus.append(gpu_info)
                
                if total_gb > max_memory:
                    max_memory = total_gb
            
            result["gpus"] = [g.to_dict() for g in gpus]
            result["available"] = True
            result["meets_requirements"] = self._check_meets_requirements(max_memory)
            result["recommended_model"] = self._get_recommended_model(max_memory)
            
            logger.info("GPU 检测 (PyTorch) 成功：gpu_count=%d, max_memory=%.2fGB", 
                       gpu_count, max_memory)
            
        except ImportError:
            logger.debug(LogCategory.MAIN, "PyTorch 未安装，跳过 PyTorch 检测")
        except Exception as e:
            logger.debug(LogCategory.MAIN, f"PyTorch 检测失败：{str(e)}")
        
        return result
    
    def _check_via_nvidia_smi(self) -> Dict[str, Any]:
        result = {
            "available": False,
            "cuda_available": False,
            "cuda_version": "",
            "driver_version": "",
            "gpu_count": 0,
            "gpus": [],
            "meets_requirements": False,
            "recommended_model": None,
        }
        
        try:
            output = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,memory.used,compute_cap", 
                 "--format=csv,noheader"],
                universal_newlines=True,
                stderr=subprocess.DEVNULL
            )
            
            try:
                driver_output = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                    universal_newlines=True,
                    stderr=subprocess.DEVNULL
                )
                result["driver_version"] = driver_output.strip().split('\n')[0]
            except Exception as e:
                logger.debug(LogCategory.MAIN, f"获取 nvidia-smi 驱动版本失败：{e}")
                pass
            
            gpus = []
            max_memory = 0
            
            for line in output.strip().split('\n'):
                if not line:
                    continue
                    
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 5:
                    name = parts[0]
                    
                    total_str = parts[1].replace('MiB', '').strip()
                    free_str = parts[2].replace('MiB', '').strip()
                    
                    try:
                        total_gb = int(total_str) / 1024
                        free_gb = int(free_str) / 1024
                    except Exception as e:
                        logger.debug(LogCategory.MAIN, f"解析显存信息失败：{e}")
                        total_gb = 0
                        free_gb = 0
                    
                    compute_cap = parts[4]
                    
                    gpu_info = GPUInfo(
                        name=name,
                        total_memory_gb=round(total_gb, 2),
                        free_memory_gb=round(free_gb, 2),
                        compute_capability=compute_cap,
                        driver_version=result["driver_version"],
                        cuda_version=result["cuda_version"]
                    )
                    gpus.append(gpu_info)
                    
                    if total_gb > max_memory:
                        max_memory = total_gb
            
            result["gpu_count"] = len(gpus)
            result["gpus"] = [g.to_dict() for g in gpus]
            result["available"] = True
            result["cuda_available"] = True
            result["meets_requirements"] = self._check_meets_requirements(max_memory)
            result["recommended_model"] = self._get_recommended_model(max_memory)
            
            logger.info("GPU 检测 (nvidia-smi) 成功：gpu_count=%d, max_memory=%.2fGB", 
                       len(gpus), max_memory)
            
        except FileNotFoundError:
            logger.debug(LogCategory.MAIN, "nvidia-smi 命令未找到")
        except Exception as e:
            logger.debug(LogCategory.MAIN, f"nvidia-smi 检测失败：{str(e)}")
        
        return result
    
    def _get_recommended_model(self, memory_gb: float) -> Optional[str]:
        for min_mem, model in sorted(self.MODEL_RECOMMENDATIONS.items(), reverse=True):
            if memory_gb >= min_mem:
                return model
        return None
    
    def get_gpu_info(self) -> List[GPUInfo]:
        return self._gpu_info
    
    def is_cuda_available(self) -> bool:
        return self._cuda_available
    
    def get_cuda_version(self) -> str:
        return self._cuda_version
    
    def meets_requirements(self) -> bool:
        if not self._checked:
            self.check_gpu_availability()
        
        if not self._gpu_info:
            return False
        
        max_memory = max(gpu.total_memory_gb for gpu in self._gpu_info)
        return self._check_meets_requirements(max_memory)
    
    def get_recommended_model(self) -> Optional[str]:
        if not self._checked:
            result = self.check_gpu_availability()
            return result.get("recommended_model")
        
        if not self._gpu_info:
            return None
        
        max_memory = max(gpu.total_memory_gb for gpu in self._gpu_info)
        return self._get_recommended_model(max_memory)


def check_gpu() -> Dict[str, Any]:
    checker = GPUChecker()
    return checker.check_gpu_availability()


def is_gpu_sufficient() -> bool:
    checker = GPUChecker()
    return checker.meets_requirements()


if __name__ == "__main__":
    print("=" * 60)
    print("GPU 检测测试")
    print("=" * 60)
    
    result = check_gpu()
    
    print(f"\n检测结果:")
    print(f"  可用：{result['available']}")
    print(f"  CUDA 可用：{result['cuda_available']}")
    print(f"  CUDA 版本：{result['cuda_version']}")
    print(f"  驱动版本：{result['driver_version']}")
    print(f"  GPU 数量：{result['gpu_count']}")
    print(f"  满足要求：{result['meets_requirements']}")
    print(f"  推荐模型：{result['recommended_model']}")
    
    if result['gpus']:
        print(f"\nGPU 详情:")
        for i, gpu in enumerate(result['gpus']):
            print(f"  GPU {i}:")
            print(f"    名称：{gpu['name']}")
            print(f"    总显存：{gpu['total_memory_gb']:.2f} GB")
            print(f"    可用显存：{gpu['free_memory_gb']:.2f} GB")
            print(f"    计算能力：{gpu['compute_capability']}")
    
    if result['error']:
        print(f"\n错误：{result['error']}")
    
    print("\n" + "=" * 60)
