#!/usr/bin/env python3
import zipfile
z = zipfile.ZipFile(r'C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\scrcpy\scrcpy-server.jar')
for name in z.namelist():
    if name.endswith('.dex'):
        print('DEX file:', name)
        data = z.read(name)
        print('DEX magic:', data[:8])
        print('DEX size:', len(data))
