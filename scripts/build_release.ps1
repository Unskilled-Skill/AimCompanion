$ErrorActionPreference = "Stop"
$ReleaseRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ReleaseRoot

$env:QT_QPA_PLATFORM = "offscreen"
python scripts/build_icon.py
python -m compileall -q core models ui tests scripts
python -m pytest -q
python scripts/smoke_ui.py
python -m PyInstaller --clean --noconfirm AimCompanion.spec

$InnoCandidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$InnoCompiler = $InnoCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $InnoCompiler) {
    throw "Inno Setup 6 is required. Install it with: winget install JRSoftware.InnoSetup"
}
& $InnoCompiler installer.iss

$Installer = Join-Path $ReleaseRoot "dist\AimCompanion-Setup.exe"
$ChecksumFile = "$Installer.sha256"
$Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Installer).Hash.ToLowerInvariant()
Set-Content -LiteralPath $ChecksumFile -Value "$Hash  AimCompanion-Setup.exe" -Encoding ascii

Get-Item -LiteralPath "dist\AimCompanion.exe", $Installer, $ChecksumFile |
    Select-Object Name, Length, LastWriteTime
