# Creates a pinnable Windows shortcut for Claude Dispatch Hub.
#
# The app's config and package resolution are relative to the working
# directory, so the shortcut sets "Start in" to the project root. That lets
# you launch from the taskbar without cd-ing anywhere first.
#
# Run:   powershell -ExecutionPolicy Bypass -File scripts\create-shortcut.ps1
# Then:  right-click the generated .lnk -> (Show more options) -> Pin to taskbar
#        (or drag it onto the taskbar).

$ErrorActionPreference = 'Stop'

# Project root = parent of this script's folder (scripts\ -> root)
$projectRoot = Split-Path -Parent $PSScriptRoot

# Prefer the known interpreter, fall back to whatever 'python' resolves to.
$python = 'C:\Python314\python.exe'
if (-not (Test-Path $python)) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $cmd) { $python = $cmd.Source }
    else { throw "Could not find python (looked for C:\Python314\python.exe and PATH)." }
}

$psExe   = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$lnkPath = Join-Path $projectRoot 'Claude Dispatch Hub.lnk'

# -Command body: run the menu; if it exits non-zero, pause so the error is readable.
# Single-quoted format string keeps $LASTEXITCODE literal (PowerShell expands it at run time).
$inner = '& ''{0}'' -m dispatch_hub; if ($LASTEXITCODE -ne 0) {{ Read-Host ''Exited with an error - press Enter to close'' }}' -f $python
$arguments = '-NoLogo -ExecutionPolicy Bypass -Command "{0}"' -f $inner

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($lnkPath)
$sc.TargetPath       = $psExe
$sc.Arguments        = $arguments
$sc.WorkingDirectory = $projectRoot
$sc.WindowStyle      = 1
$sc.Description       = 'Claude Dispatch Hub - multi-agent Claude Code launcher'
$sc.IconLocation     = "$python,0"
$sc.Save()

Write-Host "Created shortcut:"
Write-Host "  $lnkPath"
Write-Host ""
Write-Host "To pin: right-click it -> (Show more options) -> Pin to taskbar, or drag it onto the taskbar."
