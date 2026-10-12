#!/usr/bin/env python3
# contract: agent
# contract: changes-state
"""setup.py: the steps behind the first half of /setup, decided by what is on disk.

    setup.py preflight
    setup.py found [--language L] [--test-command CMD] [--billing-mode M] ...
    setup.py first-piece
    setup.py github labels
    setup.py github issue --title TEXT --body-file FILE

`found` checks the tools, then writes what a project needs to shape and run
locally. It never overwrites a file. A file that is already there is kept, and a
settings file is merged with `merge-settings.py`, so the person's rules stay. The
kit runs from its plugin folder, so nothing of the kit is copied into the project.

`first-piece` captures the first piece locally, on the quick path: a scaffold and a
test runner. `github` steps go through the gate and never through `gh` directly.
Before the gate's GitHub App exists, the gate queues the write and the `next:` line
names the command for the person to run.

The GitHub App is not made here. It comes in the second half of /setup.

Run it again and nothing changes. A missing nice-to-have answer becomes an open
question in `docs/open-questions.md`. It never stops founding.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop import bootstrap, cli, github, policy, states, versions
from loop.paths import PathError, Paths, find_project_root

PROG = "setup.py"
HERE = Path(__file__).resolve().parent
LANGUAGES = ("node", "python", "go", "rust", "ruby")
MARKERS = {
    "node": ("package.json",),
    "python": ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile"),
    "go": ("go.mod",),
    "rust": ("Cargo.toml",),
    "ruby": ("Gemfile",),
}
TEST_COMMANDS = {
    "node": "npm test",
    "python": "python3 -m unittest discover",
    "go": "go test ./...",
    "rust": "cargo test",
    "ruby": "bundle exec rake test",
}
CLOSING = (
    "The first half of /setup is done: you can shape and run locally. The GitHub App "
    "comes in the second half of /setup. Until then the gate queues its GitHub writes "
    "for you to send, and an unattended run or a pre-approved merge is refused."
)
FREE_PLAN_WARNING = (
    "This repository is private on the free plan, so GitHub gives it no server-side "
    "rules: no branch protection, no required checks and no merge queue. The local "
    "guards carry every rule here."
)
OPEN_QUESTIONS = "docs/open-questions.md"


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise cli.Failure(
            f"cannot load {path}",
            next_command="reinstall the kit, then run setup.py again",
            code=cli.ExitCode.ENVIRONMENT,
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# --- reading the project ----------------------------------------------------------


def project_root(start: str) -> Path:
    try:
        return find_project_root(Path(start))
    except PathError as error:
        raise cli.Failure(
            str(error),
            next_command="cd into the project, then run setup.py again",
            code=cli.ExitCode.REFUSED,
        ) from error


def git_out(root: Path, *args: str) -> str | None:
    done = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    return done.stdout.strip() if done.returncode == 0 else None


def check_tooling(root: Path) -> bool:
    """Stop with the install line when a tool the kit needs is missing.

    Returns True when origin is the kit's own repository. One rule says so: the
    exact-name rule of check-tooling.sh, which exits 3 under --for-run.
    """
    done = subprocess.run(
        ["sh", str(HERE / "check-tooling.sh"), "--for-run"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        stdin=subprocess.DEVNULL,
    )
    if done.returncode == 0:
        return False
    if done.returncode == 3:
        return True
    missing = [
        line.split(" is missing")[0]
        for line in done.stdout.splitlines()
        if " is missing:" in line and line.split(" is missing")[0] in ("Git", "python3", "openssl")
    ]
    names = [name.lower() for name in missing] or ["the missing tool"]
    raise cli.Failure(
        "a tool the kit needs is missing: " + ", ".join(names) + ". Nothing was written",
        next_command=(
            "install "
            + ", ".join(names)
            + " (on macOS: brew install "
            + " ".join(names)
            + "), then run /setup again"
        ),
        code=cli.ExitCode.ENVIRONMENT,
        data={"missing": names},
    )


def preflight_next(root: Path) -> str:
    return (f"python3 {shlex.quote(str(HERE / 'setup.py'))} preflight "
            f"--project {shlex.quote(str(root))}")


def origin_git(root: Path, arguments: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    """Read Git with bounded non-interactive execution and private diagnostics."""
    command = ["git", "-C", str(root), *arguments]
    environment = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, env=environment,
                                   start_new_session=True)
        try:
            output, _ = process.communicate(timeout=timeout)
        except BaseException:
            # This session contains only the Git operation we started and its helpers.
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()
                process.wait(timeout=5)
            raise
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as error:
        raise cli.Failure(
            "origin main could not be verified; the Git operation failed or timed out",
            next_command=preflight_next(root), code=cli.ExitCode.ENVIRONMENT,
        ) from error
    assert process.returncode is not None
    return subprocess.CompletedProcess(command, process.returncode, output)


def check_origin(root: Path, is_kit: bool) -> None:
    origin = git_out(root, "remote", "get-url", "origin")
    project = shlex.quote(str(root))
    if not origin:
        raise cli.Failure(
            "this project has no origin; supply your repository address, then run /setup again",
            next_command=("printf '%s' 'Your repository address: ' && "
                          "IFS= read -r field_origin_address && "
                          'test -n "$field_origin_address" && '
                          f'git -C {project} remote add -- origin "$field_origin_address"'),
            code=cli.ExitCode.REFUSED,
        )
    if is_kit:
        raise cli.Failure(
            "origin is the kit's own repository, so a run would push there. Nothing was "
            "changed",
            next_command=("printf '%s' 'Your repository address: ' && "
                          "IFS= read -r field_origin_address && "
                          'test -n "$field_origin_address" && '
                          f'git -C {project} remote set-url -- origin "$field_origin_address"'),
            code=cli.ExitCode.REFUSED,
        )
    retry = preflight_next(root)
    advertised = origin_git(root, ["ls-remote", "--exit-code", "--heads", "origin",
                                   "refs/heads/main"], 20)
    if advertised.returncode == 2 and not advertised.stdout:
        push = f"git -C {project} push origin HEAD:refs/heads/main"
        if git_out(root, "rev-parse", "--verify", "HEAD"):
            command = push
            message = "origin has no main commit; the person must publish current local history"
        else:
            command = (f"git -C {project} commit --allow-empty --only "
                       f"-m 'Initial repository commit' && {push}")
            message = ("origin has no main commit; the person must create and push "
                       "an empty first commit")
        raise cli.Failure(message, next_command=command, code=cli.ExitCode.REFUSED)
    lines = advertised.stdout.splitlines()
    if advertised.returncode != 0 or len(lines) != 1:
        raise cli.Failure("origin main could not be verified", next_command=retry,
                          code=cli.ExitCode.REFUSED)
    match = re.fullmatch(r"([0-9a-f]{40})\trefs/heads/main", lines[0])
    if match is None:
        raise cli.Failure(
            "origin main advertisement is malformed or uses an unsupported object ID",
            next_command=retry, code=cli.ExitCode.REFUSED,
        )
    commit = match.group(1)
    try:
        with tempfile.TemporaryDirectory(prefix="setup-origin-main-") as temporary:
            scratch = Path(temporary)
            initialised = origin_git(scratch, ["init", "--quiet", "--object-format=sha1"], 5)
            if initialised.returncode != 0:
                raise cli.Failure("temporary main verification could not start",
                                  next_command=retry, code=cli.ExitCode.ENVIRONMENT)
            fetched = origin_git(scratch, ["fetch", "--no-tags", "--no-write-fetch-head",
                                           "--depth=1", "--", origin, commit], 30)
            if fetched.returncode != 0:
                raise cli.Failure("origin main commit could not be retrieved",
                                  next_command=retry, code=cli.ExitCode.REFUSED)
            inspected = origin_git(scratch, ["cat-file", "-t", commit], 5)
            if inspected.returncode != 0 or inspected.stdout.strip() != "commit":
                raise cli.Failure("origin main does not have a verified commit object",
                                  next_command=retry, code=cli.ExitCode.REFUSED)
    except OSError as error:
        raise cli.Failure("temporary main verification could not complete",
                          next_command=retry, code=cli.ExitCode.ENVIRONMENT) from error


def step_preflight(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root(args.project)
    check_origin(root, check_tooling(root))
    return {"origin_main": "verified commit", "read_only": True}


def detect_language(root: Path) -> str | None:
    for language, names in MARKERS.items():
        if any((root / name).exists() for name in names):
            return language
    return None


def project_has_runner(root: Path) -> bool:
    """True when the project's HEAD already holds a test runner. The ready gate's own rule."""
    from loop.gates import ready

    try:
        return bool(ready.has_test_runner(root, "HEAD"))
    except ready.GitError:
        return False


def kit_ref(kit: Path, given: str) -> str:
    """Select a release tag or an already verified full SHA, never a branch."""
    return versions.request(kit, given)


# --- writing, never overwriting ---------------------------------------------------


class Plan:
    """What founding did, or would do under --dry-run."""

    def __init__(self, root: Path, dry_run: bool) -> None:
        self.root = root
        self.dry_run = dry_run
        self.created: list[str] = []
        self.kept: list[str] = []
        self.extended: list[str] = []
        self.warnings: list[str] = []
        self.asks: list[str] = []
        self.open_questions: list[str] = []

    def place(self, relative: str, text: str, *, executable: bool = False) -> bool:
        """Write a file that is not there. A file that is there stays as it is."""
        target = self.root / relative
        if target.exists() or target.is_symlink():
            self.kept.append(relative)
            return False
        self.created.append(relative)
        if not self.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            if executable:
                target.chmod(0o755)
        return True


def extend_ignore(plan: Plan, template: str) -> None:
    """Add the template's patterns that the project's ignore file lacks, after its own."""
    target = plan.root / ".gitignore"
    if not target.exists():
        plan.place(".gitignore", template)
        return
    have = {line.strip() for line in target.read_text("utf-8").splitlines()}
    wanted = [
        line for line in template.splitlines() if line.strip() and not line.startswith("#")
    ]
    missing = [line for line in wanted if line.strip() not in have]
    if not missing:
        return
    plan.extended.append(".gitignore")
    if not plan.dry_run:
        old = target.read_text("utf-8")
        gap = "" if old.endswith("\n") or not old else "\n"
        block = "\n# Added by the kit's setup: records and settings that belong to this computer.\n"
        target.write_text(old + gap + block + "\n".join(missing) + "\n", encoding="utf-8")


def prepare_settings(root: Path, kit: Path, merge: Any) -> dict[str, Any]:
    """Render and merge settings without creating files or directories."""
    target = root / ".claude/settings.json"
    template = json.loads(merge.render(
        (kit / "templates/claude-settings.json").read_text("utf-8"),
        {"KIT_DIR": str(kit)},
    ))
    existed = target.exists()
    if existed:
        try:
            mine = json.loads(target.read_text("utf-8"))
        except ValueError as error:
            raise cli.Failure(
                f"{target} is not valid JSON ({error}), so it was left as it is",
                next_command=f"fix {target}, then run merge-settings.py again",
                code=cli.ExitCode.REFUSED,
            ) from error
        if not isinstance(mine, dict):
            raise cli.Failure(
                f"{target} is not a JSON object, so it was left as it is",
                next_command=f"fix {target}, then run merge-settings.py again",
                code=cli.ExitCode.REFUSED,
            )
    else:
        mine = {}
    added: list[str] = []
    overridden: list[str] = []
    merged = merge.merge(mine, template, added, overridden=overridden)
    return {"text": json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
            "added": added, "overridden": overridden, "existed": existed,
            "mode": target.stat().st_mode & 0o777 if existed else 0o644}


def place_settings(plan: Plan, prepared: dict[str, Any]) -> None:
    relative = ".claude/settings.json"
    target = plan.root / relative
    if prepared["added"]:
        if not plan.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=target.parent,
                prefix=".merge-settings.", delete=False,
            ) as pending:
                pending.write(prepared["text"])
                temporary = Path(pending.name)
            try:
                temporary.chmod(prepared["mode"])
                os.replace(temporary, target)
            finally:
                if temporary.exists():
                    temporary.unlink()
        if prepared["existed"]:
            plan.extended.append(relative)
        else:
            plan.created.append(relative)
    else:
        plan.kept.append(relative)
    for line in prepared["overridden"]:
        print(f"merge-settings.py: your value beats the kit's guard value at {line}",
              file=sys.stderr)
        plan.warnings.append(f"your own setting beats a kit guard at {line}")


def build_policy(kit: Path, args: argparse.Namespace, mode: str, has_runner: bool) -> str:
    data = json.loads((kit / "templates" / "policy.json").read_text("utf-8"))
    data["billing"]["mode"] = mode
    if args.spend_cap_piece is not None:
        data["billing"]["spend_cap_per_piece_usd"] = args.spend_cap_piece
    if args.spend_cap_run is not None:
        data["billing"]["spend_cap_per_run_usd"] = args.spend_cap_run
    # With no test runner the policy holds no command. The first piece carries it as its
    # Command, and the scaffold's own change sets the policy. A command in the policy
    # would make the ready gate treat the empty project as one with a runner.
    if args.test_command and has_runner:
        data["test_command"] = args.test_command
    return json.dumps(data, indent=2) + "\n"


def render_allowlist(kit: Path, language: str | None) -> str:
    hosts: list[str] = []
    if language:
        text = (kit / "templates" / "network-allowlist" / f"{language}.txt").read_text("utf-8")
        hosts = [x.strip() for x in text.splitlines() if x.strip() and not x.startswith("#")]
    body = {"language": language, "allowedDomains": hosts}
    return json.dumps(body, indent=2) + "\n"


def write_open_questions(plan: Plan) -> None:
    if not plan.open_questions:
        return
    lines = [
        "# Open questions",
        "",
        "Founding asks no one twice. Each line is a question still open.",
        "",
    ]
    lines += [f"- {question}" for question in plan.open_questions]
    plan.place(OPEN_QUESTIONS, "\n".join(lines) + "\n")


def label_step(root: Path) -> dict[str, Any]:
    """The gate's label names and the command that creates them. Nothing is written."""
    return {
        "names": [row[0] for row in states.LABELS],
        "next": github.sync_command(root) + " (sync creates the labels once a write is queued)",
    }


