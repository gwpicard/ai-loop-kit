"""A compact report of the loop branch, from git, build notes and events."""
import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest import mock

from kit.tests.helpers import FakeGh, make_repo, run_git, settings_json
import common
import loop
import report
from kit.tests.test_status import event


class ReportTest(FakeGh):
    def setUp(self):
        super().setUp()
        self.work, _ = make_repo(self.tmp, {
            "loop.json": settings_json('## Loop\nTest command: true\n'),
            'src/api/main.py': 'old\n', 'tests/test_old.py': 'old\n',
            'tests/test_keep.py': 'old\n', 'package-lock.json': '{}\n',
            'widget/__init__.py': '', 'widget/core/run.py': 'old\n'})
        run_git(['checkout', '-b', 'loop/main'], self.work)
        self.land(8, {'src/api/main.py': 'new\nextra\n', 'src/ui/view.py': 'view\n',
                      'tests/test_new.py': 'new\n', 'tests/test_old.py': None,
                      'package-lock.json': '{"version": 2}\n'})
        self.land(9, {'tests/test_keep.py': 'changed\n', 'widget/core/run.py': 'new\n'})
        run_git(['push', 'origin', 'loop/main'], self.work)
        self.folder = Path(self.work, '.loop')
        self.folder.mkdir()
        self.scenario([{'match': 'issue view 8', 'responses': [{'stdout': json.dumps({
            'title': 'Load the list', 'body': '## Protected paths this issue may change\n\n`tests/test_old.py`\n',
            'comments': [{'body': '## Built\n\nLoad without waiting. More detail.\n\nDeviations: Kept the cache.\n\nMerged as abc.\n'}]})}]},
            {'match': 'issue view 9', 'responses': [{'code': 1, 'stderr': 'unavailable'}]}])

    def land(self, number, files):
        run_git(['checkout', '-b', 'piece/%d' % number], self.work)
        for name, text in files.items():
            path = Path(self.work, name)
            if text is None:
                path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
        run_git(['add', '-A'], self.work)
        run_git(['commit', '-m', 'Build piece'], self.work)
        run_git(['checkout', 'loop/main'], self.work)
        run_git(['merge', '--no-ff', 'piece/%d' % number, '-m', 'Issue %d' % number], self.work)

    def command(self):
        out = io.StringIO()
        with mock.patch.object(loop.os, 'getcwd', return_value=self.work), \
                mock.patch.object(loop.session, 'run', side_effect=AssertionError('session')), \
                contextlib.redirect_stdout(out):
            code = loop.main(['report'])
        self.assertEqual(code, 0)
        return out.getvalue().rstrip('\n')

    def test_groups_folders_and_counts_tests_separately(self):
        text = self.command()
        for part in ('Issues: 2', 'src/api: 1 files +2 -1', 'src/ui: 1 files +1 -0',
                     'widget/core: 1 files +1 -1', 'Source: 4 files',
                     'Tests: 1 added, 1 changed, 1 deleted'):
            self.assertIn(part, text)

    def test_risks_include_lockfiles_allowed_paths_deleted_tests_and_churn(self):
        text = self.command()
        for part in ('Manifests and lockfiles: package-lock.json', 'Allowed paths: tests/test_old.py',
                     'Deleted tests: tests/test_old.py', 'Most churn: src/api/main.py (+2 -1)'):
            self.assertIn(part, text)

    def test_report_and_what_changed_list_all_added_changed_and_deleted_support(self):
        paths = ('kit/tests/helpers.py', 'kit/tests/run.py', 'kit/tests/fake_codex.py',
                 'tests/fixtures/data.json')
        self.land(10, {p: 'old\n' for p in paths})
        run_git(['push', 'origin', 'loop/main:main'], self.work)
        self.land(11, {paths[0]: 'new\n', paths[1]: None, paths[2]: 'changed\n',
                       paths[3]: None, 'tests/fixtures/new.json': '{}\n'})
        run_git(['push', 'origin', 'loop/main'], self.work)
        text = self.command()
        for rendered in (text, report.section(text)):
            risk = next(l for l in rendered.splitlines() if l.startswith('test support files changed: '))
            for path in paths + ('tests/fixtures/new.json',):
                self.assertIn(path, risk)
        self.assertIn('Tests: 0 added, 0 changed, 0 deleted', text)

    def test_issue_uses_build_note_and_event_history(self):
        events = [event('step', '10:00', issue=8, step='builder', phase='start'),
                  event('step', '10:02', issue=8, step='review', phase='start', round=1),
                  event('step', '10:03', issue=8, step='review', phase='end', round=1),
                  event('parked', '10:04', issue=8), event('rule', '10:05', issue=8, rule='test-lock'),
                  event('step', '10:10', issue=8, step='review', phase='start', round=2),
                  event('merged', '10:20', issue=8),
                  event('step', '11:00', issue=8, step='review', phase='start', round=3)]
        (self.folder / 'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
        text = self.command()
        for part in ('Issue 8: Load the list', 'Why: Load without waiting.', 'Deviations: Kept the cache.',
                     '2 review rounds; 1 parks; rules: test-lock=1; 20.0 min',
                     'tests added: tests/test_new.py', 'tests changed: tests/test_keep.py',
                     'Why: unavailable'):
            self.assertIn(part, text)
        self.assertNotIn('More detail', text)

    def test_only_one_read_per_issue_and_no_writes_or_local_changes(self):
        before = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        self.command()
        self.assertEqual([c[:3] for c in self.calls()], [['issue', 'view', '8'], ['issue', 'view', '9']])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.folder.iterdir()})

    def test_drain_includes_the_same_report_in_a_safe_fence_and_keeps_sections(self):
        text = self.command()
        inputs = []
        def gh(args, **kw):
            if args[:2] == ['pr', 'create']:
                inputs.append(kw['input'])
            return '{}' if args[:2] == ['issue', 'view'] else '[]'
        settings = common.read_settings(self.work)
        with mock.patch.object(loop, 'gh', side_effect=gh), \
                mock.patch.object(loop.merge, 'run_tests', return_value=None), \
                mock.patch.object(loop.pass_, 'run_pass', return_value=({}, 'PASS-REPORT')), \
                mock.patch.object(loop, 'summary', return_value='## Summary\n\nSummary text.\n'):
            loop.drain(self.work, settings, loop.new_state())
        body = inputs[0]
        self.assertIn('## What changed\n\n```text\n' + text + '\n```', body)
        self.assertLess(body.index('## What changed'), body.index('## Hands-on checks'))
        for part in ('## Summary', '## Decisions to confirm', '## Landed', 'PASS-REPORT'):
            self.assertIn(part, body)

    def test_ten_issues_and_long_lists_stay_compact(self):
        for n in range(10, 18):
            self.land(n, {'tests/test_file%d.py' % i: '%d\n' % n for i in range(8)})
        run_git(['push', 'origin', 'loop/main'], self.work)
        text = self.command()
        self.assertIn('Issues: 10', text)
        self.assertLessEqual(len(text.splitlines()), 60)
        self.assertIn('and 5 more', text)


if __name__ == '__main__':
    unittest.main()
