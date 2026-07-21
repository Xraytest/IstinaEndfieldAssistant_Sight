' =============================================================================
' IstinaEndfieldAssistant (IEA) - Silent Launcher
' =============================================================================
' 双击本文件即可静默启动 IEA GUI（不弹出任何命令行窗口）。
'
' 兼容两种目录布局：
'   1. 开发布局：本 VBS 位于仓库根目录，3rd-part/python/pythonw.exe 在同级
'   2. Release 布局：本 VBS 与 IstinaEndfieldAssistant/ 文件夹同级，
'      3rd-part/python/pythonw.exe 在 IstinaEndfieldAssistant/ 下
' =============================================================================

Option Explicit

Dim fso, shell
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

' 解析本 VBS 所在目录
Dim baseDir
baseDir = fso.GetParentFolderName(WScript.ScriptFullName)

' 自动识别布局：优先 release 布局（含 IstinaEndfieldAssistant 子文件夹），
' 不存在则回退到开发布局。
Dim appDir
Dim releaseSub
releaseSub = fso.BuildPath(baseDir, "IstinaEndfieldAssistant")
If fso.FolderExists(fso.BuildPath(releaseSub, "3rd-part")) Then
    appDir = releaseSub
Else
    appDir = baseDir
End If

' 构造 pythonw.exe 与 main.py 的绝对路径
Dim pythonExe, mainScript
pythonExe  = fso.BuildPath(appDir, "3rd-part\python\pythonw.exe")
mainScript = fso.BuildPath(appDir, "src\gui\pyqt6\main.py")

' 路径检查：缺失时弹窗提示，避免静默失败
If Not fso.FileExists(pythonExe) Then
    MsgBox "未找到内置 Python 解释器：" & vbCrLf & pythonExe & vbCrLf & vbCrLf & _
           "请确认 release 包完整或 3rd-part/python 已就位。", _
           vbCritical, "IEA 启动失败"
    WScript.Quit 1
End If

If Not fso.FileExists(mainScript) Then
    MsgBox "未找到 GUI 主程序入口：" & vbCrLf & mainScript, _
           vbCritical, "IEA 启动失败"
    WScript.Quit 1
End If

' 设置工作目录为应用根（main.py 内部基于 __file__ 推断 src/ 路径，
' 此处设置 cwd 仅为兼容可能存在的相对路径读取）
shell.CurrentDirectory = appDir

' 静默启动：第二参数 0 = 隐藏窗口；第三参数 False = 不等待子进程退出
' pythonw.exe 本身不创建控制台，配合 windowStyle=0 实现完全无窗口启动
On Error Resume Next
shell.Run """" & pythonExe & """ """ & mainScript & """", 0, False
If Err.Number <> 0 Then
    MsgBox "启动 IEA 时发生错误：" & vbCrLf & Err.Description, _
           vbCritical, "IEA 启动失败"
    WScript.Quit 1
End If
On Error GoTo 0
