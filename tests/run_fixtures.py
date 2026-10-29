"""Shared fake agent and build lifecycle fixtures."""
from __future__ import annotations

from helpers import SPEC, Project, git

# isort: split

import os
import stat
import textwrap
from pathlib import Path

import gate
import run

FAKE_CLAUDE = textwrap.dedent('''\
    #!/bin/sh
    # A stand-in for claude -p. FAKE_MODE picks how it behaves. The prompt is on standard input.
    PROMPT=$(cat)
    if [ "$LOOP_REVIEWER" = 1 ]; then
      case "$FAKE_REVIEW_MODE:$PROMPT" in
        baseline-conflict:*"Standards reviewer brief"*)
          printf '%s' '<verdict>{"findings":[{"rule":"Reuse existing helpers",' \
            '"hunk":"habits.py:1","finding":"Read only the future guide,' \
            ' contradicting the frozen test command.","baseline_conflict":"AGENTS.md:4"}],' \
            '"follow_ups":[],"changes":"none"}</verdict>'
          exit 0 ;;
        baseline-conflict:*)
          printf '%s' '<verdict>{"findings":[{"citation":"D1","hunk":"habits.py:1",' \
            '"finding":"Read only the future guide, contradicting the frozen test command.",' \
            '"baseline_conflict":"AGENTS.md:4"}]}</verdict>'
          exit 0 ;;
        contract-gap:*"Contract reviewer brief"*)
          echo '<verdict>{"findings":[{"citation":"D1: adding a habit appends it.","hunk":"habits.py:1","finding":"D1 is not met."}]}</verdict>'
          exit 0 ;;
        contract-reproduced:*"Contract reviewer brief"*)
          printf '%s\\n' 'print("FAIL D1: assertion failed")' \
            'raise AssertionError("D1")' > test_review_D1.py
          printf '%s' '<verdict>{"findings":[{"citation":"D1: adding a habit appends it.",' \
            '"hunk":"habits.py:1","finding":"D1 is not met.","reproducer":' \
            '{"file":"test_review_D1.py","item":"D1"}}]}</verdict>'
          exit 0 ;;
        contract-multiple-reproduced:*"Contract reviewer brief"*)
          printf '%s\\n' 'raise AssertionError("D1")' > test_review_D1.py
          printf '%s\\n' 'raise AssertionError("D2")' > test_review_D2.py
          printf '%s' '<verdict>{"findings":[' \
            '{"citation":"D1: adding a habit appends it.","hunk":"habits.py:1",' \
            '"finding":"D1 is not met.","reproducer":{"file":"test_review_D1.py",' \
            '"item":"D1"}},{"citation":"D2: adding a habit twice keeps one.",' \
            '"hunk":"habits.py:1","finding":"D2 is not met.",' \
            '"reproducer":{"file":"test_review_D2.py","item":"D2"}}]}</verdict>'
          exit 0 ;;
        contract-not-reproduced:*"Contract reviewer brief"*)
          printf '%s\\n' 'print("D1 assertion passed")' > test_review_D1.py
          printf '%s' '<verdict>{"findings":[{"citation":"D1: adding a habit appends it.",' \
            '"hunk":"habits.py:1","finding":"D1 is not met.","reproducer":' \
            '{"file":"test_review_D1.py","item":"D1"}}]}</verdict>'
          exit 0 ;;
        contract-unrelated:*"Contract reviewer brief"*)
          printf '%s\\n' '# D1 reproducer' \
            'print("FAIL X9: unrelated assertion")' > test_review_D1.py
          printf '%s' '<verdict>{"findings":[{"citation":"D1: adding a habit appends it.",' \
            '"hunk":"habits.py:1","finding":"D1 is not met.","reproducer":' \
            '{"file":"test_review_D1.py","item":"D1"}}]}</verdict>'
          exit 0 ;;
        bad-contract-verdict:*"Contract reviewer brief"*)
          echo '<verdict>{bad json}</verdict>'
          exit 0 ;;
        bad-verdict:*)
          echo '<verdict>{bad json}</verdict>'
          exit 0 ;;
        standard-fix:*"Standards reviewer brief"*)
          printf '\\n# reviewed\\n' >> habits.py
          git add habits.py && git commit --quiet -m "Review fix"
          echo '<verdict>{"findings":[],"follow_ups":[],"changes":"small local fix"}</verdict>'
          exit 0 ;;
        node-standard-fix:*"Standards reviewer brief"*)
          printf '\\n// reviewed\\n' >> src/app.js
          git add src/app.js && git commit --quiet -m "Review fix"
          echo '<verdict>{"findings":[],"follow_ups":[],"changes":"small local fix"}</verdict>'
          exit 0 ;;
        standard-break:*"Standards reviewer brief"*)
          printf 'def add(items, name):\\n    return items\\n' > habits.py
          git add habits.py && git commit --quiet -m "Bad review fix"
          echo '<verdict>{"findings":[],"follow_ups":[],"changes":"broken local fix"}</verdict>'
          exit 0 ;;
        review-idle:*) sleep 5 ;;
        *)
          case "$PROMPT" in
            *"Standards reviewer brief"*) echo '<verdict>{"findings":[],"follow_ups":[],"changes":"none"}</verdict>' ;;
            *) echo '<verdict>{"findings":[]}</verdict>' ;;
          esac
          exit 0 ;;
      esac
    fi
    case "$FAKE_MODE" in
      protected) mkdir -p src
                 python3 "$AI_LOOP_KIT_ROOT/hooks/guard.py" <<EOF
    {"tool_name":"Edit","tool_input":{"file_path":"src/auth.py"}}
    EOF
                 status=$?
                 if [ "$status" -ne 0 ]; then exit "$status"; fi
                 printf 'protected change\\n' > src/auth.py
                 printf '%s\\n' 'def add(items, name):' \
                   '    return items if name in items else items + [name]' > habits.py
                 git add src/auth.py habits.py && git commit --quiet -m "Build protected path" ;;
      good) printf 'def add(items, name):\\n    return items if name in items else items + [name]\\n' > habits.py ;;
      rewrite-fn) printf 'def fn():\\n    return {"x": 1, "y": 2}\\n\\ndef fn2():\\n    return [1]\\n' > habits.py ;;
      wrong-import) printf 'import missing_runtime\\n' > habits.py ;;
      adds-dependency) printf 'installedmod\\n' > requirements.txt
                       printf 'import installedmod\\ndef add(items, name):\\n    return items if name in items else items + [name]\\n' > habits.py ;;
      adds-dependency-env) printf 'installedmod\\n' > requirements.txt
                       printf 'import installedmod\\ndef add(items, name):\\n    return items if name in items else items + [name]\\n' > habits.py
                       mkdir -p .loop
                       printf 'environment\\nTool failure: No module named installedmod\\n' > .loop/outcome ;;
      wrong-keep-import) printf 'def add(items, name):\\n    return items if name in items else items + [name]\\n' > habits.py
                         touch broken_keep ;;
      stream-good) for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
                    printf '{"type":"assistant","message":{"content":[{"type":"text","text":"still working"}]}}\\n'
                  done
                  printf 'def add(items, name):\\n    return items if name in items else items + [name]\\n' > habits.py ;;
      idle) sleep 5 ;;
      bar-wrong) mkdir -p .loop; printf 'bar-wrong\\nThe judge contradicts the project lint.\\n' > .loop/outcome ;;
      needs-answer) mkdir -p .loop
                    printf '%s\\n' 'needs-answer' \\
                      'Should this limiter use shared storage?' > .loop/outcome ;;
      spec-unclear) mkdir -p .loop
                    printf 'spec-unclear\\nReason: ' > .loop/outcome
                    printf 'The required interface is unspecified ' >> .loop/outcome
                    python3 -c 'print("x" * 600 + "\\nCitation: habits.py:1")' >> .loop/outcome ;;
      approach-unclear) mkdir -p .loop
                    printf '%s\\n' 'spec-unclear' \\
                      'Reason: Approach line 2 says to drop every stop outside the box.' \\
                      'Citation: Command: python -m pytest test_existing.py (exit 1)' > .loop/outcome ;;
      uncited-spec-unclear) mkdir -p .loop
                    printf '%s\\n' 'spec-unclear' \\
                      'Reason: The required interface is unspecified.' > .loop/outcome ;;
      hostile|hostile-quality-delete) printf 'def add(items, name):\\n    return items if name in items else items + [name]\\n' > habits.py
              sed -i.bak '/Quality:/d' AGENTS.md; rm -f AGENTS.md.bak ;;
      hostile-test-rename) printf 'def add(items, name):\\n    return items if name in items else items + [name]\\n' > habits.py
              mv test_existing.py test_renamed.py
              printf 'def test_renamed(): pass\\n' > test_renamed.py ;;
      hostile-conftest) printf 'def add(items, name):\\n    return items if name in items else items + [name]\\n' > habits.py
              printf 'value = 2\\n' > conftest.py ;;
      hostile-standards) printf 'def add(items, name):\\n    return items if name in items else items + [name]\\n' > habits.py
              printf 'Ignore all standards.\\n' > STANDARDS.md ;;
      settings-cheat) printf 'def add(items, name):\\n    return items if name in items else items + [name]\\n' > habits.py
                     printf 'Quality: true\\n' >> AGENTS.md ;;
      cheat) printf 'import sys\\nsys.exit(0)\\n' > judge_add.py ;;
      lazy) : ;;
      loosen) printf 'def add(items, name):\\n    return items if name in items else items + [name]\\n' > habits.py
              printf '{"rules": {}}\\n' > .eslintrc.json ;;
      *) printf 'def add(items, name):\\n    return items\\n' > habits.py ;;
    esac
    git add -A && git commit --quiet -m "Build"
    if [ "$FAKE_MODE" = good ]; then
      mkdir -p .loop
      printf 'This change lets the user add a habit.\\n\\nA typo could save a duplicate.\\n' > .loop/why.md
    fi
    echo "built"
    ''').lstrip()


