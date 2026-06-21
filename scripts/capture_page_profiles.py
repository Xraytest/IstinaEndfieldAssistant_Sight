#!/usr/bin/env python3
"""
页面特征采集工具

用于采集各类页面的特征样本，构建页面特征数据库。

用法:
    python scripts/capture_page_profiles.py --type world --count 10
    python scripts/capture_page_profiles.py --type quest_panel --count 5
"""

import sys, os, json, argparse, time
from pathlib import Path
from datetime import datetime
import subprocess
import cv2
import numpy as np
from dataclasses import dataclass, asdict

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from core.screen_analysis.advanced_analyzer import (
        GameScreenAnalyzer, PageType, PageAnalysisResult
    )

# 注意: advanced_analyzer 已废弃，新代码请使用 core.page_analyzer.HighPrecisionPageAnalyzerV2

ADB_PATH = PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"
DEVICE = "localhost:16512"


@dataclass
class PageSample:
    """页面样本"""
    page_type: str
    timestamp: str
    screenshot_path: str
    analysis_result: dict
    
    def to_dict(self):
        return asdict(self)


class PageProfileCollector:
    """页面特征采集器"""
    
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or str(PROJECT_ROOT / "data" / "page_profiles")
        os.makedirs(self.output_dir, exist_ok=True)
        self.analyzer = GameScreenAnalyzer()
        self.samples: list = []
    
    def capture_screenshot(self) -> np.ndarray:
        """截取屏幕"""
        result = subprocess.run(
            [str(ADB_PATH), "-s", DEVICE, "exec-out", "screencap", "-p"],
            capture_output=True, timeout=10
        )
        if result.returncode == 0 and len(result.stdout) > 1000:
            img = cv2.imdecode(np.frombuffer(result.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
            # 旋转到横屏
            img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            img = cv2.resize(img, (1280, 720))
            return img
        return None
    
    def save_screenshot(self, image: np.ndarray, page_type: str, index: int) -> str:
        """保存截图"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{page_type}_{index:03d}_{timestamp}.png"
        path = os.path.join(self.output_dir, filename)
        cv2.imwrite(path, image)
        return path
    
    def collect_samples(self, page_type: PageType, count: int = 5, 
                       ocr_text: str = "", yolo_classes: list = None) -> list:
        """
        采集页面样本
        
        Args:
            page_type: 页面类型
            count: 采集数量
            ocr_text: OCR 文本 (可选)
            yolo_classes: YOLO 检测结果 (可选)
            
        Returns:
            采集的样本列表
        """
        if yolo_classes is None:
            yolo_classes = []
            
        samples = []
        print(f"\n[采集] 开始采集 {page_type.value} 页面样本 ({count} 个)")
        print("="*60)
        
        for i in range(count):
            print(f"\n[样本 {i+1}/{count}] 请按 Enter 截取当前画面...")
            input("> ")
            
            # 截图
            image = self.capture_screenshot()
            if image is None:
                print("[错误] 截图失败")
                continue
            
            # 保存截图
            screenshot_path = self.save_screenshot(image, page_type.value, i)
            print(f"  截图已保存：{screenshot_path}")
            
            # 分析
            result = self.analyzer.analyze(image, ocr_text=ocr_text, yolo_classes=yolo_classes)
            print(f"  分析结果：{result.predicted_type.value} (置信度={result.confidence:.3f})")
            
            # 打印特征摘要
            print(f"  金色元素：{result.color_features.golden_count}个")
            print(f"  边缘密度：{result.texture_features.edge_density:.3f}")
            print(f"  亮度：{result.color_features.brightness_mean:.1f}")
            print(f"  导航栏密度：{result.spatial_features.nav_bar_density:.3f}")
            
            # 保存样本
            sample = PageSample(
                page_type=page_type.value,
                timestamp=datetime.now().isoformat(),
                screenshot_path=screenshot_path,
                analysis_result={
                    "predicted_type": result.predicted_type.value,
                    "confidence": result.confidence,
                    "spatial": {
                        "nav_bar_density": result.spatial_features.nav_bar_density,
                        "center_panel_density": result.spatial_features.center_panel_density,
                        "edge_density": result.spatial_features.edge_density,
                        "ui_clusters": result.spatial_features.ui_clusters,
                    },
                    "color": {
                        "golden_count": result.color_features.golden_count,
                        "golden_ratio": result.color_features.golden_ratio,
                        "brightness_mean": result.color_features.brightness_mean,
                        "brightness_std": result.color_features.brightness_std,
                    },
                    "texture": {
                        "edge_density": result.texture_features.edge_density,
                        "high_freq_energy": result.texture_features.high_freq_energy,
                    },
                    "analysis_log": result.analysis_log,
                }
            )
            samples.append(sample)
            
            # 小停顿
            time.sleep(1)
        
        return samples
    
    def save_profiles(self, samples: list, page_type: str):
        """保存页面特征配置文件"""
        # 计算特征统计
        golden_counts = [s.analysis_result["color"]["golden_count"] for s in samples]
        edge_densities = [s.analysis_result["texture"]["edge_density"] for s in samples]
        brightness_means = [s.analysis_result["color"]["brightness_mean"] for s in samples]
        nav_densities = [s.analysis_result["spatial"]["nav_bar_density"] for s in samples]
        
        profile = {
            "page_type": page_type,
            "sample_count": len(samples),
            "collected_at": datetime.now().isoformat(),
            "statistics": {
                "golden_count": {
                    "min": min(golden_counts),
                    "max": max(golden_counts),
                    "mean": np.mean(golden_counts),
                    "std": np.std(golden_counts),
                },
                "edge_density": {
                    "min": min(edge_densities),
                    "max": max(edge_densities),
                    "mean": np.mean(edge_densities),
                    "std": np.std(edge_densities),
                },
                "brightness_mean": {
                    "min": min(brightness_means),
                    "max": max(brightness_means),
                    "mean": np.mean(brightness_means),
                    "std": np.std(brightness_means),
                },
                "nav_bar_density": {
                    "min": min(nav_densities),
                    "max": max(nav_densities),
                    "mean": np.mean(nav_densities),
                    "std": np.std(nav_densities),
                },
            },
            "samples": [s.to_dict() for s in samples],
        }
        
        # 保存配置文件
        profile_path = os.path.join(self.output_dir, f"{page_type}_profile.json")
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        
        print(f"\n[保存] 特征配置文件：{profile_path}")
        print(f"  样本数：{len(samples)}")
        print(f"  金色元素范围：[{profile['statistics']['golden_count']['min']}, {profile['statistics']['golden_count']['max']}]")
        print(f"  边缘密度范围：[{profile['statistics']['edge_density']['min']:.3f}, {profile['statistics']['edge_density']['max']:.3f}]")
        
        return profile_path
    
    def update_analyzer_profiles(self):
        """更新分析器的页面特征数据库"""
        # 扫描所有已采集的配置文件
        profile_files = list(Path(self.output_dir).glob("*_profile.json"))
        
        print(f"\n[更新] 找到 {len(profile_files)} 个配置文件")
        
        updated_profiles = {}
        for profile_file in profile_files:
            with open(profile_file, "r", encoding="utf-8") as f:
                profile = json.load(f)
            
            page_type = profile["page_type"]
            stats = profile["statistics"]
            
            # 转换为 PAGE_PROFILES 格式
            updated_profiles[page_type] = {
                "golden_count": (
                    int(stats["golden_count"]["mean"] - 2 * stats["golden_count"]["std"]),
                    int(stats["golden_count"]["mean"] + 2 * stats["golden_count"]["std"])
                ),
                "edge_density": (
                    max(0, stats["edge_density"]["mean"] - 2 * stats["edge_density"]["std"]),
                    min(1, stats["edge_density"]["mean"] + 2 * stats["edge_density"]["std"])
                ),
                "brightness_mean": (
                    max(0, stats["brightness_mean"]["mean"] - 2 * stats["brightness_mean"]["std"]),
                    min(255, stats["brightness_mean"]["mean"] + 2 * stats["brightness_mean"]["std"])
                ),
            }
            
            print(f"  {page_type}: 金色=[{updated_profiles[page_type]['golden_count']}], "
                  f"边缘=[{updated_profiles[page_type]['edge_density'][0]:.3f}, {updated_profiles[page_type]['edge_density'][1]:.3f}]")
        
        # 保存更新后的配置文件
        updated_path = os.path.join(self.output_dir, "updated_page_profiles.json")
        with open(updated_path, "w", encoding="utf-8") as f:
            json.dump(updated_profiles, f, ensure_ascii=False, indent=2)
        
        print(f"\n[保存] 更新后的特征数据库：{updated_path}")
        print("[提示] 请将此配置复制到 advanced_analyzer.py 的 PAGE_PROFILES 中")
        
        return updated_path


def main():
    parser = argparse.ArgumentParser(description="页面特征采集工具")
    parser.add_argument("--type", "-t", type=str, required=True,
                       choices=["world", "quest_panel", "exit_dialog", "title", 
                               "loading", "menu", "settings", "event_panel"],
                       help="页面类型")
    parser.add_argument("--count", "-c", type=int, default=5,
                       help="采集样本数量 (默认：5)")
    parser.add_argument("--ocr", type=str, default="",
                       help="OCR 文本 (可选)")
    parser.add_argument("--update", action="store_true",
                       help="更新分析器的特征数据库")
    
    args = parser.parse_args()
    
    # 映射页面类型
    type_mapping = {
        "world": PageType.WORLD,
        "quest_panel": PageType.QUEST_PANEL,
        "exit_dialog": PageType.EXIT_DIALOG,
        "title": PageType.TITLE,
        "loading": PageType.LOADING,
        "menu": PageType.MENU,
        "settings": PageType.SETTINGS,
        "event_panel": PageType.EVENT_PANEL,
    }
    
    collector = PageProfileCollector()
    
    if args.update:
        # 更新特征数据库
        collector.update_analyzer_profiles()
    else:
        # 采集样本
        page_type = type_mapping[args.type]
        samples = collector.collect_samples(page_type, args.count, args.ocr)
        
        if samples:
            # 保存配置文件
            collector.save_profiles(samples, args.type)
            
            print("\n" + "="*60)
            print("采集完成!")
            print(f"共采集 {len(samples)} 个样本")
            print("="*60)


if __name__ == "__main__":
    main()
