#!/usr/bin/env python3
import zipfile
z = zipfile.ZipFile(r'C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\scrcpy\scrcpy-server.jar')
print('Files in JAR:')
for info in z.infolist():
    print(f'  {info.filename}: {info.file_size} bytes (compressed: {info.compress_size} bytes)')
print(f'Total uncompressed: {sum(info.file_size for info in z.infolist())} bytes')
