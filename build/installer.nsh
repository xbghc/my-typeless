; NSIS 自定义脚本。electron-builder NSIS 已内置“安装/卸载前检测并关闭运行实例”。
; 这里额外清理旧 Python (Inno Setup) 版本遗留的开机自启注册表值。
!macro customInstall
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "MyTypeless"
!macroend
