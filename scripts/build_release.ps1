$ErrorActionPreference = "Stop"
$ReleaseRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ReleaseRoot

$env:QT_QPA_PLATFORM = "offscreen"

function Invoke-Checked {
    param([Parameter(Mandatory)][scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Release command failed with exit code ${LASTEXITCODE}: $Command"
    }
}

$TestTemp = Join-Path $ReleaseRoot (
    "artifacts\release-tests-" + [guid]::NewGuid().ToString("N")
)
Invoke-Checked { python scripts/build_icon.py }
Invoke-Checked { python -m compileall -q core models ui tests scripts }
Invoke-Checked { python -m pytest -q --basetemp $TestTemp }
Invoke-Checked { python scripts/smoke_ui.py }
Invoke-Checked { python -m PyInstaller --clean --noconfirm AimCompanion.spec }

$InnoCandidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$InnoCompiler = $InnoCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $InnoCompiler) {
    throw "Inno Setup 6 is required. Install it with: winget install JRSoftware.InnoSetup"
}
Invoke-Checked { & $InnoCompiler installer.iss }

$Installer = Join-Path $ReleaseRoot "dist\AimCompanion-Setup.exe"
$ChecksumFile = "$Installer.sha256"
$Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Installer).Hash.ToLowerInvariant()
Set-Content -LiteralPath $ChecksumFile -Value "$Hash  AimCompanion-Setup.exe" -Encoding ascii

Get-Item -LiteralPath "dist\AimCompanion.exe", $Installer, $ChecksumFile |
    Select-Object Name, Length, LastWriteTime
