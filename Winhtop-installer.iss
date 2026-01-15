; =========================================================
; WinHtop Installer (v0.5)
; Optimized for Inno Setup 6.6.1+
; =========================================================

#define MyAppName "WinHtop"
#define MyAppVersion "0.5"
#define MyAppPublisher "Iza Carlos"
#define MyAppExeName "winhtop.exe"

[Setup]
; --- Unique Identity ---
AppId={{C6E2A3B4-D1F2-4EBA-BD3F-6A7C10B7B7C2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}

; --- UI and Logic ---
WizardStyle=modern
SetupIconFile=assets\winhtop.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=lowest
CloseApplications=force

; --- The "Professional" Refresh Flag ---
; This handles the environment refresh automatically at the end of installation
ChangesEnvironment=yes

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

[Code]
// ============================================================================
// WINDOWS API DECLARATIONS
// ============================================================================
type
  LongPtr = LongInt;

const
  // HWND_BROADCAST is already defined by Inno Setup, so we don't list it here.
  WM_SETTINGCHANGE = $001A;
  SMTO_ABORTIFHUNG = $0002;

// We only need to declare the function itself. 
// Inno Setup 6.x already knows types like HWND, UINT, and LongInt.
function SendMessageTimeout(hWnd: HWND; Msg: UINT; wParam: LongPtr; lParam: String; fuFlags: UINT; uTimeout: UINT; var lpdwResult: LongPtr): LongInt;
  external 'SendMessageTimeoutW@user32.dll stdcall';

// ============================================================================
// PATH MANIPULATION LOGIC
// ============================================================================

procedure RefreshEnvironment();
var
  MsgResult: LongPtr;
begin
  // We use the built-in HWND_BROADCAST constant here
  SendMessageTimeout(HWND_BROADCAST, WM_SETTINGCHANGE, 0, 'Environment', SMTO_ABORTIFHUNG, 5000, MsgResult);
end;

procedure UpdatePath(PathToAdd: string);
var
  OldPath: string;
  NewPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OldPath) then
    OldPath := '';

  if Pos(Uppercase(PathToAdd), Uppercase(OldPath)) = 0 then
  begin
    NewPath := OldPath;
    if (NewPath <> '') and (NewPath[Length(NewPath)] <> ';') then
      NewPath := NewPath + ';';
    NewPath := NewPath + PathToAdd;

    if RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', NewPath) then
      RefreshEnvironment();
  end;
end;

procedure RemovePath(PathToRemove: string);
var
  OldPath: string;
  NewPath: string;
  P: Integer;
begin
  if RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OldPath) then
  begin
    P := Pos(Uppercase(PathToRemove), Uppercase(OldPath));
    if P > 0 then
    begin
      NewPath := OldPath;
      Delete(NewPath, P, Length(PathToRemove));
      
      StringChangeEx(NewPath, ';;', ';', True);
      if (Length(NewPath) > 0) and (NewPath[Length(NewPath)] = ';') then
        Delete(NewPath, Length(NewPath), 1);
      if (Length(NewPath) > 0) and (NewPath[1] = ';') then
        Delete(NewPath, 1, 1);

      if RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', NewPath) then
        RefreshEnvironment();
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('addpath') then
    UpdatePath(ExpandConstant('{app}'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RemovePath(ExpandConstant('{app}'));
end;