import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest
from unittest.mock import patch

import install


class InstallTests(unittest.TestCase):
    def test_paths_and_optional_apps(self):
        home = Path('/home/друг "test" & spaces')
        with patch("install.shutil.which", return_value=None):
            text = install.settings(home, home / "plugins", home / "wall.jpg",
                                    home / "Фото", home / "Видео")
        config = tomllib.loads(text)
        self.assertEqual(config["shell"]["screenshot"]["directory"], str(home / "Фото"))
        self.assertNotIn("vlad-dev/ruh-vpn", config["plugins"]["enabled"])
        self.assertNotIn("vlad-dev/equalizer", config["plugins"]["enabled"])
        self.assertNotIn("recorder", config["bar"]["default"]["center"])
        self.assertNotIn("/home/vlad", text)
        self.assertNotIn("__PLUGIN", text)
        with patch("install.shutil.which", return_value="/usr/bin/app"):
            config = tomllib.loads(install.settings(home, home / "plugins", home / "wall.jpg",
                                                   home / "Фото", home / "Видео"))
        self.assertIn("vlad-dev/equalizer", config["plugins"]["enabled"])
        self.assertIn("noctalia/screen_recorder", config["plugins"]["enabled"])

    def test_backup_and_dry_run(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "settings.toml"
            target.write_bytes(b"original")
            install.deploy(b"new", target, 0o644, "one", True)
            self.assertEqual(target.read_bytes(), b"original")
            self.assertEqual(len(list(target.parent.iterdir())), 1)
            install.deploy(b"new", target, 0o644, "one", False)
            install.deploy(b"newer", target, 0o644, "two", False)
            self.assertEqual(target.with_name("settings.toml.backup-one").read_bytes(), b"original")
            self.assertEqual(target.with_name("settings.toml.backup-two").read_bytes(), b"new")
            self.assertEqual(target.read_bytes(), b"newer")

    def test_symlink_target_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "original"
            original.write_bytes(b"original")
            target = Path(directory) / "link"
            target.symlink_to(original)
            install.deploy(b"new", target, 0o644, "test", False)
            self.assertEqual(original.read_bytes(), b"original")
            self.assertTrue(target.with_name("link.backup-test").is_symlink())
            self.assertFalse(target.is_symlink())

    def test_enabled_plugin_files_exist(self):
        manifests = list((install.ROOT / "noctalia-plugins").glob("*/plugin.toml"))
        self.assertEqual(len(manifests), 9)
        for path in manifests:
            data = tomllib.loads(path.read_text())
            for kind in ("service", "widget", "panel", "shortcut", "desktop_widget"):
                for entry in data.get(kind, []):
                    self.assertTrue((path.parent / entry["entry"]).is_file(), str(path))

    def test_app_choices_and_quoted_home(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "friend & spaces"
            config = home / ".config/niri"
            config.mkdir(parents=True)
            app = home / "my-app"
            app.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            app.chmod(0o755)
            config.joinpath("apps.conf").write_text(
                f'TERMINAL="{app}"\nBROWSER="{app}"\nFILE_MANAGER="{app}"\n')
            env = {**os.environ, "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config")}
            for mode in ("terminal", "browser", "files"):
                result = subprocess.run(["bash", str(install.ROOT / "local/bin/niri-app"), mode],
                                        env=env, capture_output=True, text=True, check=True)
                self.assertEqual(result.stdout.strip(), str(home) if mode == "files" else "")


if __name__ == "__main__":
    unittest.main()
