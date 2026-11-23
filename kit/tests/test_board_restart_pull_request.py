from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from kit.tests.helpers import FakeGh, make_repo, run_git, write_exe
import common


GITHUB = '''#!PYTHON
import json, os, sys
from pathlib import Path
root = Path(os.environ['RESTART_PROJECT'])
world = json.loads((root / 'world.json').read_text())
args = sys.argv[1:]
if args[:2] == ['label', 'list']:
    print(json.dumps([dict(name=n) for n in ('inbox', 'shaping', 'ready', 'building', 'needs-user')]))
elif args[:2] == ['issue', 'list']:
    print(json.dumps([] if 'closed' in args else world['issues']))
elif args[:2] == ['issue', 'view']:
    print(json.dumps(dict(comments=world['comments'])))
elif args[:2] == ['issue', 'edit']:
    body = sys.stdin.read()
    with (root / 'boards.jsonl').open('a') as output:
        output.write(json.dumps(body) + '\\n')
    (root / '.loop/stop').touch()
elif args[:2] == ['pr', 'list']:
    pulls = world['pulls']
    for flag, field in (('--head', 'headRefName'), ('--base', 'baseRefName'), ('--state', 'state')):
        if flag in args and args[args.index(flag) + 1] != 'all':
            pulls = [p for p in pulls if p[field].lower() == args[args.index(flag) + 1].lower()]
    print(json.dumps(pulls))
elif args[:2] == ['repo', 'view']:
    print(json.dumps(dict(defaultBranchRef=dict(name=world['base']), nameWithOwner='test/project')))
elif 'milestones' in ' '.join(args):
    print('[]')
elif 'delete_branch_on_merge' in ' '.join(args):
    print('false')
else:
    sys.exit('unexpected GitHub call: ' + repr(args))
'''

RUN = """
import sys
sys.path.insert(0, sys.argv[1])
import loop
# Avoid macOS helpers; the supervisor still runs through its command entry point.
loop.sys.platform = 'linux'
loop.POLL = 0.01
sys.exit(loop.main(['run']))
"""


class RestartBoardPullRequestTest(FakeGh):
    def test_first_cycle_recovers_the_open_final_pull_request_before_drain(self):
        for branch, base, reverse in (("loop/main", "main", False), ("loop/batch", "stable", True)):
            with self.subTest(branch=branch, base=base):
                work, _ = make_repo(self.tmp, {"loop.json": json.dumps({
                    "Test command": "true", "Loop branch": branch, "Idle hours": 1})})
                run_git(["push", "origin", "main:" + branch], work)
                run_git(["update-ref", "refs/remotes/origin/" + base, "HEAD"], work)
                run_git(["symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/" + base], work)
                url = "https://example.test/pull/final"
                pulls = [dict(number=n, url=link, headRefName=head, baseRefName=target,
                              state=state, closingIssuesReferences=[])
                         for n, link, head, target, state in (
                             (6, "https://example.test/pull/piece", "issue/2", branch, "OPEN"),
                             (7, url, branch, base, "OPEN"),
                             (8, "https://example.test/pull/closed", branch, base, "CLOSED"),
                             (9, "https://example.test/pull/other", branch, "other", "OPEN"))]
                world = dict(base=base, pulls=list(reversed(pulls)) if reverse else pulls,
                             issues=[dict(number=1, title="Factory", body="", labels=[]),
                                     dict(number=2, title="Decision", body="", labels=[dict(name="needs-user")]),
                                     dict(number=3, title="Waiting", body="Depends on: #2", labels=[dict(name="ready")])],
                             comments=[dict(body="## Needs you\n\nWhich option?\n\n" + common.MARKER,
                                            createdAt=datetime.now(timezone.utc).isoformat(),
                                            author=dict(login="bot"))])
                Path(work, "world.json").write_text(json.dumps(world))
                os.environ["RESTART_PROJECT"] = work
                write_exe(Path(self.tmp, "bin/gh"), GITHUB)
                result = subprocess.run([sys.executable, "-c", RUN, str(Path(common.__file__).parent)],
                                        cwd=work, text=True, capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                boards = [json.loads(line) for line in Path(work, "boards.jsonl").read_text().splitlines()]
                self.assertTrue(boards, result.stdout)
                needs = boards[0].split("## Needs you", 1)[1].split("## Progress", 1)[0]
                self.assertIn(url, needs, "the first board update must recover the existing final pull request")
                for suffix in ("piece", "closed", "other"):
                    self.assertNotIn("https://example.test/pull/" + suffix, needs)
                self.assertNotIn("drained", boards[0])
