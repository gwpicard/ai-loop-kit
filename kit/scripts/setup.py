#!/usr/bin/env python3
# contract: agent
# contract: changes-state
"""setup.py: the steps behind the first half of /setup, decided by what is on disk.

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
import importlib.util
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop import cli, github, policy, states
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


def check_origin(root: Path, is_kit: bool) -> None:
    origin = git_out(root, "remote", "get-url", "origin")
    if not origin:
        raise cli.Failure(
            "this project has no origin, so there is no repository to shape and run against",
            next_command=f"git -C {shlex.quote(str(root))} remote add origin <the address of "
            "your own repository>, then run /setup again",
            code=cli.ExitCode.REFUSED,
        )
    if is_kit:
        raise cli.Failure(
            "origin is the kit's own repository, so a run would push there. Nothing was "
            "changed",
            next_command=f"git -C {shlex.quote(str(root))} remote set-url origin <the address of "
            "your own repository>, then run /setup again",
            code=cli.ExitCode.REFUSED,
        )


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


def kit_ref(kit: Path, given: str) -> str | None:
    if given:
        return given
    try:
        manifest = json.loads((kit / ".claude-plugin" / "plugin.json").read_text("utf-8"))
        version = manifest.get("version")
        return str(version) if version else None
    except (OSError, ValueError):
        return None


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


def place_settings(plan: Plan, kit: Path) -> None:
    merge = load_module("merge_settings", HERE / "merge-settings.py")
    result = merge.handler(
        argparse.Namespace(
            template=str(kit / "templates" / "claude-settings.json"),
            target=str(plan.root / ".claude" / "settings.json"),
            set=[f"KIT_DIR={kit}"],
            dry_run=plan.dry_run,
        )
    )
    relative = ".claude/settings.json"
    if result["added"]:
        if (plan.root / relative).exists():
            plan.extended.append(relative)
        else:
            plan.created.append(relative)
    else:
        plan.kept.append(relative)
    for line in result["overridden"]:
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


def place_allowlist(plan: Plan, kit: Path, language: str | None) -> None:
    hosts: list[str] = []
    if language:
        text = (kit / "templates" / "network-allowlist" / f"{language}.txt").read_text("utf-8")
        hosts = [x.strip() for x in text.splitlines() if x.strip() and not x.startswith("#")]
    body = {"language": language, "allowedDomains": hosts}
    plan.place(".agents/loop/network-allowlist.json", json.dumps(body, indent=2) + "\n")


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


def install_hooks(plan: Plan, kit: Path, merge: Any) -> None:
    raw = (kit / "templates" / "githooks" / "pre-push").read_text("utf-8")
    if any(char in str(kit) for char in '"$`\\\n'):
        raise cli.Failure(
            f"the kit folder {kit} holds a character that cannot go into the pre-push hook",
            next_command="move the kit to a folder with a plain name, then run /setup again",
            code=cli.ExitCode.ENVIRONMENT,
        )
    template = str(merge.render(raw, {"KIT_DIR": str(kit)}))
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


def write_kit_record(kit: Path, root: Path, dry_run: bool) -> str:
    """The plugin's version record, which the pre-run check reads. See write_record()."""
    if kit.resolve() == (root / "kit").resolve():
        return "not needed: the kit is this project's own kit/ folder"
    if (kit / "version.json").exists():
        return "kept"
    if dry_run:
        return "would write"
    try:
        load_module("pre_run_check", HERE / "pre-run-check.py").write_record(kit)
    except OSError as error:
        return f"could not write ({error}). Run the installer's record step for {kit}"
    return "written"


# --- the steps --------------------------------------------------------------------


def step_found(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root(args.project)
    kit = Path(args.kit_dir).resolve() if args.kit_dir else HERE.parent
    check_origin(root, check_tooling(root))
    plan = Plan(root, bool(getattr(args, "dry_run", False)))
    templates = kit / "templates"
    ref = kit_ref(kit, args.kit_ref)
    if ref is None:
        ref = "main"
        plan.open_questions.append(
            "Which kit version should checks.yml fetch? It uses main until the kit names one."
        )
    merge = load_module("merge_settings", HERE / "merge-settings.py")
    values = {"KIT_DIR": str(kit), "KIT_REF": ref}

    def rendered(name: str) -> str:
        return str(merge.render((templates / name).read_text("utf-8"), values))

    language = args.language or detect_language(root)
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

    for source, target in (
        ("AGENTS.md", "AGENTS.md"),
        ("CLAUDE.md", "CLAUDE.md"),
        ("overview.md", "docs/overview.md"),
        ("docs-README.md", "docs/README.md"),
        ("area-map", "docs/area-map"),
        ("CHANGELOG.md", "CHANGELOG.md"),
        ("checks.yml", ".github/workflows/checks.yml"),
        ("blocked-commands.md", ".agents/guard/blocked-commands.md"),
    ):
        plan.place(target, rendered(source))
    extend_ignore(plan, (templates / "gitignore").read_text("utf-8"))
    place_settings(plan, kit)
    install_hooks(plan, kit, merge)
    has_runner = project_has_runner(root)
    plan.place(".agents/loop/policy.json", build_policy(kit, args, mode, has_runner))
    place_allowlist(plan, kit, language)

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
    record = write_kit_record(kit, root, plan.dry_run)
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
