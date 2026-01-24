# =========================================================
# WinHtop PowerShell Installer (v0.5)
# Replicates Winhtop-installer.iss behavior
# Runs at lowest authority (User scope)
# =========================================================

$AppName = "WinHtop"
$ExeName = "winhtop.exe"
$SourceDir = "$PSScriptRoot\dist"
# Match ISS: {localappdata}\Programs\{#MyAppName}
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\$AppName"

# 1. Create Installation Directory
if (!(Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    Write-Host "Creating directory: $InstallDir" -ForegroundColor Cyan
}

# 2. Copy Files
Write-Host "Copying files..." -ForegroundColor Cyan
if (Test-Path "$SourceDir\$ExeName") {
    Copy-Item -Path "$SourceDir\$ExeName" -Destination $InstallDir -Force
}
else {
    Write-Error "Could not find $SourceDir\$ExeName. Please build the project first."
    return
}

# 3. Add to User PATH
Write-Host "Updating User PATH..." -ForegroundColor Cyan
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$PathParts = $UserPath -split ";" | Where-Object { $_ -ne "" }

if ($PathParts -notcontains $InstallDir) {
    $NewPath = ($PathParts + $InstallDir) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    
    # Refresh environment (WM_SETTINGCHANGE)
    $Signature = @'
[DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
public static extern IntPtr SendMessageTimeout(
    IntPtr hWnd, uint Msg, IntPtr wParam, string lParam, 
    uint fuFlags, uint uTimeout, out IntPtr lpdwResult);
'@
    try {
        $Win32 = Add-Type -MemberDefinition $Signature -Name "Win32Environment" -Namespace "Win32" -PassThru -ErrorAction SilentlyContinue
        if ($Win32) {
            $result = [IntPtr]::Zero
            $Win32::SendMessageTimeout([IntPtr]0xffff, 0x001A, [IntPtr]::Zero, "Environment", 0x0002, 5000, [ref]$result) | Out-Null
        }
    }
    catch {
        # Fallback to.. something
        # TODO: add "something"
    }
    
    Write-Host "Added $AppName to User PATH and refreshed environment." -ForegroundColor Green
}

# 4. Create Shortcuts (Matches ISS {group}\{#MyAppName})
$WshShell = New-Object -ComObject WScript.Shell

# Start Menu Shortcut Folder
$StartMenuDir = Join-Path ([Environment]::GetFolderPath("Programs")) $AppName
if (!(Test-Path $StartMenuDir)) {
    New-Item -ItemType Directory -Path $StartMenuDir -Force | Out-Null
}

$Shortcuts = @(
    (Join-Path $StartMenuDir "$AppName.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "$AppName.lnk")
)

foreach ($Path in $Shortcuts) {
    $Shortcut = $WshShell.CreateShortcut($Path)
    $Shortcut.TargetPath = Join-Path $InstallDir $ExeName
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.Save()
    Write-Host "Created shortcut: $Path" -ForegroundColor Yellow
}

Write-Host "`nInstallation Complete! '$AppName' is now in your PATH." -ForegroundColor Green