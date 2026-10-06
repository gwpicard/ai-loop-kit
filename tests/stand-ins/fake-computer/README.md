# fake-computer

Stand-ins for the commands the pre-run check reads about the computer. A test
puts this folder first on PATH, so the check never sees the real machine.

| Command | Reads | Set with |
| --- | --- | --- |
| `pmset` | power source and sleep assertions | `FAKE_COMPUTER_POWER` (`ac` or `battery`), `FAKE_COMPUTER_SLEEP` (`held` or `free`) |
| `vm_stat` | free memory | `FAKE_COMPUTER_FREE_MB` |
| `df` | free disk | `FAKE_COMPUTER_DISK_GB` |
| `claude` | the version only | `FAKE_CLAUDE_VERSION` |

The output copies the layout of the macOS commands. Unset variables give a
healthy computer: on mains power, sleep held off, 8192 MB free, 100 GB of disk
and Claude Code 2.1.219.

The `claude` here answers `--version` and nothing else. It is not the session
stand-in in `tests/stand-ins/fake-claude/`.
