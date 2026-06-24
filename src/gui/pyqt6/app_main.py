"""
PyQt6 application entry - simplified for agent mode
"""
import sys
import os
import ctypes


def _set_dark_title_bar(window):
    """Set Windows 10/11 title bar to dark mode via DWM API."""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(window.winId())
        if hwnd == 0:
            return
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Windows 10 20H1+)
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        # DWMWA_WINDOW_CORNER_PREFERENCE = 33 (圆角支持)
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_ROUND = 2
        DWMWCP_ROUND_SMAILL = 3
        
        # 创建值变量（必须保持引用直到 API 调用完成）
        dark_mode_value = ctypes.c_int(1)
        corner_value = ctypes.c_int(DWMWCP_ROUND)
        
        # 启用暗色标题栏
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(dark_mode_value),
            ctypes.sizeof(dark_mode_value),
        )
        # 启用圆角（可选，提升视觉效果）
        try:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(corner_value),
                ctypes.sizeof(corner_value),
            )
        except Exception:
            pass
    except Exception:
        pass


def _enable_windows_dark_mode():
    """Enable dark mode for all app dialogs via uxtheme (Windows 10 1809+)."""
    if sys.platform != "win32":
        return
    try:
        # SetPreferredAppMode(AllowDark) — ordinal 135 in uxtheme.dll
        ALLOW_DARK = 1
        ctypes.windll.uxtheme.SetPreferredAppMode(ALLOW_DARK)
        ctypes.windll.uxtheme.FlushMenuThemes()
    except Exception:
        pass
    try:
        # AllowDarkModeForWindow for the app itself (ordinal 133)
        ctypes.windll.uxtheme.AllowDarkModeForWindow = ctypes.windll.uxtheme[133]
        ctypes.windll.uxtheme.AllowDarkModeForWindow.restype = ctypes.c_int
        ctypes.windll.uxtheme.AllowDarkModeForWindow.argtypes = [ctypes.c_int, ctypes.c_int]
    except Exception:
        pass


def _install_dark_title_bar_hook(app):
    """Install event filter to auto-darken every top-level dialog title bar and
    defensively convert unparented top-level dialogs to TOOL windows to avoid
    stray taskbar entries.
    """
    if sys.platform != "win32":
        return
    try:
        from PyQt6.QtCore import QObject, QEvent, Qt

        class DarkTitleBarFilter(QObject):
            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.Show:
                    # Apply dark title bar and defensive TOOL conversion for unparented dialogs
                    try:
                        if hasattr(obj, 'isWindow') and obj.isWindow():
                            # 获取类名
                            cls_name = type(obj).__name__ if obj is not None else ''
                            
                            # 主窗口在 showEvent 中处理暗色标题栏（因为 setWindowFlags 会重建 HWND）
                            # 这里只处理对话框
                            if cls_name == 'MainWindow':
                                return False  # 跳过主窗口
                                
                            try:
                                _set_dark_title_bar(obj)
                            except Exception:
                                pass

                            try:
                                has_parent = False
                                try:
                                    has_parent = obj.parent() is not None
                                except Exception:
                                    has_parent = False
                                title = ''
                                try:
                                    title = obj.windowTitle() or ''
                                except Exception:
                                    title = ''
                                DIALOG_CLASSES = {'QMessageBox', 'QDialog', 'QFileDialog', 'QInputDialog', 'QColorDialog', 'QProgressDialog'}
                                # 只处理对话框
                                if (not has_parent) and (not title.strip() or cls_name in DIALOG_CLASSES):
                                    try:
                                        obj.setWindowFlag(Qt.WindowType.Tool, True)
                                        try:
                                            obj.setWindowFlags(obj.windowFlags())
                                        except Exception:
                                            pass
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                    except Exception:
                        pass
                return False

        _filter = DarkTitleBarFilter(app)
        app.installEventFilter(_filter)
    except Exception:
        pass
import logging
import json
from typing import Optional, Dict, Any

# Lazy import PyQt6 to allow testing without it installed
def _get_qt():
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QObject, pyqtSignal, QThread
        return QApplication, QObject, pyqtSignal, QThread
    except ImportError:
        raise ImportError("PyQt6 is not installed. Run: pip install PyQt6")

try:
    from .main_window import MainWindow
    from .theme.theme_manager import ThemeManager
except ImportError:
    from core.foundation.paths import ensure_src_path
    ensure_src_path(__file__)
    from gui.pyqt6.main_window import MainWindow
    from gui.pyqt6.theme.theme_manager import ThemeManager


class QtLogHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self._qt_initialized = False
        self._log_signal = None
        self._QObject = None
        
    def _ensure_qt(self):
        if not self._qt_initialized:
            QApplication, QObject, pyqtSignal, QThread = _get_qt()
            self._QObject = QObject
            self._log_signal = pyqtSignal(str, str)
            self._qt_initialized = True

    def emit(self, record):
        try:
            msg = self.format(record)
            # Signal emission would go here when Qt is available
        except Exception:
            pass


class WorkerThread:
    def __init__(self, target, args=None):
        _, _, _, QThread = _get_qt()
        self._thread = QThread()
        self.target = target
        self.args = args or ()
        self.finished_callbacks = []
        
    def start(self):
        import threading
        def run():
            result = self.target(*self.args)
            for cb in self.finished_callbacks:
                cb(result)
        threading.Thread(target=run, daemon=True).start()
    
    def connect_finished(self, callback):
        self.finished_callbacks.append(callback)


