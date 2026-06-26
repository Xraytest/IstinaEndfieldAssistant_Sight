#!/usr/bin/env python3
with open(r'C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\scrcpy\scrcpy-server-v4.0', 'rb') as f:
    header = f.read(20)
    print('Header bytes:', header)
    print('Header hex:', header.hex())
    if header[:2] == b'PK':
        print('This is a ZIP/JAR file')
    elif header[:4] == b'dex\n':
        print('This is a DEX file')
    else:
        print('Unknown file type')
