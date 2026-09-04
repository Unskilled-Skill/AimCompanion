param(
    [Parameter(Mandatory = $true)]
    [string]$PreviousInstaller,
    [Parameter(Mandatory = $true)]
    [string]$NewInstaller,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedVersion
)

$ErrorActionPreference = "Stop"
$ExpectedVersion = $ExpectedVersion.TrimStart('v', 'V')
$PreviousInstaller = (Resolve-Path -LiteralPath $PreviousInstaller).Path
$NewInstaller = (Resolve-Path -LiteralPath $NewInstaller).Path
$TempBase = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [IO.Path]::GetTempPath() }
$TempBase = [IO.Path]::GetFullPath($TempBase)
$SmokeRoot = [IO.Path]::GetFullPath(
    (Join-Path $TempBase ("AimCompanion-upgrade-" + [guid]::NewGuid().ToString("N")))
)
$InstallDir = Join-Path $SmokeRoot "app"
$TestLocalAppData = Join-Path $SmokeRoot "localappdata"
$Executable = Join-Path $InstallDir "AimCompanion.exe"

function Invoke-TestInstaller([string]$InstallerPath) {
    $process = Start-Process -FilePath $InstallerPath -ArgumentList @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/DIR=$InstallDir"
    ) -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Installer exited with code $($process.ExitCode): $InstallerPath"
    }
}

function Get-InstalledVersion {
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        throw "Installed executable was not created: $Executable"
    }
    return (Get-Item -LiteralPath $Executable).VersionInfo.ProductVersion
}

function Test-InstalledAppLaunch {
    $oldQtPlatform = $env:QT_QPA_PLATFORM
    $oldLocalAppData = $env:LOCALAPPDATA
    try {
        $env:QT_QPA_PLATFORM = "offscreen"
        $env:LOCALAPPDATA = $TestLocalAppData
        New-Item -ItemType Directory -Path $TestLocalAppData -Force | Out-Null
        $started = Start-Process -FilePath $Executable -WindowStyle Hidden -PassThru
        Start-Sleep -Seconds 5
        $matching = @(
            Get-Process -Name "AimCompanion" -ErrorAction SilentlyContinue |
                Where-Object { $_.Path -eq $Executable }
        )
        if ($matching.Count -eq 0 -and $started.HasExited -and $started.ExitCode -ne 0) {
            throw "Installed application exited with code $($started.ExitCode)"
        }
        $matching | Stop-Process -Force -ErrorAction SilentlyContinue
    }
    finally {
        $env:QT_QPA_PLATFORM = $oldQtPlatform
        $env:LOCALAPPDATA = $oldLocalAppData
    }
}

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
try {
    Invoke-TestInstaller $PreviousInstaller
    $previousVersion = Get-InstalledVersion
    if ($previousVersion -eq $ExpectedVersion) {
        throw "Previous installer unexpectedly has release version $ExpectedVersion"
    }
    Test-InstalledAppLaunch

    Invoke-TestInstaller $NewInstaller
    $installedVersion = Get-InstalledVersion
    if ($installedVersion -ne $ExpectedVersion) {
        throw "Upgrade produced version $installedVersion; expected $ExpectedVersion"
    }
    Test-InstalledAppLaunch
    Write-Output "Upgrade smoke passed: $previousVersion -> $installedVersion"
}
finally {
    $resolvedRoot = [IO.Path]::GetFullPath($SmokeRoot)
    $expectedPrefix = $TempBase.TrimEnd('\') + '\'
    if (
        $resolvedRoot.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Leaf $resolvedRoot).StartsWith("AimCompanion-upgrade-")
    ) {
        Remove-Item -LiteralPath $resolvedRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
