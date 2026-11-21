"""Legacy runtime folders require the intermediate kit upgrade."""
import json
from pathlib import Path
import subprocess
import sys

from kit.tests.helpers import FakeGh, make_repo
from kit.tests.test_setup import rule
import setup


KIT = Path(__file__).resolve().parents[1]
LITE = ({".lite": None}, {
    ".lite/logs/old.log": "old log\n",
    ".lite/pass.json": "{}\n",
    ".loop/logs/current.log": "current log\n",
    ".loop/pass.json": '{"keep": true}\n',
})
V1 = ({".loop/heartbeat": "old heartbeat\n"}, {
    ".loop/preferences.json": "{}\n",
    ".loop/cache/result.json": '{"old": true}\n',
    ".loop/events.jsonl": "old event\n",
    ".loop/loop.out": "current output\n",
})


def snapshot(project):
    root = Path(project)
    return {str(p.relative_to(root)): p.read_bytes() if p.is_file() else None
            for name in (".lite", ".loop") for p in [root / name, *(root / name).rglob("*")]
            if p.exists()}


class LegacyRuntimeTest(FakeGh):
    def project(self, files):
        work, _ = make_repo(self.tmp, {"loop.json": '{"Test command": "true"}\n'})
        for name, content in files.items():
            path = Path(work, name)
            if content is None:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
        self.scenario([
            rule("label list", json.dumps([{"name": n} for n in setup.LABELS])),
            rule("issue list", '[{"number":7,"title":"Factory"}]'),
        ])
        return work

    def check_tidy(self, examples):
        for files in examples:
            for dry_run in (False, True):
                with self.subTest(files=files, dry_run=dry_run):
                    work = self.project(files)
                    before = snapshot(work)
                    moved, _ = setup.tidy(work, dry_run=dry_run)
                    self.assertEqual(moved, [], "tidy must leave legacy files for kit 2.2.0")
                    self.assertEqual(snapshot(work), before)

    def check_command(self, command, examples):
        for files in examples:
            with self.subTest(command=command, files=files):
                work = self.project(files)
                before = snapshot(work)
                args = ([str(KIT / "bin/loop"), "run"] if command == "run" else
                        [sys.executable, str(KIT / "scripts/setup.py"), work])
                result = subprocess.run(args, cwd=work, capture_output=True, text=True, timeout=30)
                text = result.stdout + result.stderr
                self.assertEqual(result.returncode, 1, text)
                self.assertIn("refused:", text)
                self.assertRegex(" ".join(text.lower().split()),
                                 r"install kit 2\.2\.0.*run its setup.*then update to this version")
                after = snapshot(work)
                for name, content in before.items():
                    self.assertIn(name, after, text)
                    self.assertEqual(after[name], content, text)
                self.assertFalse(Path(work, ".loop/v1").exists(), text)

    def test_tidy_leaves_lite_files_in_place(self):
        self.check_tidy(LITE)

    def test_tidy_leaves_kit_1_files_in_place(self):
        self.check_tidy(V1)

    def test_setup_refuses_lite_with_the_intermediate_upgrade(self):
        self.check_command("setup", LITE)

    def test_setup_refuses_kit_1_with_the_intermediate_upgrade(self):
        self.check_command("setup", V1)

    def test_loop_run_refuses_lite_with_the_intermediate_upgrade(self):
        self.check_command("run", LITE)

    def test_loop_run_refuses_kit_1_with_the_intermediate_upgrade(self):
        self.check_command("run", V1)