def render_hook(kit: Path, merge: Any) -> str:
    """Validate and render the hook before publication or project writes."""
    raw = (kit / "templates" / "githooks" / "pre-push").read_text("utf-8")
    if any(char in str(kit) for char in '"$`\\\n'):
        raise cli.Failure(
            f"the kit folder {kit} holds a character that cannot go into the pre-push hook",
            next_command="move the kit to a folder with a plain name, then run /setup again",
            code=cli.ExitCode.ENVIRONMENT,
        )
    return str(merge.render(raw, {"KIT_DIR": str(kit)}))


def install_hooks(plan: Plan, kit: Path, template: str) -> None:
    hook = plan.root / ".githooks" / "pre-push"
    existed = hook.exists()
    plan.place(".githooks/pre-push", template, executable=True)
    if existed and hook.read_text("utf-8") != template:
        plan.warnings.append(
            ".githooks/pre-push is yours and differs from the kit's, so it was kept. The "
            "pre-run check refuses a run until the kit's secret scan is in it. Merge the "
            f"two by hand, or compare with {kit / 'templates' / 'githooks' / 'pre-push'}"
        )
    current = git_out(plan.root, "config", "--get", "core.hooksPath")
    if current == ".githooks":
        return
    if current:
        plan.warnings.append(
            f"core.hooksPath is {current}, not .githooks, so Git does not run the kit's "
            "pre-push hook. Point it at .githooks, or move the hook into yours"
        )
    elif not plan.dry_run:
        subprocess.run(
            ["git", "-C", str(plan.root), "config", "core.hooksPath", ".githooks"],
            check=True,
            capture_output=True,
        )


