# =========================================================
# WinHtop PowerShell Project Builder (v1 and onwards)
# =========================================================
$scriptDir = Split-Path -Parent
$MyInvocation.MyCommand.Path
$targetDir = Join-path $scriptDir "winhtop"

$repoUrl = "https://github.com/ThatOneFBIAgent/winhtop.git"

# Check for PyInstaller
if (!(Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Error "PyInstaller not found. Please run: pip install pyinstaller sounddevice numpy psutil"
    return
}

if (-not (Test-Path $targetDir)) {
    Write-Host "winhtop not found. Cloning repo"
    git clone $repoUrl $targetDir

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to clone repo. Please check your internet connection and try again."
        return
    }
}
else {
    Write-Host "winhtop found."
}

Set-Location $targetDir


Write-Host "Building WinHtop EXE..." -ForegroundColor Cyan

# --collect-all is mandatory for sounddevice to bundle the PortAudio DLLs.
# We remove numpy collection because PyInstaller's built-in hooks handle it 
# much more efficiently without bundling every single test and doc file.
pyinstaller --onefile `
    --name winhtop `
    --icon="assets\winhtop.ico" `
    --collect-all sounddevice `
    --hidden-import sounddevice `
    task_manager.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nBuild Successful! The EXE is in the 'dist' folder." -ForegroundColor Green
    Write-Host "You can now run .\install.ps1 to update your installation/path." -ForegroundColor Yellow
}
else {
    Write-Error "Build failed with exit code $LASTEXITCODE"
}