"""Lightweight internationalization framework for PyQt6.

Provides JSON-based translation loading and runtime language switching.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from PyQt6.QtCore import QLocale, QSettings, QTranslator
from PyQt6.QtWidgets import QApplication


class LocaleManager:
    """Manages application translations and language preferences."""

    def __init__(self, locales_dir: Optional[Path] = None) -> None:
        if locales_dir is None:
            locales_dir = Path(__file__).parent.parent / "locales"
        self._locales_dir = locales_dir
        self._translations: Dict[str, Dict[str, str]] = {}
        self._current_locale: str = "zh_CN"
        self._settings = QSettings("ArkStudio", "IstinaEndfieldAssistant")
        # I18N-1: 持有 translator 引用，防止被 GC 回收导致翻译失效
        self._qt_translator: Optional[QTranslator] = None
        self._load_all()

    def _load_all(self) -> None:
        for path in self._locales_dir.glob("*.json"):
            locale = path.stem
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._translations[locale] = data
            except Exception:
                continue

    def available_locales(self) -> list[dict]:
        result = []
        for locale, data in self._translations.items():
            result.append({
                "id": locale,
                "name": data.get("_meta", {}).get("name", locale),
                "native": data.get("_meta", {}).get("native", locale),
            })
        return result

    def current_locale(self) -> str:
        return self._current_locale

    def set_locale(self, locale: str) -> None:
        if locale not in self._translations:
            return
        self._current_locale = locale
        self._settings.setValue("gui/locale", locale)

    def load_saved_locale(self) -> None:
        saved = self._settings.value("gui/locale", "")
        if saved and saved in self._translations:
            self._current_locale = saved

    def tr(self, key: str, default: str = "") -> str:
        data = self._translations.get(self._current_locale, {})
        if key in data:
            return data[key]
        # fallback to zh_CN
        fallback = self._translations.get("zh_CN", {})
        if key in fallback:
            return fallback[key]
        return default or key

    def install_qt_translator(self, app: Optional[QApplication] = None) -> None:
        if app is None:
            app = QApplication.instance()
        if app is None:
            return
        # I18N-1: 持有 translator 引用，防止被 GC 回收导致翻译失效
        self._qt_translator = QTranslator(app)
        # attempt to load Qt's built-in translation for the locale
        locale = QLocale(self._current_locale)
        qm_name = f"qt_{locale.name()}"
        if self._qt_translator.load(qm_name):
            app.installTranslator(self._qt_translator)

    @property
    def locales_dir(self) -> Path:
        return self._locales_dir


_instance: Optional[LocaleManager] = None


def get_locale_manager() -> LocaleManager:
    global _instance
    if _instance is None:
        _instance = LocaleManager()
        _instance.load_saved_locale()
    return _instance
