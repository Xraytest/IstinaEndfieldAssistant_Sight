#!/usr/bin/env python3
import sys
sys.path.insert(0, 'C:\\Users\\cheng\\Documents\\ArkStudio\\IstinaAI\\IstinaEndfieldAssistant_Sight\\src')
from adbutils import Network
print('Type:', type(Network))
print('LOCAL_ABSTRACT:', Network.LOCAL_ABSTRACT)
print('Type of LOCAL_ABSTRACT:', type(Network.LOCAL_ABSTRACT))
print('UNIX:', Network.UNIX)
print('LOCAL_ABSTRACT == 1:', Network.LOCAL_ABSTRACT == 1)
print('1 in [Network.UNIX, Network.LOCAL_ABSTRACT]:', 1 in [Network.UNIX, Network.LOCAL_ABSTRACT])
