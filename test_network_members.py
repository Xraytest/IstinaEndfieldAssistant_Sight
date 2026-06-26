#!/usr/bin/env python3
import sys
sys.path.insert(0, 'C:\\Users\\cheng\\Documents\\ArkStudio\\IstinaAI\\IstinaEndfieldAssistant_Sight\\src')
from adbutils import Network
for member in Network:
    print(f'{member.name}: {member.value}')
