$install = "$env:LOCALAPPDATA\Programs\WinHtop"
$p = [Environment]::GetEnvironmentVariable("Path", "User")
$p = $p -replace ";$install", ""
[Environment]::SetEnvironmentVariable("Path", $p, "User")
Remove-Item $install -Recurse -Force
Write-Host "`nWinHtop uninstalled!`n"
