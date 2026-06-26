@echo off
cd /d "C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight"
.\3rd-part\adb\adb.exe -s 192.168.1.12:16512 shell "CLASSPATH=/data/local/tmp/scrcpy-server.jar app_process / com.genymobile.scrcpy.Server 4.0 tunnel_forward=true video=true control=false"
