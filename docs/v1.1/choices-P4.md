# P4 choices

- Require mutmut 3.8 or later. Check the installed version before running the changed-function helper.
- Require at least one configured mutmut source path. Read the project's `pyproject.toml` or `setup.cfg`.
- For subprocess acceptance tests, keep those tests in the project's Test command and configure mutmut to select an in-process adapter test for the changed function. This is the documented fallback; it keeps mutation evidence tied to code that mutmut can observe.
- When setup proposes a Quality command, replace the Quality lines in a temporary fresh-main copy of `AGENTS.md`, then run Prepare, Test and that proposed command there.
- Leave the other v1.1 ledger items for their owning packages or later field runs.

The subprocess fallback follows mutmut's documented test-selection setting, `pytest_add_cli_args_test_selection`, in its [configuration guide](https://mutmut.readthedocs.io/en/latest/#configuration). The package scope and requirements come from `docs/v1.1/PLAN.md` and the rehearsal findings in `docs/LEDGER.md`.
