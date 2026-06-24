"""
Page component module - 本地版
"""

from .auth_page import AuthPage
from .settings_page import SettingsPage
from .device_settings_page import DeviceSettingsPage
from .agent_page import AgentPage
from .model_manager_page import ModelManagerPage
from .standard_reasoning_page import StandardReasoningPage
from .prts_full_intelligence_page import PrtsFullIntelligencePage
from .iea_page import IeaPage


__all__ = [
    'AuthPage',
    'SettingsPage',
    'DeviceSettingsPage',
    'AgentPage',
    'ModelManagerPage',
    'StandardReasoningPage',
    'PrtsFullIntelligencePage',
    'IeaPage',
]
