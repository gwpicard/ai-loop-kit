# Kit size after the gauntlet archive

Measured on 16 October 2026. The baseline is release commit `da81ecc`, which
was also the fetched `main` before this change. Counts include blank lines
and comments in every Python file under `kit/`.

The gauntlet field run needed hand repairs for critic criterion keys and lost
an invalid response. Its implementation, brief and tests remain on
`preview/gauntlet` at `da81ecc`. The shipped kit refuses those checks.

## Python lines

| File | Before | After | Change |
| --- | ---: | ---: | ---: |
| `kit/hooks/guard.py` | 239 | 239 | +0 |
| `kit/quality/crap.py` | 163 | 163 | +0 |
| `kit/quality/mutmut-changed.py` | 131 | 131 | +0 |
| `kit/quality/mutmut-check.py` | 36 | 36 | +0 |
| `kit/quality/mutmut_support.py` | 56 | 56 | +0 |
| `kit/quality/proposed_quality.py` | 48 | 48 | +0 |
| `kit/scripts/agents.py` | 173 | 168 | -5 |
| `kit/scripts/builder_prompt.py` | 110 | 107 | -3 |
| `kit/scripts/critic.py` | 186 | 0 | -186 |
| `kit/scripts/gate.py` | 942 | 865 | -77 |
| `kit/scripts/gate_cli.py` | 0 | 92 | +92 |
| `kit/scripts/loopkit.py` | 973 | 652 | -321 |
| `kit/scripts/measure.py` | 102 | 102 | +0 |
| `kit/scripts/pr.py` | 121 | 121 | +0 |
| `kit/scripts/procs.py` | 140 | 140 | +0 |
| `kit/scripts/research.py` | 59 | 59 | +0 |
| `kit/scripts/review.py` | 438 | 438 | +0 |
| `kit/scripts/risk_checks.py` | 122 | 122 | +0 |
| `kit/scripts/run.py` | 613 | 611 | -2 |
| `kit/scripts/run_cli.py` | 134 | 134 | +0 |
| `kit/scripts/run_start.py` | 63 | 63 | +0 |
| `kit/scripts/sandbox.py` | 312 | 312 | +0 |
| `kit/scripts/spec.py` | 0 | 304 | +304 |
| `kit/scripts/testlint.py` | 234 | 234 | +0 |
| `kit/scripts/walkaway.py` | 289 | 289 | +0 |
| **Total** | **5,684** | **5,486** | **-198** |

`spec.py` holds the issue parser and `gate_cli.py` holds command-line dispatch.
The shared imports through `loopkit` and the gate entry points stay available.
The total remains above the 2,500-line target. The size check caps it below
5,500 lines and keeps every Python module below 900 lines.

## Test splits

The gate, spec and guard tests have separate modules. Run tests share a
fixture and fake Claude process in `run_helpers.py`; discovery runs each test
once. Only the archived critic tests leave the suite. The goal checks remain.

| File | Before | After |
| --- | ---: | ---: |
| `tests/test_loop.py` | 972 | 763 |
| `tests/test_spec.py` | 0 | 142 |
| `tests/test_guard.py` | 0 | 75 |
| `tests/test_run.py` | 999 | 409 |
| `tests/test_run_build.py` | 0 | 470 |
| `tests/run_helpers.py` | 0 | 152 |

To repeat the Python measurement from the repository root:

```sh
python3 - <<'PYTHON'
from pathlib import Path
counts = [(path, len(path.read_bytes().splitlines()))
          for path in sorted(Path("kit").rglob("*.py"))]
for path, lines in counts:
    print(f"{lines:5} {path}")
print("Total:", sum(lines for _, lines in counts))
PYTHON
```
