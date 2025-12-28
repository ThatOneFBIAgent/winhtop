; ================================
; WinHtop Installer (Inno 6.x)
; ================================

[Setup]
AppName=WinHtop
AppVersion=0.5
AppPublisher=Iza Carlos
DefaultDirName={localappdata}\Programs\WinHtop
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename=WinHtop-Setup
Compression=lzma
SolidCompression=yes
UninstallDisplayIcon={app}\winhtop.exe
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force
UsePreviousAppDir=yes
VersionInfoDescription=WinHtop Installer
VersionInfoVersion=1.0.0.0
VersionInfoCompany=WinHtop Project
VersionInfoProductName=WinHtop
VersionInfoProductVersion=1.0

; Installer icon + EXE meta
SetupIconFile=assets\winhtop.ico

[Files]
Source: "dist\winhtop.exe"; DestDir: "{app}"; Flags: ignoreversion

[Tasks]
Name: "addpath"; Description: "Add WinHtop to PATH (recommended)"; Flags: unchecked
Name: "desktopicon"; Description: "Create Desktop Shortcut"; Flags: unchecked

[Icons]
Name: "{userstartmenu}\WinHtop"; Filename: "{app}\winhtop.exe"
Name: "{userdesktop}\WinHtop"; Filename: "{app}\winhtop.exe"; Tasks: desktopicon

; Optional Win+X (Power Menu) entry
; Comment out if you don't want this behavior
; Name: "{userappdata}\Microsoft\Windows\WinX\Group3\WinHtop.lnk"; Filename: "{app}\winhtop.exe"; Flags: createonlyiffileexists

[Run]
; Add PATH entry (user-scope) if task selected
Filename: "{cmd}"; \
Parameters: "/C setx PATH ""%PATH%;{app}"""; \
Flags: runhidden; Tasks: addpath

; Refresh runtime PATH so new shells see it immediately
Filename: "{cmd}"; \
Parameters: "/C powershell -command ""$p=[Environment]::GetEnvironmentVariable('Path','User'); if(-not($p.Contains('{app}'))) [Environment]::SetEnvironmentVariable('Path',$p+';{app}','User')"""; \
Flags: runhidden; Tasks: addpath

[UninstallRun]
; Remove PATH entry on uninstall (only user scope)
Filename: "{cmd}"; \
Parameters: "/C powershell -command ""$p=[Environment]::GetEnvironmentVariable('Path','User'); $np=$p -replace ';{app}',''; [Environment]::SetEnvironmentVariable('Path',$np,'User')"""; \
Flags: runhidden; \
RunOnceId: "RemoveUserPathWinHtop"
