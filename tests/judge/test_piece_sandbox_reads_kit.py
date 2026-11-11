# A walk-away Claude session may read the kit, its Python install and uv, and writes nowhere new.
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kit" / "scripts"))

try:
    import sandbox
except ImportError as error:
    if error.name != "sandbox" and not str(error.name).startswith("sandbox."):
        raise
    sandbox = None

KIT_ROOT = Path(__file__).resolve().parents[2] / "kit"
SYSTEM_UV = ["/opt/homebrew/bin/uv", "/usr/local/bin/uv"]


def settings(folder, which=None, home=None):
    assert sandbox is not None and hasattr(sandbox, "settings_for"), "sandbox.settings_for must exist"
    with patch.object(sandbox.shutil, "which", return_value=which):
        if home is None:
            return sandbox.settings_for(folder)["sandbox"]["filesystem"]
        with patch.object(Path, "home", return_value=home):
            return sandbox.settings_for(folder)["sandbox"]["filesystem"]


def uv_entries(allow_read):
    return {path for path in allow_read if Path(path).name == "uv"}


class SandboxReadsKitTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.folder = self.root / "build"
        self.folder.mkdir()
        self.home = self.root / "home"
        self.home.mkdir()

    def make_uv(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\n")
        path.chmod(0o755)
        return path

    def test_D1_allow_read_includes_the_kit_root(self):
        read = settings(self.folder, home=self.home)["allowRead"]
        self.assertTrue((KIT_ROOT / "bin" / "kit-python").is_file())
        self.assertIn(str(KIT_ROOT.resolve()), read)

    def test_D2_allow_read_includes_the_parent_of_the_base_prefix(self):
        read = settings(self.folder, home=self.home)["allowRead"]
        self.assertIn(str(Path(sys.base_prefix).resolve().parent), read)

    def test_D3_uv_on_path_is_allowed_resolved(self):
        real = self.make_uv(self.root / "real" / "uv")
        link = self.root / "bin" / "uv"
        link.parent.mkdir()
        link.symlink_to(real)
        read = settings(self.folder, which=str(link), home=self.home)["allowRead"]
        self.assertIn(str(real.resolve()), read)

    def test_D3_uv_on_path_wins_over_a_home_candidate(self):
        on_path = self.make_uv(self.root / "onpath" / "uv")
        home_uv = self.make_uv(self.home / ".local" / "bin" / "uv")
        read = settings(self.folder, which=str(on_path), home=self.home)["allowRead"]
        self.assertIn(str(on_path.resolve()), read)
        self.assertNotIn(str(home_uv.resolve()), read)

    def test_D3_uv_at_a_candidate_path_is_allowed_when_not_on_path(self):
        cargo = self.make_uv(self.home / ".cargo" / "bin" / "uv")
        read = settings(self.folder, which=None, home=self.home)["allowRead"]
        self.assertIn(str(cargo.resolve()), read)

    def test_D3_first_existing_candidate_only(self):
        local = self.make_uv(self.home / ".local" / "bin" / "uv")
        cargo = self.make_uv(self.home / ".cargo" / "bin" / "uv")
        read = settings(self.folder, which=None, home=self.home)["allowRead"]
        self.assertIn(str(local.resolve()), read)
        self.assertNotIn(str(cargo.resolve()), read)

    def test_D3_no_uv_adds_no_uv_path(self):
        read = settings(self.folder, which=None, home=self.home)["allowRead"]
        expected = {str(Path(p).resolve()) for p in SYSTEM_UV if Path(p).exists()}
        self.assertEqual(uv_entries(read), expected)

    def test_D4_allow_write_is_unchanged(self):
        home = self.home
        write = settings(self.folder, home=home)["allowWrite"]
        self.assertEqual(write, [str(self.folder.resolve()), str(Path(tempfile.gettempdir())),
                                 str(home / ".npm"), str(home / ".cache" / "pip")])

    def test_D5_credential_paths_stay_denied(self):
        deny = settings(self.folder, home=self.home)["denyRead"]
        for name in ("~/.ssh", "~/.config/gh", "~/Library/Keychains"):
            self.assertIn(str(Path(name).expanduser()), deny)


if __name__ == "__main__":
    unittest.main()
