# =========================================================
# WinHtop PowerShell Uninstaller (v0.5)
# Replicates Winhtop-installer.iss behavior
# =========================================================

$AppName = "WinHtop"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\$AppName"

Write-Host "Uninstalling $AppName..." -ForegroundColor Cyan

# 1. Remove Shortcuts
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$StartMenuDir = Join-Path ([Environment]::GetFolderPath("Programs")) $AppName

$Shortcuts = @(
    (Join-Path $DesktopPath "$AppName.lnk"),
    (Join-Path $StartMenuDir "$AppName.lnk")
)

foreach ($Path in $Shortcuts) {
    if (Test-Path $Path) {
        Remove-Item $Path -Force
        Write-Host "Removed shortcut: $Path" -ForegroundColor Yellow
    }
}

# Remove Start Menu directory if empty
if (Test-Path $StartMenuDir) {
    $Files = Get-ChildItem -Path $StartMenuDir
    if ($Files.Count -eq 0) {
        Remove-Item $StartMenuDir -Force
        Write-Host "Removed Start Menu directory: $StartMenuDir" -ForegroundColor Yellow
    }
}

# 2. Remove from User PATH
Write-Host "Removing from User PATH..." -ForegroundColor Cyan
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$PathParts = $UserPath -split ";" | Where-Object { $_ -ne "" -and $_ -ne $InstallDir }

$NewPath = $PathParts -join ";"
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
catch {}

Write-Host "Removed $AppName from User PATH." -ForegroundColor Green

# 3. Remove Files
if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
    Write-Host "Removed installation files from $InstallDir" -ForegroundColor Yellow
}

Write-Host "`nUninstallation Complete." -ForegroundColor Green