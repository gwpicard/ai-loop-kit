import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

from kit.tests.helpers import run_git
from kit.tests.test_guard import GUARD, GuardCase


TEST = "tests/run-all.sh"
FILES = "python3 kit/tests/run.py {files}"
ROLES = ("builder", "test-writer", "reviewer", "pass")
RUNNERS = ("bash", "sh", "zsh", "python3", "python", "node", "./")
FORMS = ("claude", "codex", "codex-shell")
CASES = (
    ("recursive-delete", ("rm", "-rf", "scratch")),
    ("recursive-delete", ("find", "scratch", "-delete")),
    ("role-git", ("git", "push", "origin", "feature")),
    ("role-git", ("git", "merge", "feature")),
    ("full-test", (TEST,)),
)


def script_text(runner, words, layout=0):
    command = shlex.join(words)
    if runner in ("python", "python3", "node"):
        literal = (repr(list(words)) if not layout else
                   json.dumps(list(words), indent=4))
        if runner == "node":
            return "require('child_process').spawnSync(%s, %s);\n" % (
                json.dumps(words[0]), json.dumps(list(words[1:]), indent=4))
        return "import subprocess\nsubprocess.run(%s)\n" % literal
    if words[0] == "find":
        command = 'find "$tmp" -delete'
    return '#!/bin/sh\ntmp=scratch\n%s\n' % command


def launch(runner, path):
    if runner == "./":
        return shlex.quote("./" + path)
    return runner + " " + shlex.quote(path)