def write_kit_record(kit: Path, root: Path, dry_run: bool,
                     prepared: versions.Prepared | None = None) -> str:
    """Publish the verified release baseline in the stable machine-local home."""
    release = prepared or versions.prepare(kit, root, dry_run=dry_run)
    return versions.publish(release)


# --- the steps --------------------------------------------------------------------


def step_found(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root(args.project)
    kit = Path(args.kit_dir).resolve() if args.kit_dir else HERE.parent
    check_origin(root, check_tooling(root))
    plan = Plan(root, bool(getattr(args, "dry_run", False)))
    templates = kit / "templates"
    try:
        development = bool(getattr(args, "development", False))
        selected = args.kit_ref if development else kit_ref(kit, args.kit_ref)
        release = versions.prepare(kit, root, selected, dry_run=plan.dry_run,
                                   development=development)
        versions.check_foundation_selection(root, release.commit, development=development)
    except versions.VersionError as error:
        raise cli.Failure(str(error), next_command=error.next_command,
                          code=cli.ExitCode.REFUSED) from error
    merge = load_module("merge_settings", HERE / "merge-settings.py")
    values = {"KIT_DIR": str(kit), "KIT_REF": release.commit}

    def rendered(name: str) -> str:
        return str(merge.render((templates / name).read_text("utf-8"), values))

    language = args.language or detect_language(root)
    values["SCAFFOLD_TEST_COMMAND"] = json.dumps(
        args.test_command or TEST_COMMANDS.get(str(language), "")
    )
    if language is None:
        plan.open_questions.append(
            "Which language is this project written in? The network allowlist is empty until "
            "it is known. Run setup.py found --language <name>."
        )
    keyed = bool(os.environ.get("ANTHROPIC_API_KEY"))
    mode = args.billing_mode or ("api_key" if keyed else "subscription")
    if not args.test_command:
        plan.open_questions.append(
            "What command runs every test? The policy's test_command is empty until it is "
            "known, and the first piece sets up the test runner."
        )

    foundation = (
        ("AGENTS.md", "AGENTS.md"),
        ("CLAUDE.md", "CLAUDE.md"),
        ("overview.md", "docs/overview.md"),
        ("docs-README.md", "docs/README.md"),
        ("area-map", "docs/area-map"),
        ("CHANGELOG.md", "CHANGELOG.md"),
        ("checks.yml", ".github/workflows/checks.yml"),
        ("blocked-commands.md", ".agents/guard/blocked-commands.md"),
    )
    # Read and render every foundation input before publishing or changing the project.
    rendered_hook = render_hook(kit, merge)
    rendered_files = [(target, rendered(source)) for source, target in foundation]
    if development:
        development_files = []
        for target, text in rendered_files:
            if target == ".github/workflows/checks.yml":
                text = versions.DEVELOPMENT_MARKER + "\n" + text
            development_files.append((target, text))
        rendered_files = development_files
        plan.warnings.append(
            f"This is a development kit at {release.commit}, not a tagged release."
        )
    workflow = next(text for target, text in rendered_files
                    if target == ".github/workflows/checks.yml")
    if re.search(r"\{\{(?:KIT_[A-Z_]+|SCAFFOLD_TEST_COMMAND)\}\}", workflow):
        raise cli.Failure("the generated check has unresolved distribution placeholders",
                          next_command="reinstall the tagged kit release, then run setup.py found",
                          code=cli.ExitCode.REFUSED)
    prepared_settings = prepare_settings(root, kit, merge)
    rendered_policy = build_policy(kit, args, mode, project_has_runner(root))
    rendered_allowlist = render_allowlist(kit, language)
    ignore_template = (templates / "gitignore").read_text("utf-8")
    ignore_target = root / ".gitignore"
    if ignore_target.exists():
        ignore_target.read_text("utf-8")
    existing_hook = root / ".githooks/pre-push"
    if existing_hook.exists():
        existing_hook.read_text("utf-8")
    try:
        record = write_kit_record(kit, root, plan.dry_run, release)
    except versions.VersionError as error:
        raise cli.Failure(str(error), next_command=error.next_command,
                          code=cli.ExitCode.REFUSED) from error
    for target, text in rendered_files:
        plan.place(target, text)
    extend_ignore(plan, ignore_template)
    place_settings(plan, prepared_settings)
    install_hooks(plan, kit, rendered_hook)
    plan.place(".agents/loop/policy.json", rendered_policy)
    plan.place(".agents/loop/network-allowlist.json", rendered_allowlist)

    if mode == "api_key":
        for key, given in (
            ("spend_cap_per_piece_usd", args.spend_cap_piece),
            ("spend_cap_per_run_usd", args.spend_cap_run),
        ):
            if given is None:
                plan.asks.append(key)
    if args.repo_visibility == "private" and args.plan == "free":
        plan.warnings.append(FREE_PLAN_WARNING)
    if not args.repo_visibility or not args.plan:
        plan.asks.append(
            "repo_visibility and plan, to say whether the repository has server-side rules"
        )

    write_open_questions(plan)
    labels = label_step(root)
    return {
        "project": str(root),
        "kit_dir": str(kit),
        "language": language,
        "billing_mode": mode,
        "created": plan.created,
        "kept": plan.kept,
        "extended": plan.extended,
        "warnings": plan.warnings,
        "asks": plan.asks,
        "open_questions": plan.open_questions,
        "labels": labels,
        "kit_record": record,
        "kit_revision": release.commit,
        "kit_mode": "development" if development else "release",
        "kit_version": release.body.get("version"),
        "closing": CLOSING,
    }


def run_gate(root: Path, kit: Path, *argv: str) -> dict[str, Any]:
    """Start the gate. This is the only road to GitHub: setup.py never starts gh."""
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = str(kit)
    done = subprocess.run(
        [sys.executable, str(kit / "scripts" / "gate.py"), *argv, "--json"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env=env,
        stdin=subprocess.DEVNULL,
    )
    try:
        body = json.loads(done.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        body = {}
    if done.returncode != 0:
        try:
            code = cli.ExitCode(done.returncode)
        except ValueError:
            code = cli.ExitCode.FAILURE
        raise cli.Failure(
            str(body.get("error") or done.stderr.strip() or "the gate failed"),
            next_command=str(body.get("next") or "run gate.py --help"),
            code=code,
        )
    return dict(body)


def step_github(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root(args.project)
    kit = Path(args.kit_dir).resolve() if args.kit_dir else HERE.parent
    if args.what == "labels":
        reply = run_gate(root, kit, "labels", "--create", *(["--dry-run"] if args.dry_run else []))
        return {"gate": reply}
    reply = run_gate(
        root,
        kit,
        "capture",
        "--title",
        args.title,
        "--body-file",
        args.body_file,
        *(["--dry-run"] if args.dry_run else []),
    )
    if reply.get("github") == "queued" and reply.get("next"):
        sys.stderr.write(f"next: {reply['next']}\n")
    return {"gate": reply, "next": reply.get("next", "")}


def add_open_question(root: Path, text: str, *, dry_run: bool) -> None:
    """Add one line to docs/open-questions.md, once. Make the file when it is absent."""
    target = root / OPEN_QUESTIONS
    line = f"- {text}\n"
    if dry_run:
        return
    if target.exists():
        old = target.read_text("utf-8")
        if text in old:
            return
        target.write_text(old + ("" if old.endswith("\n") else "\n") + line, encoding="utf-8")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    head = "# Open questions\n\nFounding asks no one twice. Each line is a question still open.\n\n"
    target.write_text(head + line, encoding="utf-8")


def first_piece_body(kit: Path, command: str) -> str:
    """The first piece's text, from the kit's template. The spec format has one home."""
    merge = load_module("merge_settings", HERE / "merge-settings.py")
    text = (kit / "templates" / "first-piece.md").read_text("utf-8")
    return str(merge.render(text, {"TEST_COMMAND": command}))


def sync_scaffold_command(root: Path, command: str, *, dry_run: bool) -> None:
    """Keep the generated bootstrap entry aligned with the first piece's judge.

    Only this named entry belongs to the kit. Preserve every other byte of the
    workflow, including changes the person has not committed. A custom workflow
    without the entry stays as it is.
    """
    workflow = root / ".github" / "workflows" / "checks.yml"
    if not workflow.exists():
        return
    text = workflow.read_bytes().decode("utf-8")
    prefix = "          SCAFFOLD_TEST_COMMAND: "
    lines = text.splitlines(keepends=True)
    entries = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    if not entries:
        return
    if len(entries) != 1:
        raise cli.Failure(
            "checks.yml has more than one scaffold command entry",
            next_command="keep one SCAFFOLD_TEST_COMMAND entry in checks.yml, then try again",
            code=cli.ExitCode.REFUSED,
        )
    index = entries[0]
    newline = "\r\n" if lines[index].endswith("\r\n") else (
        "\n" if lines[index].endswith("\n") else ""
    )
    lines[index] = prefix + json.dumps(command) + newline
    updated = "".join(lines)
    if not dry_run and updated != text:
        workflow.write_bytes(updated.encode("utf-8"))


def step_first_piece(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root(args.project)
    kit = Path(args.kit_dir).resolve() if args.kit_dir else HERE.parent
    paths = Paths.for_project(root, kit_folder=kit)
    existing = sorted(
        int(p.name) for p in paths.pieces_dir.glob("*") if p.is_dir() and p.name.isdigit()
    ) if paths.pieces_dir.is_dir() else []
    if existing:
        return {"captured": False, "piece": existing[0], "reason": "a piece is already captured"}
    command = ""
    try:
        command = str(policy.read(paths.policy_file).get("test_command", ""))
    except policy.PolicyError:
        command = ""
    language = None
    allow = root / ".agents" / "loop" / "network-allowlist.json"
    if allow.exists():
        try:
            language = json.loads(allow.read_text("utf-8")).get("language")
        except ValueError:
            language = None
    command = args.test_command or command or TEST_COMMANDS.get(str(language), "")
    if not command:
        note = (
            "What command runs every test? The first piece cannot be captured until it is "
            "known."
        )
        add_open_question(root, note, dry_run=args.dry_run)
        raise cli.Failure(
            "no test command is known, so the first piece has no judge command",
            next_command="python3 " + shlex.quote(str(HERE / "setup.py"))
            + ' first-piece --test-command "<the command that runs every test>"',
            code=cli.ExitCode.REFUSED,
        )
    sync_scaffold_command(root, command, dry_run=args.dry_run)
    bootstrap.check(root, command)
    with tempfile.TemporaryDirectory() as folder:
        body = Path(folder) / "first-piece.md"
        body.write_text(first_piece_body(kit, command), encoding="utf-8")
        if args.dry_run:
            return {"captured": False, "piece": None, "dry_run_body": str(command)}
        reply = run_gate(
            root,
            kit,
            "capture",
            "--title",
            "Scaffold the project and its test runner",
            "--body-file",
            str(body),
        )
    return {"captured": True, "piece": reply.get("piece"), "gate": reply}


# --- the command ------------------------------------------------------------------


def _common(command: argparse.ArgumentParser) -> None:
    command.add_argument("--project", default=".", help="a folder inside the project")
    command.add_argument(
        "--kit-dir", default="", help="the installed kit folder (default: this script's)"
    )
    command.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                         help="print JSON on standard output")
    command.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS,
                         help="say what would change, and change nothing")


def setup(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    preflight = commands.add_parser("preflight", help="check tooling, origin and remote main")
    _common(preflight)
    found = commands.add_parser("found", help="write the foundation, never overwriting")
    _common(found)
    found.add_argument("--language", choices=LANGUAGES, default="")
    found.add_argument("--test-command", default="", help="the command that runs every test")
    found.add_argument("--billing-mode", choices=policy.BILLING_MODES, default="")
    found.add_argument("--spend-cap-piece", type=float, default=None, help="dollars for a piece")
    found.add_argument("--spend-cap-run", type=float, default=None, help="dollars for a run")
    found.add_argument("--repo-visibility", choices=("private", "public"), default="")
    found.add_argument("--plan", choices=("free", "paid"), default="")
    found.add_argument("--kit-ref", default="", help="the kit version checks.yml fetches")
    found.add_argument("--development", action="store_true",
                       help="verify a development kit against an explicit full public commit SHA")
    first = commands.add_parser("first-piece", help="capture the first piece locally")
    _common(first)
    first.add_argument("--test-command", default="", help="the command that runs every test")
    gh = commands.add_parser("github", help="a GitHub step, through the gate")
    gh_what = gh.add_subparsers(dest="what", required=True, metavar="step")
    labels = gh_what.add_parser("labels", help="create the gate's labels")
    _common(labels)
    issue = gh_what.add_parser("issue", help="file an idea as a piece")
    _common(issue)
    issue.add_argument("--title", required=True)
    issue.add_argument("--body-file", required=True)


def handler(args: argparse.Namespace) -> dict[str, Any]:
    args.dry_run = bool(getattr(args, "dry_run", False))
    if args.command == "preflight":
        return step_preflight(args)
    if args.command == "found":
        return step_found(args)
    if args.command == "first-piece":
        return step_first_piece(args)
    return step_github(args)


def main(argv: list[str]) -> int:
    return cli.run(
        PROG,
        "The steps behind the first half of /setup: found a project, capture its first piece.",
        setup,
        handler,
        argv,
        changes_state=True,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
