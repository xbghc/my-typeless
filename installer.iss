; Inno Setup Script for My Typeless
; 编译: iscc installer.iss
; 版本号由 CI 通过 /D 参数传入

#ifndef APP_VERSION
  #define APP_VERSION "1.0.0"
#endif

[Setup]
AppId={{E8B7F3A1-5C2D-4A9E-B6D8-3F1E7A2C9D04}
AppName=My Typeless
AppVersion={#APP_VERSION}
AppVerName=My Typeless v{#APP_VERSION}
AppPublisher=xbghc
AppPublisherURL=https://github.com/xbghc/my-typeless
AppSupportURL=https://github.com/xbghc/my-typeless/issues
DefaultDirName={autopf}\MyTypeless
DefaultGroupName=My Typeless
OutputDir=dist
OutputBaseFilename=MyTypeless-Setup
Compression=lzma2/ultra64
SolidCompression=yes
SetupIconFile=src\my_typeless\resources\app_icon.ico
UninstallDisplayIcon={app}\MyTypeless.exe
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 允许覆盖安装（升级）
UsePreviousAppDir=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Launch at startup"; GroupDescription: "Other options:"

[Files]
Source: "dist\MyTypeless.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\My Typeless"; Filename: "{app}\MyTypeless.exe"
Name: "{group}\Uninstall My Typeless"; Filename: "{uninstallexe}"
Name: "{autodesktop}\My Typeless"; Filename: "{app}\MyTypeless.exe"; Tasks: desktopicon

[Registry]
; 开机自启（仅当用户勾选时）
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "MyTypeless"; ValueData: """{app}\MyTypeless.exe"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\MyTypeless.exe"; Description: "Launch My Typeless"; Flags: nowait postinstall skipifsilent