class TestSessionScript(GuardCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        scripts = Path(cls.work, "scripts")
        scripts.mkdir()
        for runner in RUNNERS:
            name = "direct" if runner == "./" else runner
            path = scripts / ("unchanged-" + name)
            path.write_text("".join(script_text(runner, words) for _, words in CASES))
            path.chmod(0o755)
        for state in ("working", "staged", "committed"):
            (scripts / (state + ".sh")).write_text("#!/bin/sh\necho safe\n")
        run_git(["add", "scripts"], cls.work)
        run_git(["commit", "-qm", "script baseline"], cls.work)
        cls.start = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=cls.work, text=True).strip()
        (scripts / "committed.sh").write_text('find "$tmp" -delete\n')
        run_git(["add", "scripts/committed.sh"], cls.work)
        run_git(["commit", "-qm", "session script change"], cls.work)
        (scripts / "staged.sh").write_text('find "$tmp" -delete\n')
        run_git(["add", "scripts/staged.sh"], cls.work)
        (scripts / "working.sh").write_text('find "$tmp" -delete\n')

    def hook(self, command, role="builder", form="claude", cwd=None, files=FILES):
        env = {k: v for k, v in os.environ.items() if not k.startswith("LOOP_")}
        env.update(LOOP_AGENT="claude" if form == "claude" else "codex",
                   LOOP_START=self.start, LOOP_TEST_COMMAND=TEST,
                   LOOP_TEST_FILES_COMMAND=files)
        if role:
            env["LOOP_ROLE"] = role
        payload = ["/bin/bash", "-lc", command] if form == "codex-shell" else command
        data = {"tool_name": "Bash", "tool_input": {"command": payload},
                "cwd": cwd or self.work}
        try:
            result = subprocess.run([sys.executable, GUARD], input=json.dumps(data),
                                    capture_output=True, text=True, env=env, timeout=30)
        except subprocess.TimeoutExpired:
            self.fail("the guard hung while inspecting " + command)
        self.assertNotIn("guard: internal error", result.stderr)
        return result

    def refused_script(self, result, rule, path):
        self.refused(result)
        self.assertIn("rule: " + rule, result.stderr.splitlines())
        self.assertIn(Path(path).name, result.stderr)

    def test_untracked_scripts_are_refused_by_rule_in_each_launcher(self):
        for runner in RUNNERS:
            for rule, words in CASES:
                for layout, relative in enumerate(("scripts/session-script", "scripts/with spaces/session script")):
                    path = Path(self.work, relative)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(script_text(runner, words, layout))
                    path.chmod(0o755)
                    # Exercise relative paths and absolute paths with quoted spaces.
                    operand = relative if runner == "./" or not layout else str(path)
                    for form in FORMS:
                        with self.subTest(runner=runner, words=words, path=operand, form=form):
                            result = self.hook(launch(runner, operand), form=form)
                            self.refused_script(result, rule, path)

    def test_working_staged_and_committed_changes_compare_with_loop_start(self):
        for state in ("working", "staged", "committed"):
            path = "scripts/" + state + ".sh"
            for role in ROLES:
                for form in FORMS:
                    with self.subTest(state=state, role=role, form=form):
                        result = self.hook("sh " + path, role, form)
                        self.refused_script(result, "recursive-delete", path)

    def test_scripts_outside_the_project_are_refused(self):
        outside = Path(self._tmp.name, "outside script.sh")
        for rule, words in CASES:
            outside.write_text(script_text("sh", words))
            for form in FORMS:
                with self.subTest(words=words, form=form):
                    result = self.hook("bash " + shlex.quote(str(outside)), form=form)
                    self.refused_script(result, rule, outside)

    def test_unchanged_tracked_scripts_and_safe_session_scripts_are_allowed(self):
        for runner in RUNNERS:
            name = "direct" if runner == "./" else runner
            unchanged = "scripts/unchanged-" + name
            safe = "scripts/safe-" + name
            path = Path(self.work, safe)
            path.write_text(script_text(runner, ("git", "status")))
            path.chmod(0o755)
            for relative in (unchanged, safe):
                for form in FORMS:
                    with self.subTest(runner=runner, path=relative, form=form):
                        self.allowed(self.hook(launch(runner, relative), form=form))

    def test_only_the_first_operand_is_read_and_paths_use_the_command_cwd(self):
        safe = Path(self.work, "scripts/first-operand.sh")
        safe.write_text("#!/bin/sh\nprintf '%s\\n' \"$1\"\n")
        dangerous = Path(self.work, "scripts/second-operand.sh")
        dangerous.write_text('find "$tmp" -delete\n')
        for form in FORMS:
            with self.subTest(form=form):
                self.allowed(self.hook("sh scripts/first-operand.sh scripts/second-operand.sh", form=form))
                result = self.hook("sh second-operand.sh", form=form,
                                   cwd=str(dangerous.parent))
                self.refused_script(result, "recursive-delete", dangerous)

    def test_full_test_string_literals_are_refused_but_targeted_runs_are_allowed(self):
        path = Path(self.work, "scripts/test-command.py")
        for command in (TEST, FILES.format(files="kit/tests/test_example.py")):
            path.write_text("import os\nos.system(%s)\n" % repr(command))
            for form in FORMS:
                with self.subTest(command=command, form=form):
                    result = self.hook("python3 scripts/test-command.py", form=form)
                    if command == TEST:
                        self.refused_script(result, "full-test", path)
                        self.allowed(self.hook("python3 scripts/test-command.py", form=form, files=""))
                    else:
                        self.allowed(result)

    def test_without_a_role_no_script_is_read(self):
        for runner in RUNNERS:
            path = Path(self.work, "scripts/no-role-script")
            path.write_text(script_text(runner, ("rm", "-rf", "scratch")))
            path.chmod(0o755)
            fifo = Path(self.work, "scripts/no-role-fifo-" + ("direct" if runner == "./" else runner))
            os.mkfifo(fifo)
            # Opening the FIFO for reading would hang: the guard must leave it alone.
            for relative in ("scripts/no-role-script", str(fifo.relative_to(self.work))):
                for form in FORMS:
                    with self.subTest(runner=runner, path=relative, form=form):
                        self.allowed(self.hook(launch(runner, relative), role=None, form=form))


class TestBuilderScriptGuidance(GuardCase):
    def paragraphs(self):
        brief = Path(GUARD).resolve().parents[1] / "briefs/builder.md"
        return [" ".join(p.replace("`", "").lower().split())
                for p in re.split(r"\n\s*\n", brief.read_text())]

    def test_refused_commands_cannot_be_moved_into_code(self):
        candidates = [p for p in self.paragraphs() if "refused command" in p]
        self.assertTrue(any(
            re.search(r"never|do not|must not", p) and
            all(term in p for term in ("script", "interpreter code", "project code", "same result"))
            for p in candidates), "builder guidance must prohibit moving a refused command into code")

    def test_script_scratch_space_is_created_in_the_system_temporary_folder_and_left(self):
        self.assertTrue(any(
            "script" in p and "scratch" in p and "system temporary folder" in p and
            re.search(r"creat|mktemp", p) and re.search(r"leav\w* (?:it |the (?:folder|directory) )?there", p)
            for p in self.paragraphs()),
            "builder guidance must create script scratch space in the system temporary folder and leave it there")

    def test_an_issue_needing_the_refused_outcome_parks(self):
        self.assertTrue(any(
            "builder" in p and "issue" in p and "refused" in p and
            re.search(r"need|requir", p) and re.search(r"\bpark\w*\b", p)
            for p in self.paragraphs()),
            "builder guidance must park an issue that needs the refused outcome")
