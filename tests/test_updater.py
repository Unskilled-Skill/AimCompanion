import unittest

from core.updater import UpdateError, is_newer_version, parse_release, version_tuple


class UpdaterTests(unittest.TestCase):
    def test_semantic_versions_compare_numerically(self):
        self.assertEqual(version_tuple("v1.2"), (1, 2, 0))
        self.assertTrue(is_newer_version("1.10.0", "1.9.9"))
        self.assertFalse(is_newer_version("1.0.0", "1.0.0"))

    def test_release_requires_the_official_installer_asset(self):
        with self.assertRaises(UpdateError):
            parse_release({"tag_name": "v1.1.0", "assets": []})

    def test_release_prefers_github_sha256_digest(self):
        digest = "a" * 64
        release = parse_release({
            "tag_name": "v1.1.0",
            "html_url": "https://example.invalid/release",
            "assets": [{
                "name": "AimCompanion-Setup.exe",
                "browser_download_url": "https://example.invalid/setup.exe",
                "digest": f"sha256:{digest}",
            }],
        })
        self.assertEqual(release["version"], "1.1.0")
        self.assertEqual(release["expected_hash"], digest)


if __name__ == "__main__":
    unittest.main()
