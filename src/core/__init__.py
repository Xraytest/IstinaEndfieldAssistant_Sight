"""安卓核心模块 — 三层架构

- foundation: 基础层（无内部依赖的底层模块）
- capability: 能力层（可独立使用的功能模块）
- service: 服务层（组合能力层模块实现业务逻辑）
"""

from .foundation import *
from .capability import *
from .service import *