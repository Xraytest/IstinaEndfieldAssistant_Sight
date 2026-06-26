#!/usr/bin/env python3
import sys
sys.path.insert(0, 'C:\\Users\\cheng\\Documents\\ArkStudio\\IstinaAI\\IstinaEndfieldAssistant_Sight\\src')
from adbutils import Network
print('LOCAL_ABSTRACT:', Network.LOCAL_ABSTRACT)
print('LOCAL_TCP:', Network.LOCAL_TCP)
print('LOCAL_UDP:', Network.LOCAL_UDP)
for attr in dir(Network):
    if not attr.startswith('_'):
        print(f'{attr}: {getattr(Network, attr)}')
