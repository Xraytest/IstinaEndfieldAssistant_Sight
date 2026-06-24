#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
椤甸潰鐗瑰緛閲囬泦宸ュ叿

鐢ㄤ簬閲囬泦鍚勭被椤甸潰鐨勭壒寰佹牱鏈紝鏋勫缓椤甸潰鐗瑰緛鏁版嵁搴撱€?
鐢ㄦ硶:
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
    from core.capability.screen_analysis.advanced_analyzer import (
        GameScreenAnalyzer, PageType, PageAnalysisResult
    )

# 娉ㄦ剰: advanced_analyzer 宸插簾寮冿紝鏂颁唬鐮佽浣跨敤 core.page_analyzer.HighPrecisionPageAnalyzerV2

ADB_PATH = PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"
DEVICE = "localhost:16512"


@dataclass
class PageSample:
    """椤甸潰鏍锋湰"""
    page_type: str
    timestamp: str
    screenshot_path: str
    analysis_result: dict
    
    def to_dict(self):
        return asdict(self)


class PageProfileCollector:
    """椤甸潰鐗瑰緛閲囬泦鍣?""
    
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or str(PROJECT_ROOT / "data" / "page_profiles")
        os.makedirs(self.output_dir, exist_ok=True)
        self.analyzer = GameScreenAnalyzer()
        self.samples: list = []
    
    def capture_screenshot(self) -> np.ndarray:
        """鎴彇灞忓箷"""
        result = subprocess.run(
            [str(ADB_PATH), "-s", DEVICE, "exec-out", "screencap", "-p"],
            capture_output=True, timeout=10
        )
        if result.returncode == 0 and len(result.stdout) > 1000:
            img = cv2.imdecode(np.frombuffer(result.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
            # 鏃嬭浆鍒版í灞?            img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            img = cv2.resize(img, (1280, 720))
            return img
        return None
    
    def save_screenshot(self, image: np.ndarray, page_type: str, index: int) -> str:
        """淇濆瓨鎴浘"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{page_type}_{index:03d}_{timestamp}.png"
        path = os.path.join(self.output_dir, filename)
        cv2.imwrite(path, image)
        return path
    
    def collect_samples(self, page_type: PageType, count: int = 5, 
                       ocr_text: str = "", yolo_classes: list = None) -> list:
        """
        閲囬泦椤甸潰鏍锋湰
        
        Args:
            page_type: 椤甸潰绫诲瀷
            count: 閲囬泦鏁伴噺
            ocr_text: OCR 鏂囨湰 (鍙€?
            yolo_classes: YOLO 妫€娴嬬粨鏋?(鍙€?
            
        Returns:
            閲囬泦鐨勬牱鏈垪琛?        """
        if yolo_classes is None:
            yolo_classes = []
            
        samples = []
        print(f"\n[閲囬泦] 寮€濮嬮噰闆?{page_type.value} 椤甸潰鏍锋湰 ({count} 涓?")
        print("="*60)
        
        for i in range(count):
            print(f"\n[鏍锋湰 {i+1}/{count}] 璇锋寜 Enter 鎴彇褰撳墠鐢婚潰...")
            input("> ")
            
            # 鎴浘
            image = self.capture_screenshot()
            if image is None:
                print("[閿欒] 鎴浘澶辫触")
                continue
            
            # 淇濆瓨鎴浘
            screenshot_path = self.save_screenshot(image, page_type.value, i)
            print(f"  鎴浘宸蹭繚瀛橈細{screenshot_path}")
            
            # 鍒嗘瀽
            result = self.analyzer.analyze(image, ocr_text=ocr_text, yolo_classes=yolo_classes)
            print(f"  鍒嗘瀽缁撴灉锛歿result.predicted_type.value} (缃俊搴?{result.confidence:.3f})")
            
            # 鎵撳嵃鐗瑰緛鎽樿
            print(f"  閲戣壊鍏冪礌锛歿result.color_features.golden_count}涓?)
            print(f"  杈圭紭瀵嗗害锛歿result.texture_features.edge_density:.3f}")
            print(f"  浜害锛歿result.color_features.brightness_mean:.1f}")
            print(f"  瀵艰埅鏍忓瘑搴︼細{result.spatial_features.nav_bar_density:.3f}")
            
            # 淇濆瓨鏍锋湰
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
            
            # 灏忓仠椤?            time.sleep(1)
        
        return samples
    
    def save_profiles(self, samples: list, page_type: str):
        """淇濆瓨椤甸潰鐗瑰緛閰嶇疆鏂囦欢"""
        # 璁＄畻鐗瑰緛缁熻
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
        
        # 淇濆瓨閰嶇疆鏂囦欢
        profile_path = os.path.join(self.output_dir, f"{page_type}_profile.json")
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        
        print(f"\n[淇濆瓨] 鐗瑰緛閰嶇疆鏂囦欢锛歿profile_path}")
        print(f"  鏍锋湰鏁帮細{len(samples)}")
        print(f"  閲戣壊鍏冪礌鑼冨洿锛歔{profile['statistics']['golden_count']['min']}, {profile['statistics']['golden_count']['max']}]")
        print(f"  杈圭紭瀵嗗害鑼冨洿锛歔{profile['statistics']['edge_density']['min']:.3f}, {profile['statistics']['edge_density']['max']:.3f}]")
        
        return profile_path
    
    def update_analyzer_profiles(self):
        """鏇存柊鍒嗘瀽鍣ㄧ殑椤甸潰鐗瑰緛鏁版嵁搴?""
        # 鎵弿鎵€鏈夊凡閲囬泦鐨勯厤缃枃浠?        profile_files = list(Path(self.output_dir).glob("*_profile.json"))
        
        print(f"\n[鏇存柊] 鎵惧埌 {len(profile_files)} 涓厤缃枃浠?)
        
        updated_profiles = {}
        for profile_file in profile_files:
            with open(profile_file, "r", encoding="utf-8") as f:
                profile = json.load(f)
            
            page_type = profile["page_type"]
            stats = profile["statistics"]
            
            # 杞崲涓?PAGE_PROFILES 鏍煎紡
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
            
            print(f"  {page_type}: 閲戣壊=[{updated_profiles[page_type]['golden_count']}], "
                  f"杈圭紭=[{updated_profiles[page_type]['edge_density'][0]:.3f}, {updated_profiles[page_type]['edge_density'][1]:.3f}]")
        
        # 淇濆瓨鏇存柊鍚庣殑閰嶇疆鏂囦欢
        updated_path = os.path.join(self.output_dir, "updated_page_profiles.json")
        with open(updated_path, "w", encoding="utf-8") as f:
            json.dump(updated_profiles, f, ensure_ascii=False, indent=2)
        
        print(f"\n[淇濆瓨] 鏇存柊鍚庣殑鐗瑰緛鏁版嵁搴擄細{updated_path}")
        print("[鎻愮ず] 璇峰皢姝ら厤缃鍒跺埌 advanced_analyzer.py 鐨?PAGE_PROFILES 涓?)
        
        return updated_path


def main():
    parser = argparse.ArgumentParser(description="椤甸潰鐗瑰緛閲囬泦宸ュ叿")
    parser.add_argument("--type", "-t", type=str, required=True,
                       choices=["world", "quest_panel", "exit_dialog", "title", 
                               "loading", "menu", "settings", "event_panel"],
                       help="椤甸潰绫诲瀷")
    parser.add_argument("--count", "-c", type=int, default=5,
                       help="閲囬泦鏍锋湰鏁伴噺 (榛樿锛?)")
    parser.add_argument("--ocr", type=str, default="",
                       help="OCR 鏂囨湰 (鍙€?")
    parser.add_argument("--update", action="store_true",
                       help="鏇存柊鍒嗘瀽鍣ㄧ殑鐗瑰緛鏁版嵁搴?)
    
    args = parser.parse_args()
    
    # 鏄犲皠椤甸潰绫诲瀷
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
        # 鏇存柊鐗瑰緛鏁版嵁搴?        collector.update_analyzer_profiles()
    else:
        # 閲囬泦鏍锋湰
        page_type = type_mapping[args.type]
        samples = collector.collect_samples(page_type, args.count, args.ocr)
        
        if samples:
            # 淇濆瓨閰嶇疆鏂囦欢
            collector.save_profiles(samples, args.type)
            
            print("\n" + "="*60)
            print("閲囬泦瀹屾垚!")
            print(f"鍏遍噰闆?{len(samples)} 涓牱鏈?)
            print("="*60)


if __name__ == "__main__":
    main()

