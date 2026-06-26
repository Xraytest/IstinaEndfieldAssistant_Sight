#!/usr/bin/env python3
import zipfile
z = zipfile.ZipFile(r'C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\scrcpy\scrcpy-server.jar')
print('AndroidManifest.xml (first 2000 chars):')
print(z.read('AndroidManifest.xml').decode('utf-8', errors='ignore')[:2000])
