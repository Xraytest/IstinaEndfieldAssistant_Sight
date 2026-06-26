#!/usr/bin/env python3
import zipfile
z = zipfile.ZipFile(r'C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\scrcpy\scrcpy-server-v4.0')
print('Files in JAR:')
for info in z.infolist():
    print(f'  {info.filename}: {info.file_size} bytes')
