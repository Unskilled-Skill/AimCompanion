import hashlib
import os
from unittest.mock import patch

import pytest

from scripts.verify_release import (
    ReleaseVerificationError, _get_json, verify_release_payload,
)


def _release(include_checksum=True):
    assets = [{
        "name": "AimCompanion-Setup.exe",
        "browser_download_url": "https://example.test/setup.exe",
    }]
    if include_checksum:
        assets.append({
            "name": "AimCompanion-Setup.exe.sha256",
            "browser_download_url": "https://example.test/setup.sha256",
        })
    return {
        "tag_name": "v2.0.0",
        "html_url": "https://example.test/release",
        "assets": assets,
    }


def test_release_requires_installer_checksum_and_matching_version():
    installer = b"verified installer"
    checksum = hashlib.sha256(installer).hexdigest() + "  AimCompanion-Setup.exe"
    report = verify_release_payload(
        _release(), installer, checksum, expected_version="2.0.0",
    )
    assert report.asset_names == {
        "AimCompanion-Setup.exe", "AimCompanion-Setup.exe.sha256",
    }
    assert report.checksum_matches is True
    assert report.updater_selected_version == "2.0.0"


def test_missing_checksum_fails_release():
    with pytest.raises(ReleaseVerificationError, match="checksum asset"):
        verify_release_payload(
            _release(False), b"installer", "0" * 64,
            expected_version="2.0.0",
        )


def test_github_api_request_uses_workflow_token():
    with patch.dict(os.environ, {"GITHUB_TOKEN": "workflow-token"}), patch(
        "scripts.verify_release.urllib.request.urlopen"
    ) as urlopen:
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = b"{}"

        _get_json("https://api.github.com/repos/example/project/releases/tags/v1")

    request = urlopen.call_args.args[0]
    assert request.get_header("Authorization") == "Bearer workflow-token"
