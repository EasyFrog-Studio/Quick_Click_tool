$ErrorActionPreference = 'Stop'

$quickClick = $PSScriptRoot
$toolRoot = Join-Path $quickClick 'package_tool'
$outputDir = Join-Path $toolRoot 'Quick_Click'
$shortcutPath = Join-Path $toolRoot 'Quick_Click.lnk'
$buildDir = Join-Path $quickClick 'build'
$python = Join-Path $quickClick '.venv\Scripts\python.exe'
$entry = Join-Path $quickClick 'app.py'

# stale output from a previous build must not be mistaken for a fresh one
if (Test-Path $outputDir) { Remove-Item $outputDir -Recurse -Force }
if (Test-Path $shortcutPath) { Remove-Item $shortcutPath -Force }

& $python -m PyInstaller --noconfirm --clean --onedir --noconsole --name Quick_Click --collect-data customtkinter --distpath $toolRoot --workpath $buildDir --specpath $buildDir $entry
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$exePath = Join-Path $outputDir 'Quick_Click.exe'
if (-not (Test-Path $exePath)) {
    throw "Build reported success but $exePath is missing"
}

# relative Arguments survive moving package_tool only when the launcher's working directory is the .lnk folder
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "$env:windir\explorer.exe"
$shortcut.Arguments = 'Quick_Click\Quick_Click.exe'
$shortcut.WorkingDirectory = ''
$shortcut.IconLocation = "$exePath,0"
$shortcut.Description = '快速連點器'
$shortcut.Save()

Write-Host "Output folder: $outputDir"
Write-Host "Shortcut: $shortcutPath"
