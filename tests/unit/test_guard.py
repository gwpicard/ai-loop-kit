"""Unit tests for the command guard hook (kit/hooks/guard.py) and the command log.

The hook reads a command, not its text. These tests feed it every spelling in
`kit/templates/blocked-commands.md`, the permission matcher's own cases, and the
harmless forms that must still run. A refusal always carries a reason. Nothing
here deletes anything: the throwaway folder is made with mkdtemp and left in
place.
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any

REPO = Path(__file__).resolve().parents[2]
HOOKS = REPO / "kit" / "hooks"
sys.path.insert(0, str(REPO / "kit" / "scripts"))
sys.path.insert(0, str(HOOKS))


def load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


matcher = load("permission_matcher", REPO / "tests" / "lib" / "permission-matcher.py")
guard = load("guard", HOOKS / "guard.py")
command_log = load("command_log", HOOKS / "command-log.py")

BLOCKED = (REPO / "kit" / "templates" / "blocked-commands.md").read_text()

DENY, ASK, ALLOW = "deny", "ask", "allow"


class Project:
    """A throwaway project: a main folder on `main`, and one worktree."""

    def __init__(self) -> None:
        base = Path(os.path.realpath(tempfile.mkdtemp()))
        self.base = base
        self.home = base / "home"
        self.data = base / "data"
        self.root = base / "demo"
        self.home.mkdir()
        self.data.mkdir()
        (self.root / ".git").mkdir(parents=True)
        (self.root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        self.worktree = self.root / ".agents" / "worktrees" / "w1"
        self.worktree.mkdir(parents=True)
        admin = self.root / ".git" / "worktrees" / "w1"
        admin.mkdir(parents=True)
        (admin / "HEAD").write_text("ref: refs/heads/piece-1\n")
        (self.worktree / ".git").write_text(f"gitdir: {admin}\n")
        self.feature = base / "feature"
        (self.feature / ".git").mkdir(parents=True)
        (self.feature / ".git" / "HEAD").write_text("ref: refs/heads/my-feature\n")
        self.env = {
            "HOME": str(self.home),
            "AI_LOOP_KIT_DATA": str(self.data),
            "AI_LOOP_KIT_RUN": "night-1",
        }
        self.key_dir = self.data / self._key()
        (self.key_dir / "held-out").mkdir(parents=True)
        (self.key_dir / "app-key.pem").write_text("not a real key\n")
        (self.key_dir / "held-out" / "case1.txt").write_text("hidden\n")
        (self.home / ".config" / "gh").mkdir(parents=True)
        (self.home / ".config" / "gh" / "hosts.yml").write_text("oauth_token: nope\n")

    def _key(self) -> str:
        from loop.paths import project_key

        return project_key(self.root)


P: Project


def setUpModule() -> None:
    global P
    P = Project()


def bash(command: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> Any:
    payload = {
        "session_id": "s1",
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(cwd or P.root),
    }
    return guard.decide(payload, env or P.env)


def tool(name: str, tool_input: dict[str, Any], cwd: Path | None = None) -> Any:
    payload = {
        "session_id": "s1",
        "hook_event_name": "PreToolUse",
        "tool_name": name,
        "tool_input": tool_input,
        "cwd": str(cwd or P.root),
    }
    return guard.decide(payload, P.env)


class Cases(unittest.TestCase):
    def expect(self, command: str, kind: str, cwd: Path | None = None) -> None:
        got = bash(command, cwd)
        self.assertEqual(got.kind, kind, f"{command!r}: {got.kind}, {got.reason}")
        if kind != ALLOW:
            self.assertTrue(got.reason.strip(), f"{command!r} has no reason")

    def refused(self, *commands: str) -> None:
        for command in commands:
            with self.subTest(command=command):
                self.expect(command, DENY)

    def passes(self, *commands: str) -> None:
        for command in commands:
            with self.subTest(command=command):
                self.expect(command, ALLOW)


class ReferenceSpellings(Cases):
    """Every spelling in blocked-commands.md, read from the file itself."""

    def read(self, marker: str, heading: str, keep: Any) -> list[str]:
        found = matcher.read_list(BLOCKED, marker, keep, heading)
        self.assertTrue(found, f"no list {marker!r} under {heading!r}")
        return list(found)

    def test_push_spellings_the_rules_refuse(self) -> None:
        listed = self.read(
            "These spellings are refused",
            "A direct push to `main`",
            lambda s: "push" in s and " " in s,
        )
        self.assertGreater(len(listed), 8)
        self.refused(*listed)

    def test_push_spellings_the_rules_miss(self) -> None:
        listed = self.read(
            "These spellings are not refused",
            "A direct push to `main`",
            lambda s: "push" in s and " " in s,
        )
        for command in listed:
            with self.subTest(command=command):
                got = bash(command)
                # A branch held in a variable cannot be read, so it asks.
                expected = ASK if "$" in command else DENY
                self.assertEqual(got.kind, expected, f"{command!r}: {got.reason}")
                self.assertTrue(got.reason)

    def test_delete_spellings_the_rules_refuse(self) -> None:
        listed = self.read(
            "These spellings are refused", "Deleting files and Git history", lambda s: " " in s
        )
        self.assertGreater(len(listed), 8)
        self.refused(*listed)

    def test_delete_spellings_the_rules_miss(self) -> None:
        listed = self.read(
            "These spellings are not refused",
            "Deleting files and Git history",
            lambda s: " " in s,
        )
        self.assertGreater(len(listed), 5)
        self.refused(*listed)

    def test_state_spellings_refused_by_the_rules_and_the_hook(self) -> None:
        heading = "Changing a piece's state by hand"
        both = self.read(
            "These spellings are refused by the hook and by the deny rules",
            heading,
            lambda s: "gh" in s and " " in s,
        )
        self.refused(*both)

    def test_state_spellings_only_the_hook_refuses(self) -> None:
        heading = "Changing a piece's state by hand"
        hook_only = self.read(
            "The hook refuses these spellings, and the deny rules miss them",
            heading,
            lambda s: "gh" in s and " " in s,
        )
        self.refused(*hook_only)

    def test_state_spellings_neither_refuses(self) -> None:
        heading = "Changing a piece's state by hand"
        neither = self.read("Neither refuses these spellings", heading, lambda s: " " in s)
        for command in neither:
            with self.subTest(command=command):
                got = bash(command)
                # A label in a variable cannot be read, so it asks. A call
                # from another script is invisible, so it passes.
                if "$LABEL" in command:
                    self.assertEqual(got.kind, ASK)
                else:
                    self.assertEqual(got.kind, ALLOW)

    def test_the_hook_name_in_the_reference_is_the_new_one(self) -> None:
        self.assertIn("kit/hooks/guard.py", BLOCKED)
        self.assertNotIn("state-guard", BLOCKED)
        self.assertNotIn("setup-ai-build-kit", BLOCKED)


class MatcherCases(Cases):
    """The cases the permission matcher cannot read, and the ones it can."""

    def test_option_between_git_and_push(self) -> None:
        self.refused("git -C . push origin main", "git -c push.default=current push origin main")

    def test_wrappers_and_full_paths(self) -> None:
        self.refused(
            "env X=1 git push --force",
            "X=1 git push origin main",
            "/usr/bin/git push origin main",
            "command git push -f origin feature",
            "nohup git push origin HEAD:main",
            "timeout 5 git push origin main",
            "sudo -u me git push origin main",
        )

    def test_shell_inside_a_shell(self) -> None:
        self.refused(
            'sh -c "rm -rf x"',
            "bash -lc 'git push origin main'",
            "sh -c \"sh -c 'rm -r build'\"",
            "eval 'git reset --hard'",
        )

    def test_chains_pipes_and_substitutions(self) -> None:
        self.refused(
            "echo done; git push origin main",
            "git status && rm -rf build",
            "ls | xargs rm -rf",
            "echo $(git reset --hard)",
            "echo `git reset --hard`",
            "(cd x && git push --force)",
            "git status\nrm -r build",
        )

    def test_find_delete(self) -> None:
        self.refused(
            "find . -delete",
            "find build -name '*.o' -delete",
            "find . -exec rm -rf {} \\;",
        )

    def test_history_and_clean(self) -> None:
        self.refused(
            "git reset --hard",
            "git reset --hard HEAD~1",
            "git clean -fd",
            "git clean -f",
            "git reflog expire --expire=now --all",
            "git gc --prune=now",
            "git worktree remove --force .agents/worktrees/w1",
        )

    def test_force_push_spellings(self) -> None:
        self.refused(
            "git push --force origin feature",
            "git push -f origin feature",
            "git push --force-with-lease origin feature",
            "git push origin +feature",
            "git push -fu origin feature",
        )

    def test_push_main_spellings(self) -> None:
        self.refused(
            "git push origin :main",
            "git push --delete origin main",
            "git push origin HEAD:refs/heads/main",
            "git push origin 'main'",
            "git push --mirror origin",
            "git push --all origin",
        )

    def test_implicit_push_while_main_is_checked_out(self) -> None:
        self.refused("git push", "git push origin", "git push origin HEAD", "git push -u origin")

    def test_state_labels(self) -> None:
        self.refused(
            "gh issue edit 5 --add-label state:ready",
            "gh issue edit 5 --add-label needs-you",
            "gh issue edit 5 --remove-label needs-you",
            "gh issue create --title x --label needs-you",
            "gh pr edit 5 --add-label state:done",
            "gh label create needs-you",
            "gh label delete needs-you --yes",
        )

    def test_gh_api_label_writes(self) -> None:
        self.refused(
            "gh api -X POST repos/o/r/issues/5/labels -f 'labels[]=state:ready'",
            "gh api -X DELETE repos/o/r/issues/12/labels/state:ready",
            "gh api --method=PUT repos/o/r/issues/5/labels --input labels.json",
            "gh api repos/o/r/issues/5/labels -f labels[]=bug",
            "gh api -X POST repos/o/r/labels -f name=needs-you",
            "gh api graphql -f query='mutation { addLabelsToLabelable(input: {}) { id } }'",
        )

    def test_gate_sync_is_for_the_person(self) -> None:
        self.refused(
            "python3 kit/scripts/gate.py sync",
            "kit/scripts/gate.py sync --dry-run",
            "cd x && python3 gate.py sync",
        )

    def test_harmless_forms_pass(self) -> None:
        self.passes(
            "git push origin feature",
            "git push -u origin feature",
            "git push origin main-fix",
            "git push origin HEAD:feature",
            "git push -o main origin feature",
            "git push origin heads/feature",
            "git status",
            "git log --oneline main",
            "git checkout main",
            "git gc",
            "git reflog",
            "git clean -n",
            "git reset --soft HEAD~1",
            "git worktree remove .agents/worktrees/w1",
            "rm -f notes.txt",
            "rm file.txt",
            "ls -la",
            "find . -name '*.py'",
            "gh issue view 5",
            "gh issue list --label state:ready",
            "gh issue edit 12 --add-label type:bug",
            "gh issue edit 12 --title 'Explain state:ready on the board'",
            "gh label list",
            "gh api repos/o/r/issues/12/labels",
            "python3 kit/scripts/gate.py report",
            "python3 kit/scripts/gate.py move 12 ready",
            'git commit -m "Move the piece to state:ready through the gate"',
            "echo .env >> .gitignore",
            "cat <<'EOF' > notes.txt\ngit push origin main\nrm -rf x\nEOF",
        )

    def test_harmless_push_in_a_feature_folder(self) -> None:
        for command in ("git push", "git push origin", "git push origin HEAD"):
            with self.subTest(command=command):
                self.expect(command, ALLOW, cwd=P.feature)

    def test_push_main_from_a_worktree_on_a_piece_branch(self) -> None:
        self.expect("git push origin HEAD", ALLOW, cwd=P.worktree)
        self.expect("git push origin main", DENY, cwd=P.worktree)

    def test_the_person_is_asked_before_a_comment_in_their_name(self) -> None:
        for command in (
            "gh issue comment 5 --body 'hello'",
            "gh pr comment 5 -b hello",
            "/opt/homebrew/bin/gh pr comment 5 --body-file note.md",
            "sh -c 'gh issue comment 5 -b hi'",
            "gh pr review 5 --approve",
            "gh -R o/r issue comment 5 -b hi",
        ):
            with self.subTest(command=command):
                self.expect(command, ASK)

    def test_a_command_that_cannot_be_read_asks(self) -> None:
        self.expect("echo 'unfinished", ASK)

    def test_github_tool_calls_with_state_labels(self) -> None:
        got = tool("mcp__github__add_issue_labels", {"labels": ["bug", "state:ready"]})
        self.assertEqual(got.kind, DENY)
        got = tool("mcp__github__add_issue_labels", {"labels": [{"name": "needs-you"}]})
        self.assertEqual(got.kind, DENY)
        got = tool("mcp__github__add_issue_labels", {"labels": ["bug"]})
        self.assertEqual(got.kind, ALLOW)
        got = tool("mcp__github__add_issue_comment", {"body": "hello"})
        self.assertEqual(got.kind, ASK)
        self.assertEqual(tool("mcp__other__thing", {"labels": ["state:ready"]}).kind, ALLOW)

    def test_other_tools_pass(self) -> None:
        self.assertEqual(tool("Task", {"prompt": "go"}).kind, ALLOW)


class RealEnvFiles(Cases):
    def marked(self, folder: Path, name: str = ".env") -> Path:
        path = folder / name
        path.write_text(guard.THROWAWAY_MARKER + "\nPORT=3000\n")
        return path

    def test_cat_env_in_the_main_folder(self) -> None:
        (P.root / ".env").write_text("SECRET=1\n")
        self.refused("cat .env", "cat ./.env", "head -n 3 .env", "grep SECRET .env")
        self.refused("cat .e*", "cat < .env", "source .env", "cat .env.local")

    def test_env_in_the_main_folder_is_refused_even_with_the_marker(self) -> None:
        self.marked(P.root)
        self.refused("cat .env")
        got = tool("Read", {"file_path": str(P.root / ".env")})
        self.assertEqual(got.kind, DENY)

    def test_env_in_a_subfolder_of_the_main_folder(self) -> None:
        (P.root / "app").mkdir(exist_ok=True)
        self.marked(P.root / "app")
        self.refused("cat app/.env")

    def test_throwaway_env_in_a_worktree_passes(self) -> None:
        self.marked(P.worktree)
        self.expect("cat .env", ALLOW, cwd=P.worktree)
        got = tool("Read", {"file_path": str(P.worktree / ".env")}, cwd=P.worktree)
        self.assertEqual(got.kind, ALLOW)

    def test_env_in_a_worktree_without_the_marker_is_refused(self) -> None:
        (P.worktree / ".env.local").write_text("SECRET=1\n")
        self.expect("cat .env.local", DENY, cwd=P.worktree)
        got = tool("Read", {"file_path": str(P.worktree / ".env.local")}, cwd=P.worktree)
        self.assertEqual(got.kind, DENY)

    def test_an_env_file_that_does_not_exist_is_refused_unless_marked(self) -> None:
        self.expect("cat .env.staging", DENY, cwd=P.worktree)

    def test_the_example_file_is_not_an_env_file(self) -> None:
        self.passes("cat .env.example", "cat .env.sample")

    def test_main_folder_path_from_a_worktree_session(self) -> None:
        self.marked(P.root)
        self.expect(f"cat {P.root}/.env", DENY, cwd=P.worktree)

    def test_reading_with_the_file_tools(self) -> None:
        got = tool("Grep", {"pattern": "x", "path": str(P.root / ".env")})
        self.assertEqual(got.kind, DENY)
        got = tool("Read", {"file_path": str(P.root / "README.md")})
        self.assertEqual(got.kind, ALLOW)


class SecretsAndCredentials(Cases):
    def test_app_key_file(self) -> None:
        key = P.key_dir / "app-key.pem"
        self.refused(f"cat {key}", f"openssl rsa -in {key}", f"cp {key} /tmp/x")
        self.assertEqual(tool("Read", {"file_path": str(key)}).kind, DENY)

    def test_app_key_of_another_project(self) -> None:
        other = P.data / "other-0123456789ab"
        other.mkdir(exist_ok=True)
        self.refused(f"cat {other}/app-key.pem")

    def test_held_out_folder(self) -> None:
        held = P.key_dir / "held-out"
        self.refused(f"cat {held}/case1.txt", f"ls {held}", f"cp -n {held}/case1.txt .")
        self.assertEqual(tool("Read", {"file_path": str(held / "case1.txt")}).kind, DENY)
        self.assertEqual(tool("Glob", {"path": str(held), "pattern": "*"}).kind, DENY)

    def test_gh_config(self) -> None:
        self.refused(
            f"cat {P.home}/.config/gh/hosts.yml",
            "cat ~/.config/gh/hosts.yml",
            'cat "$HOME/.config/gh/hosts.yml"',
            "cat ${HOME}/.config/gh/*",
        )
        self.assertEqual(
            tool("Read", {"file_path": str(P.home / ".config/gh/hosts.yml")}).kind, DENY
        )

    def test_gh_config_folder_set_by_the_environment(self) -> None:
        elsewhere = P.base / "ghconf"
        elsewhere.mkdir(exist_ok=True)
        env = dict(P.env, GH_CONFIG_DIR=str(elsewhere))
        self.assertEqual(bash(f"cat {elsewhere}/hosts.yml", env=env).kind, DENY)

    def test_gh_auth_token(self) -> None:
        self.refused(
            "gh auth token",
            "gh auth token --hostname github.com",
            "gh auth status --show-token",
            "gh auth status -t",
            "/opt/homebrew/bin/gh auth token",
            "TOKEN=$(gh auth token)",
            "echo hi && gh auth token",
        )
        self.passes("gh auth status")

    def test_keychain(self) -> None:
        self.refused(
            "security find-generic-password -s github -w",
            "security find-internet-password -s github.com -w",
            "/usr/bin/security find-generic-password -a me",
            "security dump-keychain",
            f"cat {P.home}/Library/Keychains/login.keychain-db",
        )
        self.passes("security list-keychains")


class ShellGrammar(Cases):
    """Keywords and grouping must not hide a command."""

    def test_keywords_and_groups_do_not_hide_a_command(self) -> None:
        self.refused(
            "{ git push -f; }",
            "{ git push origin main; }",
            "if true; then git push -f; fi",
            "if git push -f; then echo no; fi",
            "if true; then echo a; else git reset --hard; fi",
            "if false; then :; elif true; then git push -f; fi",
            "for i in 1; do git push -f; done",
            "while true; do git push -f; done",
            "until false; do git push -f; done",
            "case x in x) git push -f;; esac",
            "! git push -f",
            "f() { git push -f; }; f",
            "function f { git push -f; }",
            "time { git push -f; }",
            "{ cat .env; }",
            "if true; then gh issue edit 5 --add-label state:ready; fi",
            "for i in 1; do rm -rf x; done",
            "{ git reset --hard; }",
        )

    def test_harmless_keyword_forms_pass(self) -> None:
        self.passes(
            "{ git status; }",
            "if true; then git push origin feature; fi",
            "for i in 1 2; do echo $i; done",
            "! git diff --quiet",
        )

    def test_env_split_string_is_judged(self) -> None:
        self.refused(
            "env -S 'git push -f'",
            "env --split-string='git push origin main'",
            "env -S 'FOO=1 git reset --hard'",
            "env -Sgit\\ push\\ -f",
            "env -i -S 'git push -f'",
        )
        self.passes("env -S 'git status'", "env --split-string='ls -l'")


class TrackedFolder(Cases):
    def test_cd_changes_where_a_relative_path_points(self) -> None:
        self.refused(
            f"cd {P.key_dir} && cat app-key.pem",
            f"cd {P.key_dir}; cat ./app-key.pem",
            f"cd {P.key_dir} && cat held-out/case1.txt",
            f"cd {P.data} && cat */app-key.pem",
            f"pushd {P.key_dir} && cat app-key.pem",
            f"cd {P.home}/.config/gh && cat hosts.yml",
            f"cd {P.root} && cat .env",
            f"cd {P.root}/.agents && cat ../.env",
            f"cd {P.key_dir} && cd held-out && cat case1.txt",
        )
        self.expect(f"cd {P.root} && cat .env", DENY, cwd=P.feature)

    def test_cd_to_a_harmless_folder_still_passes(self) -> None:
        self.passes(
            f"cd {P.feature} && cat README.md",
            f"cd {P.feature} && git status",
            f"cd {P.root}; cd {P.feature}; cat .env.example",
        )

    def test_cd_changes_which_branch_a_bare_push_names(self) -> None:
        self.expect(f"cd {P.root} && git push origin", DENY, cwd=P.feature)
        self.expect(f"cd {P.feature} && git push origin", ALLOW, cwd=P.root)

    def test_popd_returns(self) -> None:
        self.expect(f"pushd {P.root} && popd && cat .env.example", ALLOW, cwd=P.feature)


class RoundTwoFixes(Cases):
    """A redirect before the program, defaults in variables, and three small gaps."""

    def test_a_redirect_before_the_program_does_not_hide_it(self) -> None:
        self.refused(
            "2>&1 git push -f",
            "2>/dev/null rm -rf x",
            "<in git push origin main",
            "&>log gh issue edit 5 --add-label state:ready",
            "3>&- git reset --hard",
            "1>&2 git push -f",
            "{ 2>&1 git push -f; }",
            "if true; then 2>&1 git push -f; fi",
            "2>&1 cat .env",
        )

    def test_a_number_that_is_an_argument_stays_an_argument(self) -> None:
        self.passes(
            "echo 2 > out.txt",
            "2>&1 git status",
            "echo 2>&1 git push -f",
            "git log -n 2 > /dev/null",
        )

    def test_a_default_in_a_variable_is_expanded(self) -> None:
        key = P.key_dir.name
        self.refused(
            f"cat ${{NOPE_X:-{P.data}}}/{key}/app-key.pem",
            f"cat ${{NOPE_X-{P.data}}}/{key}/app-key.pem",
            f"cat ${{NOPE_X:={P.data}}}/{key}/app-key.pem",
            f"cat ${{AI_LOOP_KIT_DATA:-/x}}/{key}/app-key.pem",
            "cat ${HOME:-/x}/.config/gh/hosts.yml",
            f"cd ${{NOPE_X:-{P.key_dir}}} && cat app-key.pem",
        )
        self.passes("ls ${HOME:-/tmp}", f"cat ${{NOPE_X:-{P.feature}}}/README.md")

    def test_env_with_a_clustered_split_flag(self) -> None:
        self.refused(
            "env -iS 'git push -f'",
            "env -vS 'git push -f'",
            "env -iS'git reset --hard'",
        )
        self.passes("env -iS 'git status'")

    def test_gh_config_get_of_the_token(self) -> None:
        self.refused(
            "gh config get oauth_token",
            "gh config get -h github.com oauth_token",
            "gh config get oauth_token --host github.com",
            "gh config get --host github.com oauth_token",
        )
        self.passes("gh config get editor", "gh config list")

    def test_cd_dash_returns_to_the_last_folder(self) -> None:
        self.refused(
            f"cd {P.key_dir}; cd /tmp; cd -; cat app-key.pem",
            f"cd {P.key_dir} && cd {P.feature} && cd - && cat app-key.pem",
        )
        self.passes(f"cd {P.feature}; cd {P.key_dir}; cd -; cat app-key.pem")


class ReadsByVariableGlobOrTree(Cases):
    def test_a_variable_that_names_the_data_folder(self) -> None:
        key = P.key_dir.name
        self.refused(
            f"cat $AI_LOOP_KIT_DATA/{key}/app-key.pem",
            f"cat ${{AI_LOOP_KIT_DATA}}/{key}/app-key.pem",
            f'cat "$AI_LOOP_KIT_DATA/{key}/app-key.pem"',
            f"cat $AI_LOOP_KIT_DATA/{key}/held-out/case1.txt",
            f"cd $AI_LOOP_KIT_DATA/{key} && cat app-key.pem",
            f"D={P.data}; cat $D/{key}/app-key.pem",
            f"export D={P.data} && cat ${{D}}/{key}/app-key.pem",
            f"openssl rsa -in $AI_LOOP_KIT_DATA/{key}/app-key.pem",
        )

    def test_the_default_data_folder_when_the_variable_is_unset(self) -> None:
        env = {"HOME": str(P.home)}
        default = P.home / ".local" / "share" / "ai-loop-kit" / "k-0123456789ab"
        default.mkdir(parents=True, exist_ok=True)
        (default / "app-key.pem").write_text("x\n")
        for command in (
            f"cat {default}/app-key.pem",
            "cat $AI_LOOP_KIT_DATA/k-0123456789ab/app-key.pem",
            "cat ~/.local/share/ai-loop-kit/*/app-key.pem",
        ):
            with self.subTest(command=command):
                self.assertEqual(bash(command, env=env).kind, DENY, command)

    def test_xdg_and_gh_variables(self) -> None:
        env = dict(P.env, XDG_CONFIG_HOME=str(P.base / "xdg"), GH_CONFIG_DIR=str(P.base / "ghc"))
        for command in (
            "cat $XDG_CONFIG_HOME/gh/hosts.yml",
            "cat ${GH_CONFIG_DIR}/hosts.yml",
        ):
            with self.subTest(command=command):
                self.assertEqual(bash(command, env=env).kind, DENY, command)

    def test_a_glob(self) -> None:
        self.refused(
            f"cat {P.data}/*/app-key.pem",
            f"cat {P.data}/*/app-key.p*",
            f"cat {P.key_dir}/*",
            f"cat {P.key_dir}/held-out/*",
            f"cat {P.data}/*/held-*/case?.txt",
            "cat $AI_LOOP_KIT_DATA/*/*",
            f"cat {P.home}/.config/g?/*",
        )

    def test_a_recursive_read_of_a_parent_folder(self) -> None:
        self.refused(
            f"grep -r k {P.data}",
            f"grep -rn secret {P.key_dir}",
            f"grep -R k {P.data}/",
            f"grep --recursive k {P.data}",
            f"grep -d recurse k {P.data}",
            "grep -r k $AI_LOOP_KIT_DATA",
            f"rg k {P.data}",
            f"rg k {P.home}",
            f"grep -r token {P.home}/.config",
            "grep -r token ~",
            f"find {P.data} -exec cat {{}} +",
            f"find {P.data} -type f -exec cat {{}} \\;",
            f"find {P.home} -name hosts.yml -exec cat {{}} \\;",
            f"find {P.key_dir} -execdir head {{}} +",
            f"cp -r {P.data} out",
            f"tar cf out.tar {P.data}",
            f"cd {P.base} && grep -r k data",
            f"cd {P.data} && grep -r k .",
        )

    def test_the_search_tools_over_a_parent_folder(self) -> None:
        for name, keys in (("Grep", {"pattern": "k"}), ("Glob", {"pattern": "**/*"})):
            for folder in (P.data, P.home, P.home / ".config"):
                with self.subTest(tool=name, folder=str(folder)):
                    self.assertEqual(tool(name, dict(keys, path=str(folder))).kind, DENY)
        self.assertEqual(tool("Grep", {"pattern": "k", "path": str(P.feature)}).kind, ALLOW)

    def test_recursive_reads_of_ordinary_folders_pass(self) -> None:
        self.passes(
            "grep -r TODO .",
            f"grep -rn TODO {P.feature}",
            f"find {P.feature} -name '*.py' -exec cat {{}} +",
            f"find {P.home} -name notes.txt",
            "rg TODO kit",
            f"cp -r {P.feature} out",
        )


class GuardedWrites(Cases):
    def denied(self, name: str, path: Path, cwd: Path | None = None) -> None:
        with self.subTest(tool=name, path=str(path)):
            got = tool(name, {"file_path": str(path)}, cwd=cwd)
            self.assertEqual(got.kind, DENY, got.reason)
            self.assertTrue(got.reason)

    def test_file_tools_on_the_guards(self) -> None:
        for name in ("Edit", "Write", "MultiEdit"):
            self.denied(name, P.root / ".claude" / "settings.json")
            self.denied(name, P.root / ".claude" / "settings.local.json")
            self.denied(name, P.root / ".agents" / "pieces" / "3" / "record.jsonl")
            self.denied(name, P.root / ".agents" / "loop" / "policy.json")
            self.denied(name, P.root / ".github" / "workflows" / "ci.yml")
            self.denied(name, P.root / ".githooks" / "commit-msg")

    def test_the_same_files_in_a_worktree(self) -> None:
        self.denied("Edit", P.worktree / ".claude" / "settings.json", cwd=P.worktree)
        self.denied("Write", P.worktree / ".github" / "workflows" / "x.yml", cwd=P.worktree)
        self.denied("Write", P.root / ".agents" / "pieces" / "3" / "x", cwd=P.worktree)
        got = tool("NotebookEdit", {"notebook_path": str(P.root / ".claude/settings.json")})
        self.assertEqual(got.kind, DENY)

    def test_the_installed_kit_hooks(self) -> None:
        plugin = P.base / "plugin"
        (plugin / "hooks").mkdir(parents=True, exist_ok=True)
        env = dict(P.env, CLAUDE_PLUGIN_ROOT=str(plugin))
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(plugin / "hooks" / "guard.py")},
            "cwd": str(P.root),
        }
        self.assertEqual(guard.decide(payload, env).kind, DENY)

    def test_a_relative_path_is_read_from_the_session_folder(self) -> None:
        got = tool("Edit", {"file_path": ".claude/settings.json"})
        self.assertEqual(got.kind, DENY)

    def test_other_files_pass(self) -> None:
        for name in ("Edit", "Write"):
            for path in (
                P.root / "src" / "app.py",
                P.worktree / "src" / "app.py",
                P.root / ".claude" / "commands" / "x.md",
                P.root / ".agents" / "runs" / "night-1" / "handoff.json",
            ):
                with self.subTest(tool=name, path=str(path)):
                    self.assertEqual(tool(name, {"file_path": str(path)}).kind, ALLOW)

    def test_shell_writes_to_the_guards(self) -> None:
        self.refused(
            "echo '{}' > .claude/settings.json",
            "echo x >> .claude/settings.local.json",
            "printf x | tee .github/workflows/ci.yml",
            "sed -i s/a/b/ .claude/settings.json",
            "cp evil .githooks/commit-msg",
            "mv x .agents/loop/policy.json",
            "rm .agents/pieces/3/record.jsonl",
            "touch .agents/pieces/3/x",
            "chmod 777 .claude/settings.json",
            "dd if=x of=.claude/settings.json",
        )

    def test_shell_reads_of_the_guards_pass(self) -> None:
        self.passes(
            "cat .claude/settings.json",
            "ls .agents/pieces",
            "grep -r x .github/workflows",
            "git diff -- .claude/settings.json",
            "cp .claude/settings.json /tmp/copy.json",
        )


class Reasons(Cases):
    def test_every_refusal_names_the_next_step(self) -> None:
        for command in ("git push origin main", "rm -rf x", "git reset --hard", "gh auth token"):
            with self.subTest(command=command):
                got = bash(command)
                self.assertEqual(got.kind, DENY)
                self.assertIn("next:", got.reason)
                self.assertIn("another way", got.reason)


class MainFunction(unittest.TestCase):
    def run_main(self, payload: Any, raw: str | None = None) -> tuple[int, str, str]:
        import io

        out, err = io.StringIO(), io.StringIO()
        text = raw if raw is not None else json.dumps(payload)
        code = guard.main(io.StringIO(text), out, err, P.env)
        return code, out.getvalue(), err.getvalue()

    def payload(self, command: str) -> dict[str, Any]:
        return {
            "session_id": "s1",
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "cwd": str(P.root),
        }

    def test_a_refusal_exits_2_with_the_reason_on_standard_error(self) -> None:
        code, out, err = self.run_main(self.payload("git push origin main"))
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("main", err)

    def test_an_ask_prints_the_permission_decision(self) -> None:
        code, out, _ = self.run_main(self.payload("gh pr comment 5 -b hi"))
        self.assertEqual(code, 0)
        body = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(body["hookEventName"], "PreToolUse")
        self.assertEqual(body["permissionDecision"], "ask")
        self.assertTrue(body["permissionDecisionReason"])

    def test_a_pass_prints_nothing(self) -> None:
        self.assertEqual(self.run_main(self.payload("git status")), (0, "", ""))

    def test_input_that_is_not_json_fails_closed(self) -> None:
        for raw in ("not json", "", "[1, 2]", '"text"', "null", "{"):
            with self.subTest(raw=raw):
                code, out, err = self.run_main(None, raw=raw)
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn("next:", err)

    def test_a_missing_command_passes(self) -> None:
        payload = self.payload("")
        payload["tool_input"] = {}
        self.assertEqual(self.run_main(payload)[0], 0)

    def test_every_decision_reaches_the_log(self) -> None:
        log = P.root / ".agents" / "runs" / "night-1" / "commands.log"
        before = len(log.read_text().splitlines()) if log.exists() else 0
        self.run_main(self.payload("git push origin main"))
        self.run_main(self.payload("gh pr comment 5 -b hi"))
        self.run_main(self.payload("git status"))
        lines = [json.loads(x) for x in log.read_text().splitlines()[before:]]
        self.assertEqual([x["event"] for x in lines], ["refuse", "ask", "pass"])
        self.assertTrue(lines[0]["reason"])
        self.assertEqual(lines[2]["command"], "git status")


class CommandLog(unittest.TestCase):
    def folder(self) -> Path:
        project = Path(os.path.realpath(tempfile.mkdtemp())) / "demo"
        (project / ".git").mkdir(parents=True)
        return project

    def read(self, project: Path, run: str) -> list[dict[str, Any]]:
        path = project / ".agents" / "runs" / run / "commands.log"
        return [json.loads(x) for x in path.read_text().splitlines()]

    def test_a_line_is_json_with_the_fields_a_reader_needs(self) -> None:
        project = self.folder()
        env = {"AI_LOOP_KIT_RUN": "night-2", "HOME": str(project.parent)}
        command_log.record(
            {"session_id": "s9", "tool_name": "Bash", "cwd": str(project),
             "tool_input": {"command": "ls"}},
            "pass", "", env,
        )
        (line,) = self.read(project, "night-2")
        for key in ("time", "session", "event", "tool", "command", "cwd", "run", "retry"):
            self.assertIn(key, line)
        self.assertEqual(line["event"], "pass")
        self.assertEqual(line["run"], "night-2")
        self.assertEqual(line["retry"], 0)

    def test_a_repeat_in_the_same_session_counts_as_a_retry(self) -> None:
        project = self.folder()
        env = {"AI_LOOP_KIT_RUN": "night-3", "HOME": str(project.parent)}
        payload = {"session_id": "s9", "tool_name": "Bash", "cwd": str(project),
                   "tool_input": {"command": "make test"}}
        for _ in range(3):
            command_log.record(payload, "pass", "", env)
        other = dict(payload, session_id="s10")
        command_log.record(other, "pass", "", env)
        self.assertEqual([x["retry"] for x in self.read(project, "night-3")], [0, 1, 2, 0])

    def test_without_a_run_name_the_line_goes_to_attended(self) -> None:
        project = self.folder()
        env = {"HOME": str(project.parent)}
        payload = {"session_id": "s", "tool_name": "Bash", "cwd": str(project),
                   "tool_input": {"command": "ls"}}
        command_log.record(payload, "pass", "", env)
        self.assertEqual(self.read(project, "attended")[0]["run"], "attended")

    def test_a_bad_run_name_falls_back_to_attended(self) -> None:
        project = self.folder()
        env = {"HOME": str(project.parent), "AI_LOOP_KIT_RUN": "../escape"}
        payload = {"session_id": "s", "tool_name": "Bash", "cwd": str(project),
                   "tool_input": {"command": "ls"}}
        command_log.record(payload, "pass", "", env)
        self.assertEqual(self.read(project, "attended")[0]["run"], "attended")
        self.assertFalse((project.parent / "escape").exists())

    def test_a_worktree_session_writes_to_the_main_folders_run(self) -> None:
        env = dict(P.env, AI_LOOP_KIT_RUN="night-4")
        payload = {"session_id": "s", "tool_name": "Bash", "cwd": str(P.worktree),
                   "tool_input": {"command": "ls"}}
        command_log.record(payload, "pass", "", env)
        self.assertEqual(self.read(P.root, "night-4")[0]["cwd"], str(P.worktree))

    def test_secrets_are_scrubbed_before_they_are_written(self) -> None:
        project = self.folder()
        env = {"AI_LOOP_KIT_RUN": "night-5", "HOME": str(project.parent)}
        secret = "ghp_" + "a" * 36
        command = f"curl -H 'Authorization: token {secret}' x; API_KEY=hunter2 run"
        payload = {"session_id": "s", "tool_name": "Bash", "cwd": str(project),
                   "tool_input": {"command": command}}
        command_log.record(payload, "pass", "", env)
        text = (project / ".agents/runs/night-5/commands.log").read_text()
        self.assertNotIn(secret, text)
        self.assertNotIn("hunter2", text)

    def test_a_long_command_is_cut(self) -> None:
        project = self.folder()
        env = {"AI_LOOP_KIT_RUN": "night-6", "HOME": str(project.parent)}
        payload = {"session_id": "s", "tool_name": "Bash", "cwd": str(project),
                   "tool_input": {"command": "echo " + "x" * 10000}}
        command_log.record(payload, "pass", "", env)
        self.assertLess(len(self.read(project, "night-6")[0]["command"]), 3000)

    def test_the_log_hook_records_what_ran_and_what_failed(self) -> None:
        import io

        project = self.folder()
        env = {"AI_LOOP_KIT_RUN": "night-7", "HOME": str(project.parent)}
        base = {"session_id": "s", "tool_name": "Bash", "cwd": str(project),
                "tool_input": {"command": "make test"}}
        ran = dict(base, hook_event_name="PostToolUse", tool_response={"interrupted": False})
        failed = dict(base, hook_event_name="PostToolUseFailure", error="exit 2")
        for payload in (ran, failed):
            code = command_log.main(io.StringIO(json.dumps(payload)), io.StringIO(), env)
            self.assertEqual(code, 0)
        events = [x["event"] for x in self.read(project, "night-7")]
        self.assertEqual(events, ["ran", "failed"])

    def test_the_log_hook_never_blocks(self) -> None:
        import io

        self.assertEqual(command_log.main(io.StringIO("not json"), io.StringIO(), {}), 0)
        self.assertEqual(command_log.main(io.StringIO("{}"), io.StringIO(), {}), 0)

    def test_a_log_that_cannot_be_written_does_not_stop_the_guard(self) -> None:
        project = self.folder()
        (project / ".agents").write_text("a file where a folder should be\n")
        env = {"AI_LOOP_KIT_RUN": "night-8", "HOME": str(project.parent)}
        payload = {"session_id": "s", "tool_name": "Bash", "cwd": str(project),
                   "tool_input": {"command": "ls"}}
        command_log.record(payload, "pass", "", env)


class HookBypasses(Cases):
    """Ways to switch off the git hooks, or to hide a command behind a name."""

    def test_the_refused_spellings(self) -> None:
        self.refused(
            "git commit --no-verify -m x",
            "git commit -m x --no-verify",
            "git commit -n -m x",
            "git commit -nm x",
            "git -C . commit --no-verify -m x",
            "git config core.hooksPath /tmp/none",
            "git config --global core.hooksPath /tmp/none",
            "git config --unset core.hooksPath",
            "git -c core.hooksPath=/tmp/none commit -m x",
            "git config alias.st status",
            "git config --global alias.p 'push origin main'",
        )

    def test_the_spellings_that_pass(self) -> None:
        self.passes(
            "git commit -m x",
            "git commit -am 'fix the name'",
            "git config --get core.hooksPath",
            "git config user.name Someone",
            "git config --get alias.st",
        )


if __name__ == "__main__":
    unittest.main()
