import json
from pathlib import Path
import re
import subprocess

from kit.tests.helpers import FakeGh, make_repo
import common


KIT = Path(__file__).resolve().parents[1]


class OpenParksStatusTest(FakeGh):
    def test_status_lists_all_current_parks_outside_the_event_window(self):
        work, _ = make_repo(self.tmp, {"loop.json": '{"Test command": "true"}'})
        runtime = Path(work, ".loop")
        runtime.mkdir()
        questions = {n: "May the build change option %d?" % n for n in (2, 3, 4, 5)}
        events = [dict(time="2020-01-01T10:00:00+00:00", kind="parked",
                       issue=n, reason="An obsolete question") for n in (*questions, 8)]
        (runtime / "events.jsonl").write_text("\n".join(map(json.dumps, events)) + "\n")
        issues = [dict(number=n, title="Decision %d" % n, state="OPEN",
                       labels=[{"name": "needs-user"}]) for n in questions]
        for opened, window in ((issues, "1m"), (list(reversed(issues)), "24h")):
            with self.subTest(window=window):
                rules = []
                for n, question in questions.items():
                    comments = [dict(body="## Needs you\n\nAn obsolete question\n\n" + common.MARKER),
                                dict(body="## Needs you\n\n" + question + "\n\nRecommended: approve.\n\n"
                                     + common.MARKER, createdAt="2020-01-02T10:00:00Z"),
                                dict(body="Unrelated later note", author={"login": "bot"})]
                    rules.append(dict(match="issue view %d " % n,
                                      responses=[{"stdout": json.dumps({"comments": comments})}]))
                rules.append(dict(match="issue list", responses=[{"stdout": json.dumps(opened)}]))
                self.scenario(rules)
                result = subprocess.run([str(KIT / "bin/loop"), "status", "--since", window],
                                        cwd=work, text=True, capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                section = re.search(r"(?im)^open[ -]parks:[^\n]*(?:\n[ \t]+[^\n]*)*", result.stdout)
                self.assertIsNotNone(section, "status must show current open parks:\n" + result.stdout)
                for n, question in questions.items():
                    self.assertIn("#%d" % n, section.group())
                    self.assertIn(question, section.group())
                self.assertNotIn("obsolete", section.group())
                self.assertNotIn("#%d" % 8, section.group())
                listings = [args for args in self.calls() if args[:2] == ["issue", "list"]]
                self.assertTrue(listings, "current parks must come from GitHub")
                for args in listings:
                    self.assertIn("open", args)
                    self.assertIn("needs-user", args)
