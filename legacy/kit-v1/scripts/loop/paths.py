"""Every shared path of a project that runs the loop, defined once.

No later piece writes one of these paths by hand. A piece asks `Paths` for it.
The folders outside the project (the held-out folder and the App key) sit under
the person's local data folder, so an agent working in the project cannot reach
them by accident.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DATA_ENV = "AI_LOOP_KIT_DATA"
PLUGIN_ENV = "CLAUDE_PLUGIN_ROOT"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class PathError(ValueError):
    """A name or a place that cannot be used. The message names what to do."""


def _home(env: Mapping[str, str]) -> Path:
    home = env.get("HOME")
    if not home:
        raise PathError("HOME is not set. Set AI_LOOP_KIT_DATA to a folder outside the project.")
    return Path(home)


def data_home(env: Mapping[str, str]) -> Path:
    """The person's local data folder for the kit, outside any project."""
    if env.get(DATA_ENV):
        return Path(env[DATA_ENV])
    if env.get("XDG_DATA_HOME"):
        return Path(env["XDG_DATA_HOME"]) / "ai-loop-kit"
    return _home(env) / ".local" / "share" / "ai-loop-kit"


def kit_dir(project_root: Path, env: Mapping[str, str]) -> Path:
    """The installed kit folder.

    In this repository it is `kit/`. In a founded project it is the plugin cache.
    """
    if env.get(PLUGIN_ENV):
        return Path(env[PLUGIN_ENV])
    if (project_root / "kit" / "scripts" / "loop").is_dir():
        return project_root / "kit"
    return _home(env) / ".claude" / "plugins" / "cache" / "ai-loop-kit"


def find_project_root(start: Path) -> Path:
    """Walk up from `start` to the folder that holds `.git`."""
    here = start.resolve()
    for folder in (here, *here.parents):
        if (folder / ".git").exists():
            return folder
    raise PathError(f"{start} is not inside a Git repository. Run the script from the project.")


def _check_run_name(name: str) -> str:
    if not _NAME.match(name) or ".." in name:
        raise PathError(
            f"{name!r} is not a valid run name. Use letters, digits, '.', '_' and '-' only."
        )
    return name


def project_key(root: Path) -> str:
    """A folder name for a project: its name plus a hash of its full path.

    Two projects with the same folder name at different paths get different keys.
    """
    resolved = root.resolve()
    digest = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:12]
    return f"{resolved.name}-{digest}"


@dataclass(frozen=True)
class Paths:
    """All shared paths for one project."""

    root: Path
    data_dir: Path
    kit_dir: Path

    @classmethod
    def for_project(
        cls,
        root: Path,
        *,
        data_base: Path | None = None,
        kit_folder: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> Paths:
        """Build the paths for the project at `root`.

        Without arguments the data folder and the kit folder come from `env`
        (the real environment by default).
        """
        env = os.environ if env is None else env
        base = data_base if data_base is not None else data_home(env)
        kit = kit_folder if kit_folder is not None else kit_dir(root, env)
        return cls(root=root, data_dir=base / project_key(root), kit_dir=kit)

    # --- inside the project -------------------------------------------------

    @property
    def agents_dir(self) -> Path:
        return self.root / ".agents"

    @property
    def runs_dir(self) -> Path:
        return self.agents_dir / "runs"

    def run_dir(self, name: str) -> Path:
        return self.runs_dir / _check_run_name(name)

    def run_record(self, name: str) -> Path:
        return self.run_dir(name) / "run.json"

    @property
    def project_lock(self) -> Path:
        """One retained admission lock for every run name in this project."""
        return self.runs_dir / ".project.lock"

    def lock_file(self, name: str) -> Path:
        """The run's PID mirror, read by pre-run and merge checks."""
        return self.run_dir(name) / "lock"

    def heartbeat(self, name: str) -> Path:
        return self.run_dir(name) / "heartbeat"

    def mailbox(self, name: str) -> Path:
        return self.run_dir(name) / "mailbox"

    def command_log(self, name: str) -> Path:
        return self.run_dir(name) / "commands.log"

    @property
    def pieces_dir(self) -> Path:
        return self.agents_dir / "pieces"

    def piece_dir(self, number: int) -> Path:
        if number < 1:
            raise PathError(f"{number} is not a piece number. Piece numbers start at 1.")
        return self.pieces_dir / str(number)

    @property
    def worktrees_dir(self) -> Path:
        return self.agents_dir / "worktrees"

    @property
    def policy_file(self) -> Path:
        return self.agents_dir / "loop" / "policy.json"

    @property
    def area_map(self) -> Path:
        """The project's area map: one `<pattern> <area>` line each, last match wins."""
        return self.root / "docs" / "area-map"

    @property
    def local_settings(self) -> Path:
        """Machine-local settings. Git ignores this file."""
        return self.agents_dir / "loop" / "local.json"

    # --- outside the project ------------------------------------------------

    @property
    def held_out_dir(self) -> Path:
        return self.data_dir / "held-out"

    @property
    def app_key_file(self) -> Path:
        return self.data_dir / "app-key.pem"
