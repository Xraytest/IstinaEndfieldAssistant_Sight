# 单步执行探索操作
$adb = "C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\adb\adb.exe"
$device = $env:IEA_DEVICE_SERIAL
if (-not $device) { $device = "localhost:16512" }
$cache = "C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\cache"

Write-Host "=== 探索游戏 ==="

# 第一步：先截图看看当前场景
Write-Host "1. 截图当前画面..."
& $adb -s $device exec-out screencap -p | Set-Content -Path "$cache\explore_current.png" -Encoding Byte

# 第二步：尝试向前移动（滑动手势）
Write-Host "2. 执行向前滑动..."
& $adb -s $device shell "input swipe 640 680 640 350 1200"

Start-Sleep -Seconds 3

# 第三步：再次截图
Write-Host "3. 再次截图..."
& $adb -s $device exec-out screencap -p | Set-Content -Path "$cache\explore_after.png" -Encoding Byte

# 第四步：尝试打开菜单或交互（轻触右上角区域）
Write-Host "4. 尝试交互..."
& $adb -s $device shell "input tap 1200 80"

Start-Sleep -Seconds 3

Write-Host "5. 最终截图..."
& $adb -s $device exec-out screencap -p | Set-Content -Path "$cache\explore_final.png" -Encoding Byte

Write-Host "=== 探索操作完成 ==="