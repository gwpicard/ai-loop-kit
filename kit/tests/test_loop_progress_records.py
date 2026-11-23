"""Read progress records after running the supervisor with fake GitHub and agents."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from kit.tests.fake_claude import FakeClaudeGh
from kit.tests.helpers import make_repo, run_git, write_exe
import common


SCRIPTS = str(Path(common.__file__).parent)
RUNNER = """
import sys
sys.path.insert(0, sys.argv[1])
import loop
loop.POLL = loop.BUSY_POLL = 0.02
# Batch work and host load do not affect the records for an individual build.
loop.drain = lambda *a: None
loop.sync_default = lambda *a: False
loop.headroom = lambda: None
sys.exit(loop.main(['run']))
"""

GITHUB = '''#!PYTHON
import json, os, subprocess, sys
from pathlib import Path
root = Path(os.environ['PROGRESS_PROJECT'])
runtime = root / '.loop'
state_path = runtime / 'github.json'
state = json.loads(state_path.read_text())
number = state['number']
args = sys.argv[1:]
body = sys.stdin.read() if '--body-file' in args else ''
def save():
    state_path.write_text(json.dumps(state))
def stop():
    (runtime / 'stop').touch()
def issue():
    return dict(number=number, title='Piece', body='Build the feature.',
                labels=[dict(name=n) for n in state['labels']],
                comments=state['comments'], state='CLOSED' if state['closed'] else 'OPEN')
if args[:2] == ['label', 'list']:
    print(json.dumps([dict(name=n) for n in
                     ('inbox', 'shaping', 'ready', 'building', 'needs-user')]))
elif args[:2] == ['repo', 'view']:
    print(json.dumps(dict(nameWithOwner='test/project',
                         defaultBranchRef=dict(name='main'), deleteBranchOnMerge=False)))
elif 'permission' in ' '.join(args):
    print(json.dumps(dict(permission='write')))
elif 'timeline' in ' '.join(args):
    print(json.dumps([dict(event='labeled', label=dict(name='ready'), actor=dict(login='person'))]))
elif args[:2] == ['issue', 'list']:
    if '--state' in args and args[args.index('--state') + 1] == 'closed':
        print(json.dumps([dict(number=number)] if state['closed'] else []))
    else:
        print(json.dumps([dict(number=1, title='Factory', body='', labels=[])]
                         + ([] if state['closed'] else [issue()])))
elif args[:2] == ['issue', 'view']:
    print(json.dumps(issue()))
elif args[:2] == ['issue', 'edit'] and args[2] == str(number):
    for flag in ('--add-label', '--remove-label'):
        if flag in args:
            label = args[args.index(flag) + 1]
            labels = set(state['labels'])
            labels.add(label) if flag == '--add-label' else labels.discard(label)
            state['labels'] = sorted(labels)
    save()
elif args[:2] == ['issue', 'comment']:
    state['comments'].append(dict(body=body, author=dict(login='bot')))
    save()
    if body.startswith('## Needs you'):
        stop()
elif args[:2] == ['issue', 'close']:
    state['closed'] = True
    save()
    stop()
elif args[:2] == ['pr', 'create']:
    state['pr'] = True
    save()
    print('https://example.test/pull/9')
elif args[:2] == ['pr', 'merge']:
    sha = subprocess.check_output(['git', 'rev-parse', 'issue/' + str(number)], cwd=state['origin'], text=True).strip()
    subprocess.run(['git', 'update-ref', 'refs/heads/loop/main', sha], cwd=state['origin'], check=True)
    state['merged'] = True
    save()
elif args[:2] == ['pr', 'list']:
    rows = []
    if state.get('pr') and '--head' in args:
        sha = subprocess.check_output(['git', 'rev-parse', 'issue/' + str(number)], cwd=state['origin'], text=True).strip()
        if '--state' not in args or args[args.index('--state') + 1] != 'merged' or state.get('merged'):
            rows = [dict(number=9, state='MERGED' if state.get('merged') else 'OPEN',
                         headRefOid=sha, mergeCommit=dict(oid=sha), files=[])]
    print(json.dumps(rows))
elif args[:2] == ['pr', 'view']:
    print(json.dumps(dict(comments=[])))
elif args[:2] in (['issue', 'edit'], ['pr', 'edit'], ['pr', 'comment']):
    pass
elif 'milestones' in ' '.join(args):
    print('[]')
else:
    sys.exit('unexpected GitHub call: ' + repr(args))
'''


class ProgressRecordsTest(FakeClaudeGh):
    def run_factory(self, number=4, parked=False, earlier_answer=False):
        work, origin = make_repo(self.tmp, {
            'loop.json': json.dumps({'Test command':
                                    'test ! -f tests/test_feature.py || test -f app.py || '
                                    '{ echo AssertionError; false; }',
                                    'Max rounds': 2, 'Idle hours': 1}),
        })
        run_git(['push', 'origin', 'main:loop/main'], work)
        runtime = Path(work, '.loop')
        runtime.mkdir(exist_ok=True)
        park = {'body': '## Needs you\n\nWhich value?\n\n' + common.MARKER,
                'author': {'login': 'bot'}}
        reply = {'body': 'Use 8080.', 'author': {'login': 'person'}}
        comments = ([park, {'body': 'Use 80.', 'author': {'login': 'person'}}]
                    if earlier_answer else []) + [park, reply]
        (runtime / 'github.json').write_text(json.dumps({
            'number': number, 'origin': origin, 'labels': ['needs-user'],
            'comments': comments, 'closed': False,
        }))
        os.environ['PROGRESS_PROJECT'] = work
        write_exe(Path(self.tmp, 'bin', 'gh'), GITHUB)
        changes = {'reply': 'VERDICT: CHANGES\nHEAD: {HEAD}\n\n1. Check the value.'}
        approve = {'reply': 'VERDICT: APPROVE\nHEAD: {HEAD}\n\n1. none'}
        self.claude({
            'test-writer': [{'files': {'tests/test_feature.py': 'assert feature\n'},
                             'reply': 'TESTS:\ntests/test_feature.py'}],
            'builder': [{'files': {'app.py': 'value = 8080\n'},
                         'reply': 'BUILT:\nSet the value.\nDEVIATIONS:\nnone'}],
            'reviewer': [changes, changes if parked else approve],
        })
        log = runtime / 'loop.out'
        with log.open('w') as output:
            result = subprocess.run([sys.executable, '-c', RUNNER, SCRIPTS], cwd=work,
                                    stdout=output, stderr=subprocess.STDOUT, timeout=60)
        text = log.read_text()
        self.assertEqual(result.returncode, 0, text)
        events = [json.loads(line) for line in (runtime / 'events.jsonl').read_text().splitlines()]
        outcome = 'parked' if parked else 'merged'
        self.assertEqual(len([e for e in events if e['kind'] == outcome and e.get('issue') == number]), 1,
                         text + repr(events))
        self.assertEqual([c['role'] for c in self.claude_calls()],
                         ['test-writer', 'builder', 'reviewer', 'builder', 'reviewer'])
        return text.splitlines(), events

    def assert_line(self, lines, number, pattern):
        matches = [line for line in lines if re.search(r'#%d\b' % number, line)
                   and re.search(pattern, line, re.I)]
        self.assertEqual(len(matches), 1, '\n'.join(lines))
        self.assertRegex(matches[0], r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ')

    def test_reply_requeue_has_one_issue_line(self):
        for number, earlier in ((4, False), (7, True)):
            with self.subTest(number=number, earlier_answer=earlier):
                lines, _ = self.run_factory(number, earlier_answer=earlier)
                self.assert_line(lines, number, r'requeu|queued again|answer|repl')

    def test_each_review_verdict_has_one_issue_line(self):
        lines, _ = self.run_factory()
        for verdict in ('CHANGES', 'APPROVE'):
            with self.subTest(verdict=verdict):
                self.assert_line(lines, 4, r'\b' + verdict + r'\b')

    def test_merge_has_one_issue_line(self):
        lines, _ = self.run_factory()
        self.assert_line(lines, 4, r'\bmerged\b')

    def test_park_has_one_issue_line(self):
        lines, _ = self.run_factory(parked=True)
        self.assert_line(lines, 4, r'\bpark(?:ed)?\b')

    def test_reply_requeue_records_one_answered_event(self):
        for number, earlier in ((7, False), (4, True)):
            with self.subTest(number=number, earlier_answer=earlier):
                _, events = self.run_factory(number, earlier_answer=earlier)
                answered = [e for e in events if e['kind'] == 'answered' and e.get('issue') == number]
                self.assertEqual(len(answered), 1, events)
