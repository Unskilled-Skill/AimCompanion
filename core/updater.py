import hashlib
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from core.version import GITHUB_REPOSITORY, VERSION


API_URL = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
USER_AGENT = f"AimCompanion/{VERSION}"
INSTALLER_ASSET = "AimCompanion-Setup.exe"
CHECKSUM_ASSET = f"{INSTALLER_ASSET}.sha256"


class UpdateError(RuntimeError):
    pass


def version_tuple(value: str) -> tuple[int, int, int]:
    numbers = [int(part) for part in re.findall(r"\d+", value)[:3]]
    return tuple((numbers + [0, 0, 0])[:3])


def is_newer_version(candidate: str, current: str = VERSION) -> bool:
    return version_tuple(candidate) > version_tuple(current)


def parse_release(payload: dict) -> dict:
    version = str(payload.get("tag_name", "")).lstrip("vV")
    if not version:
        raise UpdateError("The latest GitHub release has no version tag.")
    assets = payload.get("assets") or []
    installer = next(
        (asset for asset in assets if asset.get("name") == INSTALLER_ASSET),
        None,
    )
    checksum = next(
        (asset for asset in assets if asset.get("name") == CHECKSUM_ASSET),
        None,
    )
    if not installer:
        raise UpdateError("The latest release does not contain the Windows installer.")
    digest = installer.get("digest") or ""
    expected_hash = digest.split(":", 1)[1] if digest.startswith("sha256:") else None
    return {
        "version": version,
        "name": payload.get("name") or f"Aim Companion {version}",
        "notes": payload.get("body") or "",
        "page_url": payload.get("html_url") or "",
        "download_url": installer["browser_download_url"],
        "checksum_url": checksum.get("browser_download_url") if checksum else None,
        "expected_hash": expected_hash,
    }


def _request(url: str, timeout: int = 12):
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
    )
    return urllib.request.urlopen(request, timeout=timeout)


def get_latest_release() -> dict:
    try:
        with _request(API_URL) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        raise UpdateError(f"Could not check GitHub Releases: {error}") from error
    return parse_release(payload)


def _fetch_checksum(release: dict) -> str:
    if release.get("expected_hash"):
        return release["expected_hash"].lower()
    if not release.get("checksum_url"):
        raise UpdateError("The update has no SHA-256 checksum and was rejected.")
    try:
        with _request(release["checksum_url"]) as response:
            checksum = response.read().decode("ascii", errors="strict").split()[0]
    except Exception as error:
        raise UpdateError(f"Could not verify the update checksum: {error}") from error
    if not re.fullmatch(r"[0-9a-fA-F]{64}", checksum):
        raise UpdateError("The published update checksum is invalid.")
    return checksum.lower()


def download_release(release: dict, interrupted=None) -> str:
    expected_hash = _fetch_checksum(release)
    destination = Path(tempfile.gettempdir()) / (
        f"AimCompanion-{release['version']}-Setup.exe"
    )
    digest = hashlib.sha256()
    try:
        with _request(release["download_url"], timeout=20) as response:
            with destination.open("wb") as output:
                while True:
                    if interrupted and interrupted():
                        raise UpdateError("Update download cancelled.")
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    digest.update(chunk)
    except UpdateError:
        destination.unlink(missing_ok=True)
        raise
    except Exception as error:
        destination.unlink(missing_ok=True)
        raise UpdateError(f"Could not download the update: {error}") from error
    if digest.hexdigest().lower() != expected_hash:
        destination.unlink(missing_ok=True)
        raise UpdateError("The downloaded update failed SHA-256 verification.")
    return str(destination)


def _powershell_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _delayed_installer_script(installer: Path, target: Path) -> str:
    """Wait for the one-file bootloader to release the app before updating."""
    installer_literal = _powershell_literal(str(installer))
    target_literal = _powershell_literal(str(target))
    process_name_literal = _powershell_literal(target.stem)
    return f"""
$installerPath = {installer_literal}
$targetPath = {target_literal}
$processName = {process_name_literal}
$deadline = (Get-Date).AddSeconds(60)
do {{
    $running = @(
        Get-Process -Name $processName -ErrorAction SilentlyContinue |
            Where-Object {{ $_.Path -eq $targetPath }}
    )
    if ($running.Count -eq 0) {{ break }}
    Start-Sleep -Milliseconds 250
}} while ((Get-Date) -lt $deadline)
if ($running.Count -ne 0) {{ exit 2 }}
$setup = Start-Process -FilePath $installerPath -ArgumentList @(
    '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'
) -WindowStyle Hidden -Wait -PassThru
if ($setup.ExitCode -ne 0) {{ exit $setup.ExitCode }}
if (Test-Path -LiteralPath $targetPath) {{
    Start-Process -FilePath $targetPath
}}
""".strip()


def launch_installer(path: str):
    installer = Path(path).resolve()
    if not installer.is_file() or installer.suffix.casefold() != ".exe":
        raise UpdateError("The verified Windows installer could not be found.")
    target = Path(sys.executable).resolve()
    script = _delayed_installer_script(installer, target)
    encoded_script = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    subprocess.Popen(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-WindowStyle", "Hidden", "-EncodedCommand", encoded_script,
        ],
        cwd=str(installer.parent),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def automatic_updates_supported() -> bool:
    return os.name == "nt" and bool(getattr(sys, "frozen", False))


class UpdateCheckWorker(QThread):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def run(self):
        try:
            self.completed.emit(get_latest_release())
        except Exception as error:
            self.failed.emit(str(error))


class UpdateDownloadWorker(QThread):
    completed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, release: dict, parent=None):
        super().__init__(parent)
        self.release = release

    def run(self):
        try:
            path = download_release(self.release, self.isInterruptionRequested)
            self.completed.emit(path)
        except Exception as error:
            self.failed.emit(str(error))