class PyQt6Application:
    def __init__(self, argv=None, agent_executor=None, gui_client=None,
                 screen_capture=None, config=None):
        QApplication, _, _, _ = _get_qt()
        self._app = QApplication(argv or sys.argv)
        self.main_window = None
        self.agent_executor = agent_executor
        self.gui_client = gui_client
        self.screen_capture = screen_capture
        self.config = config

    def run(self):
        self.main_window = MainWindow(
            agent_executor=self.agent_executor,
            gui_client=self.gui_client,
            screen_capture=self.screen_capture,
            config=self.config
        )
        self.main_window.show()
        return self._app.exec()


def run_application(agent_executor=None, gui_client=None,
                    screen_capture=None, touch_executor=None,
                    config=None, inference_manager=None):
    """
    Run the PyQt6 application with business logic components（纯本地版）

    Args:
        agent_executor: AgentExecutor instance for agent execution
        gui_client: GUIClient instance (GUI layer's only inference entry)
        screen_capture: ScreenCapture instance for screenshots
        touch_executor: TouchManager instance for touch operations
        config: Configuration dictionary
        inference_manager: InferenceManager instance for local inference
    """
    QApplication, _, _, _ = _get_qt()
    print("[应用主进程] 创建 QApplication...")
    app = QApplication(sys.argv)
    # 防止最后一个窗口被关闭时退出（隐藏到托盘时仍保持运行）
    try:
        app.setQuitOnLastWindowClosed(False)
    except Exception:
        pass

    # 启用 Windows 暗色模式（弹窗标题栏自动变暗）
    _enable_windows_dark_mode()

    # 应用主题
    print("[应用主进程] 应用主题...")
    theme = ThemeManager.get_instance()
    app.setStyleSheet(theme.get_stylesheet() + """
        /* 暗色弹窗 */
        QMessageBox {
            background-color: #0c0c14;
            color: #e8e8ee;
        }
        QMessageBox QLabel {
            color: #e8e8ee;
            font-size: 12px;
            font-family: Consolas;
        }
        QMessageBox QPushButton {
            background-color: rgba(24, 209, 255, 0.10);
            color: #18d1ff;
            border: 1px solid rgba(24, 209, 255, 0.25);
            border-radius: 2px;
            padding: 6px 16px;
            font-size: 11px;
            font-family: Consolas;
            min-width: 70px;
        }
        QMessageBox QPushButton:hover {
            background-color: rgba(24, 209, 255, 0.18);
        }
    """)

    # 自动为所有顶层窗口（含弹窗）设置暗色标题栏
    _install_dark_title_bar_hook(app)
    
    # 创建主窗口
    print("[应用主进程] 创建主窗口...")
    main_window = MainWindow(
        agent_executor=agent_executor,
        gui_client=gui_client,
        screen_capture=screen_capture,
        touch_executor=touch_executor,
        config=config,
        inference_manager=inference_manager
    )

    # 在显示窗口前创建 native hidden owner（提高 owner 稳定性）
    try:
        # 主窗口提供 _ensure_hidden_owner，会优先尝试 native owner
        main_window._ensure_hidden_owner()
    except Exception:
        pass

    # 设置变更时自动持久化到 client_config.json
    def _save_config(updated_config):
        """统一保存到项目根目录的配置文件"""
        # 确定唯一配置文件路径：项目根目录
        _f = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(_f)))
        config_path = os.path.join(project_root, "config", "client_config.json")

        try:
            import json, tempfile
            import os as _os
            # 递归清理，只保留 JSON 可序列化的基本类型
            UNSET = object()
            def _sanitize(obj):
                if isinstance(obj, (str, int, float, bool)) or obj is None:
                    return obj
                if isinstance(obj, dict):
                    out = {}
                    for k, v in obj.items():
                        if not isinstance(k, str):
                            continue
                        sv = _sanitize(v)
                        if sv is not UNSET:
                            out[k] = sv
                    return out
                if isinstance(obj, list):
                    arr = []
                    for item in obj:
                        sv = _sanitize(item)
                        if sv is not UNSET:
                            arr.append(sv)
                    return arr
                return UNSET

            cleaned = _sanitize(updated_config)
            if cleaned is UNSET:
                cleaned = {}
            # 确保目录存在
            _os.makedirs(_os.path.dirname(config_path), exist_ok=True)
            # 读取现有配置并合并，避免因序列化失败而清空配置文件
            existing = {}
            try:
                if _os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as fr:
                        existing = json.load(fr)
            except Exception:
                existing = {}

            def _merge(a, b):
                for k, v in (b or {}).items():
                    if isinstance(v, dict) and isinstance(a.get(k), dict):
                        _merge(a[k], v)
                    else:
                        a[k] = v

            if isinstance(cleaned, dict):
                _merge(existing, cleaned)
            else:
                # If cleaned is not dict (e.g., list), replace entirely
                existing = cleaned

            # 原子写入
            fd, tmp_path = tempfile.mkstemp(prefix="client_config_", suffix=".tmp", dir=_os.path.dirname(config_path))
            with _os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
            _os.replace(tmp_path, config_path)
        except Exception as e:
            from core.foundation.logger import get_logger, LogCategory
            get_logger().exception(LogCategory.MAIN, "保存配置失败", error=str(e))
    main_window.settings_changed.connect(_save_config)

    print("[应用主进程] 显示窗口...")
    main_window.show()
    main_window.raise_()
    main_window.activateWindow()

    # 设置 Windows 标题栏暗色模式
    _set_dark_title_bar(main_window)

    print("[应用主进程] 启动事件循环...")
    return app.exec()
