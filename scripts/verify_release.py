"""Verify that a GitHub release satisfies the Aim Companion updater contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1]))

from core.updater import CHECKSUM_ASSET, INSTALLER_ASSET, parse_release
from core.version import VERSION


class ReleaseVerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class VerificationReport:
    tag: str
    asset_names: frozenset[str]
    checksum_matches: bool
    updater_selected_version: str
    download_size: int


def verify_release_payload(payload, installer_bytes, checksum_text, expected_version=VERSION):
    tag = str(payload.get("tag_name", ""))
    if tag.lstrip("vV") != expected_version:
        raise ReleaseVerificationError(
            f"release tag {tag!r} does not match application {expected_version}"
        )
    names = frozenset(asset.get("name", "") for asset in payload.get("assets", ()))
    if INSTALLER_ASSET not in names:
        raise ReleaseVerificationError("installer asset is missing")
    if CHECKSUM_ASSET not in names:
        raise ReleaseVerificationError("checksum asset is missing")
    if not installer_bytes:
        raise ReleaseVerificationError("installer asset is empty")
    match = re.match(r"\s*([0-9a-fA-F]{64})\b", checksum_text)
    if not match:
        raise ReleaseVerificationError("checksum asset is invalid")
    actual = hashlib.sha256(installer_bytes).hexdigest()
    if actual.casefold() != match.group(1).casefold():
        raise ReleaseVerificationError("installer checksum does not match")
    selected = parse_release(payload)
    return VerificationReport(
        tag=tag,
        asset_names=names,
        checksum_matches=True,
        updater_selected_version=selected["version"],
        download_size=len(installer_bytes),
    )


def _get_json(url):
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json", "User-Agent": f"AimCompanion/{VERSION}",
    })
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read(8_000_001).decode("utf-8"))


def _get_bytes(url, limit=250_000_000):
    request = urllib.request.Request(url, headers={"User-Agent": f"AimCompanion/{VERSION}"})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(limit + 1)
    if len(body) > limit:
        raise ReleaseVerificationError("release asset exceeds size limit")
    return body


def verify_release(repository, tag):
    payload = _get_json(f"https://api.github.com/repos/{repository}/releases/tags/{tag}")
    assets = {asset["name"]: asset for asset in payload.get("assets", ())}
    try:
        installer = _get_bytes(assets[INSTALLER_ASSET]["browser_download_url"])
        checksum = _get_bytes(
            assets[CHECKSUM_ASSET]["browser_download_url"], limit=4096,
        ).decode("ascii")
    except KeyError as error:
        raise ReleaseVerificationError(f"required release asset is missing: {error}") from error
    return verify_release_payload(payload, installer, checksum)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    report = verify_release(args.repository, args.tag)
    print(json.dumps({
        "tag": report.tag,
        "assets": sorted(report.asset_names),
        "checksum_matches": report.checksum_matches,
        "updater_selected_version": report.updater_selected_version,
        "download_size": report.download_size,
    }, indent=2))


if __name__ == "__main__":
    main()
