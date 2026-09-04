import hashlib

import pytest

from scripts.verify_release import ReleaseVerificationError, verify_release_payload


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