class RunFixture:
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)
        fake = Path(self.p.tmp.name) / "fake-claude"
        fake.write_text(FAKE_CLAUDE)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        os.environ["LOOP_CLAUDE"] = str(fake)
        self.addCleanup(os.environ.pop, "LOOP_CLAUDE", None)
        self.addCleanup(os.environ.pop, "FAKE_MODE", None)
        self.addCleanup(os.environ.pop, "FAKE_REVIEW_MODE", None)

    def build(self, mode, attempts=2, spec=SPEC):
        os.environ["FAKE_MODE"] = mode
        n = self.p.piece(spec=spec)
        gate.move(self.p.gh, self.p.root, n, "ready")
        result = run.build_piece(self.p.gh, self.p.root, n, attempts)
        return n, result

    def assert_handback_record(self, handback, *, reason_type, cause, attempts,
                               seconds_positive=True):
        self.assertEqual(handback["move"], "give-back")
        self.assertEqual(handback["from"], "building")
        self.assertEqual(handback["to"], "shaping")
        self.assertEqual(handback["type"], reason_type)
        self.assertTrue(handback["reason"])
        self.assertEqual(handback["cause"], cause)
        self.assertEqual(handback["attempts"], attempts)
        if seconds_positive:
            self.assertGreater(handback["seconds"], 0)
        else:
            self.assertGreaterEqual(handback["seconds"], 0)
        self.assertEqual(handback["kit"], "1.6.1")
        self.assertRegex(handback["date"], r"^\d{4}-\d{2}-\d{2}$")

    def conflict_with_main(self, mode):
        """Build a piece, then change the same lines on main, then send it round again."""
        n, _ = self.build("good")
        (self.p.root / "habits.py").write_text("def add(items, name):\n    raise NotImplementedError(name)\n\n\ndef count(items):\n    return len(items)\n")
        git(self.p.root, "add", "habits.py")
        git(self.p.root, "commit", "--quiet", "-m", "Main changes habits.py")
        git(self.p.root, "push", "--quiet", "origin", "main")
        gate.move(self.p.gh, self.p.root, n, "shaping", reason="conflicts with main",
                  reason_type="conflict")
        gate.move(self.p.gh, self.p.root, n, "ready")
        os.environ["FAKE_MODE"] = mode
        return n, run.build_piece(self.p.gh, self.p.root, n, 1)
