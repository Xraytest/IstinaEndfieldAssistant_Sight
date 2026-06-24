"""Stub for status indicator - replaced by Agent mode"""

from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt


class ConnectionStatusIndicator(QWidget):
    """连接状态指示器 - Agent 模式简化版"""
    
    def __init__(self, connection_type: str = "server", parent=None):
        super().__init__(parent)
        self.connection_type = connection_type
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        
        # 状态点
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #00ffa2; font-size: 10px;")
        layout.addWidget(self.status_dot)
        
        # 状态文本
        self.status_text = QLabel("ONLINE")
        self.status_text.setStyleSheet("color: #00ffa2; font-size: 11px; font-family: Consolas;")
        layout.addWidget(self.status_text)
        
        layout.addStretch()
        
        self.setStyleSheet("background-color: transparent;")
    
    def set_connected(self) -> None:
        """Set status to connected (online)"""
        self.status_dot.setStyleSheet("color: #00ffa2; font-size: 10px;")
        self.status_text.setText("ONLINE")
        self.status_text.setStyleSheet("color: #00ffa2; font-size: 11px; font-family: Consolas;")
    
    def set_disconnected(self) -> None:
        """Set status to disconnected (offline)"""
        self.status_dot.setStyleSheet("color: #ff3355; font-size: 10px;")
        self.status_text.setText("OFFLINE")
        self.status_text.setStyleSheet("color: #ff3355; font-size: 11px; font-family: Consolas;")
    
    def set_connecting(self) -> None:
        """Set status to connecting (in progress)"""
        self.status_dot.setStyleSheet("color: #fffa00; font-size: 10px;")
        self.status_text.setText("CONNECTING...")
        self.status_text.setStyleSheet("color: #fffa00; font-size: 11px; font-family: Consolas;")
    
    
class StatusIndicatorWidget(QWidget):
    """状态指示器组件 - Agent 模式简化版"""
    
    STATUS_CONNECTED = "connected"
    STATUS_CONNECTING = "connecting"
    STATUS_DISCONNECTED = "disconnected"
    STATUS_ERROR = "error"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = self.STATUS_DISCONNECTED
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #ff3355; font-size: 10px;")
        layout.addWidget(self.status_dot)
        
        self.status_text = QLabel("DISCONNECTED")
        self.status_text.setStyleSheet("color: #ff3355; font-size: 11px; font-family: Consolas;")
        layout.addWidget(self.status_text)
        
        layout.addStretch()
        self.setStyleSheet("background-color: transparent;")
    
    def set_connected(self) -> None:
        """Set status to connected"""
        self._status = self.STATUS_CONNECTED
        self.status_dot.setStyleSheet("color: #00ffa2; font-size: 10px;")
        self.status_text.setText("CONNECTED")
        self.status_text.setStyleSheet("color: #00ffa2; font-size: 11px; font-family: Consolas;")
    
    def set_disconnected(self) -> None:
        """Set status to disconnected"""
        self._status = self.STATUS_DISCONNECTED
        self.status_dot.setStyleSheet("color: #ff3355; font-size: 10px;")
        self.status_text.setText("DISCONNECTED")
        self.status_text.setStyleSheet("color: #ff3355; font-size: 11px; font-family: Consolas;")
    
    def set_connecting(self) -> None:
        """Set status to connecting"""
        self._status = self.STATUS_CONNECTING
        self.status_dot.setStyleSheet("color: #fffa00; font-size: 10px;")
        self.status_text.setText("CONNECTING...")
        self.status_text.setStyleSheet("color: #fffa00; font-size: 11px; font-family: Consolas;")
    
    def set_error(self) -> None:
        """Set status to error"""
        self._status = self.STATUS_ERROR
        self.status_dot.setStyleSheet("color: #ff6b6b; font-size: 10px;")
        self.status_text.setText("ERROR")
        self.status_text.setStyleSheet("color: #ff6b6b; font-size: 11px; font-family: Consolas;")
    
    def set_status(self, status: str) -> None:
        """Set status by name"""
        if status == self.STATUS_CONNECTED:
            self.set_connected()
        elif status == self.STATUS_DISCONNECTED:
            self.set_disconnected()
        elif status == self.STATUS_CONNECTING:
            self.set_connecting()
        elif status == self.STATUS_ERROR:
            self.set_error()


class DualStatusIndicator(QWidget):
    """双重状态指示器 - Agent 模式简化版"""
    
    def __init__(self, labels=None, parent=None):
        super().__init__(parent)
        self.labels = labels or ("首个", "次要")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(16)
        
        # 第一个指示器
        self.first_frame = QWidget()
        first_layout = QHBoxLayout(self.first_frame)
        first_layout.setContentsMargins(0, 0, 0, 0)
        
        self.first_dot = QLabel("●")
        self.first_dot.setStyleSheet("color: #ff3355; font-size: 10px;")
        self.first_text = QLabel(self.labels[0])
        self.first_text.setStyleSheet("color: #ff3355; font-size: 11px; font-family: Consolas;")
        first_layout.addWidget(self.first_dot)
        first_layout.addWidget(self.first_text)
        layout.addWidget(self.first_frame)
        
        # 分隔符
        sep = QLabel("|")
        sep.setStyleSheet("color: rgba(232, 232, 238, 0.3); font-size: 10px;")
        layout.addWidget(sep)
        
        # 第二个指示器
        self.second_frame = QWidget()
        second_layout = QHBoxLayout(self.second_frame)
        second_layout.setContentsMargins(0, 0, 0, 0)
        
        self.second_dot = QLabel("●")
        self.second_dot.setStyleSheet("color: #ff3355; font-size: 10px;")
        self.second_text = QLabel(self.labels[1])
        self.second_text.setStyleSheet("color: #ff3355; font-size: 11px; font-family: Consolas;")
        second_layout.addWidget(self.second_dot)
        second_layout.addWidget(self.second_text)
        layout.addWidget(self.second_frame)
        
        layout.addStretch()
        self.setStyleSheet("background-color: transparent;")
    
    def set_first_status(self, status: str) -> None:
        """Set first indicator status"""
        color = "#ff3355"  # default: disconnected/error
        if status == "connected":
            color = "#00ffa2"
        elif status == "connecting":
            color = "#fffa00"
        
        self.first_dot.setStyleSheet(f"color: {color}; font-size: 10px;")
        self.first_text.setStyleSheet(f"color: {color}; font-size: 11px; font-family: Consolas;")
    
    def set_second_status(self, status: str) -> None:
        """Set second indicator status"""
        color = "#ff3355"  # default: disconnected/error
        if status == "connected":
            color = "#00ffa2"
        elif status == "connecting":
            color = "#fffa00"
        
        self.second_dot.setStyleSheet(f"color: {color}; font-size: 10px;")
        self.second_text.setStyleSheet(f"color: {color}; font-size: 11px; font-family: Consolas;")