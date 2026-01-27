; =========================================================
; WinHtop Installer
; =========================================================

#define MyAppName "WinHtop"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "Iza Carlos"
#define MyAppExeName "winhtop.exe"
#define MyAppId "C6E2A3B4-D1F2-4EBA-BD3F-6A7C10B7B7C2"

[Setup]
AppId={{{#MyAppId}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
UsePreviousAppDir=yes

ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

PrivilegesRequired=none
CloseApplications=force

Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

SetupIconFile=assets\winhtop.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
ChangesEnvironment=yes
OutputBaseFilename=WinHtopInstaller

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "addpath"; Description: "Add to PATH (Recommended)"; Flags: checkedonce
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[UninstallDelete]
Type: files; Name: "{app}\*.conf"
Type: files; Name: "{app}\*.log"
Type: dirifempty; Name: "{app}"

[Code]
function GetInstalledUninstaller(): string;
var
  Key: string;
begin
  Key := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\' +
         '{C6E2A3B4-D1F2-4EBA-BD3F-6A7C10B7B7C2}_is1';

  if RegQueryStringValue(
       HKLM,
       Key,
       'UninstallString',
       Result
     ) then
    exit;

  Result := '';
end;

function InitializeSetup(): Boolean;
var
  Uninstaller: string;
  Choice: Integer;
  ResultCode: Integer;
begin
  Result := True;

  Uninstaller := GetInstalledUninstaller();

  if Uninstaller <> '' then
  begin
    Choice := MsgBox(
      'WinHtop is already installed.'#13#13 +
      'Yes  = uninstall current version'#13 +
      'No   = open maintenance mode',
      mbConfirmation,
      MB_YESNO
    );

    if Choice = IDYES then
    begin
      Exec(
        RemoveQuotes(Uninstaller),
        '',
        '',
        SW_SHOWNORMAL,
        ewWaitUntilTerminated,
        ResultCode
      );

      MsgBox(
        'Uninstall complete. Please run the installer again to reinstall.',
        mbInformation,
        MB_OK
      );

      Result := False;
      exit;
    end;

    { NO means maintenance mode, let Inno continue naturally }
  end;
end;
