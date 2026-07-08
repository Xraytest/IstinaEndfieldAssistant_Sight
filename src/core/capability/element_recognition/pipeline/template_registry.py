from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

import cv2
import numpy as np

from core.foundation.paths import get_project_root

logger = logging.getLogger(__name__)


class TemplateRegistry:
    _instance: Optional[TemplateRegistry] = None
    _templates: Dict[str, np.ndarray] = {}
    _template_paths: Dict[str, Path] = {}
    _loaded_modules: Set[str] = set()
    _module_counts: Dict[str, int] = {}

    def __new__(cls) -> TemplateRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_initialized"):
            self._root = get_project_root() / "assets" / "templates"
            self._initialized = True

    def _scan_module_dir(self, module_dir: Path, module_name: str) -> int:
        count = 0
        for fpath in module_dir.glob("*.png"):
            key = f"{module_name}/{fpath.stem}"
            if key not in self._templates:
                img = cv2.imread(str(fpath), cv2.IMREAD_GRAYSCALE)
                if img is not None and img.shape[0] >= 8 and img.shape[1] >= 8:
                    self._templates[key] = img
                    self._template_paths[key] = fpath
                    count += 1
        return count

    def load_module(self, module_name: str) -> int:
        if self._is_maaend_tag(module_name):
            return self.load_maaend_module(module_name.replace("maaend:", "", 1))
        module_dir = self._root / module_name
        if not module_dir.is_dir():
            return 0
        count = self._scan_module_dir(module_dir, module_name)
        self._loaded_modules.add(module_name)
        self._module_counts[module_name] = count
        if count:
            logger.info(f"Loaded {count} templates from module '{module_name}'")
        else:
            existing = sum(1 for k in self._templates if k.startswith(f"{module_name}/"))
            if existing:
                logger.debug(f"Module '{module_name}' already loaded ({existing} templates)")
                self._module_counts[module_name] = existing
                count = existing
        return count

    def load_all(self) -> int:
        total = 0
        if not self._root.is_dir():
            logger.warning(f"Template root not found: {self._root}")
            return 0
        for child in sorted(self._root.iterdir()):
            if child.is_dir():
                total += self.load_module(child.name)
        return total

    @staticmethod
    def _is_maaend_tag(module_name: str) -> bool:
        return module_name.startswith("maaend:")

    def load_maaend_module(self, module_name: str) -> int:
        if module_name.startswith("maaend:"):
            module_name = module_name.replace("maaend:", "", 1)
        maaend_root = get_project_root() / "3rd-part" / "maaend" / "resource" / "image"
        module_dir = maaend_root / module_name
        if not module_dir.is_dir():
            return 0
        count = self._scan_module_dir(module_dir, module_name)
        self._loaded_modules.add(f"maaend:{module_name}")
        self._module_counts[f"maaend:{module_name}"] = count
        if count:
            logger.info(f"Loaded {count} templates from MaaEnd module '{module_name}'")
        else:
            existing = sum(1 for k in self._templates if k.startswith(f"{module_name}/"))
            if existing:
                self._module_counts[f"maaend:{module_name}"] = existing
                count = existing
        return count

    def get(self, template_ref: str) -> Optional[np.ndarray]:
        if template_ref.endswith(".png"):
            template_ref = template_ref[:-4]
        return self._templates.get(template_ref)

    def get_path(self, template_ref: str) -> Optional[Path]:
        if template_ref.endswith(".png"):
            template_ref = template_ref[:-4]
        return self._template_paths.get(template_ref)

    def resolve(self, template_ref: str) -> Optional[np.ndarray]:
        if template_ref.endswith(".png"):
            key = template_ref[:-4]
        else:
            key = template_ref
        img = self._templates.get(key)
        if img is not None:
            return img
        for tpl_key, tpl_img in self._templates.items():
            if tpl_key.endswith((key, key.replace("/", "_"))):
                return tpl_img
            if key.endswith(tpl_key.split("/")[-1]):
                return tpl_img
        return None

    def available_templates(self) -> List[str]:
        return sorted(self._templates.keys())

    def available_modules(self) -> List[str]:
        modules = set()
        for key in self._templates:
            if "/" in key:
                modules.add(key.split("/")[0])
        return sorted(modules)

    def is_module_loaded(self, module_name: str) -> bool:
        return module_name in self._loaded_modules or f"maaend:{module_name}" in self._loaded_modules

    def clear(self) -> None:
        self._templates.clear()
        self._template_paths.clear()
        self._loaded_modules.clear()
