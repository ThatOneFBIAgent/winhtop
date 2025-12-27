# Clone WinHtop
git clone https://github.com/ThatOneFBIAgent/winhtop.git
Set-Location winhtop

# Install Python dependencies
pip install psutil

# Create install directory
$install = "$env:LOCALAPPDATA\Programs\WinHtop"
mkdir $install -Force | Out-Null

# Copy entry script and modules folder
Copy-Item .\task_manager.py "$install\winhtop.py" -Force
Copy-Item .\modules "$install\modules" -Recurse -Force

# Create CLI launcher
Set-Content "$install\winhtop.cmd" '@echo off
python "%LOCALAPPDATA%\Programs\WinHtop\winhtop.py" %*'

# Add to USER PATH if not already present
$p = [Environment]::GetEnvironmentVariable("Path","User")
if ($p -notlike "*$install*") {
  [Environment]::SetEnvironmentVariable("Path", "$p;$install", "User")
}

Write-Host "`nWinHtop installed! Open a NEW terminal and run:`n"
Write-Host "    winhtop" -ForegroundColor Green
