"""Read Test minutes and apply it to real merge and drain test commands."""
import json
from pathlib import Path
from unittest import mock

from kit.tests import test_full_suite_priority_timeout as fixtures
import common
import loop
import merge
import pass_


class TestMinutesTest(fixtures.FullSuitePriorityTimeoutTest):
    def test_default_and_configured_minutes(self):
        self.assertEqual(common.read_settings(self.work)['Test minutes'], 30)
        Path(self.work, 'loop.json').write_text(json.dumps({**self.values, 'Test minutes': 7}))
        settings = common.read_settings(self.work)
        self.assertEqual(settings['Test minutes'], 7)
        self.assertIs(type(settings['Test minutes']), int)

    def test_invalid_minutes_are_refused(self):
        for value in (0, -1, 0.5, 1.5, True, '2'):
            with self.subTest(value=value):
                Path(self.work, 'loop.json').write_text(json.dumps({**self.values, 'Test minutes': value}))
                with self.assertRaisesRegex(common.SettingsError, 'Test minutes'):
                    common.read_settings(self.work)

    def test_standalone_runner_without_settings_keeps_default_budget(self):
        Path(self.work, 'loop.json').unlink()
        real_run = common.run_shell
        with mock.patch.object(common, 'run_shell', wraps=real_run) as run:
            self.assertIsNone(merge.run_tests(self.work, self.sha, 'true'))
        self.assertEqual(run.call_args.args[2], 1800)

    def test_merge_and_drain_use_project_limit_only_for_tests(self):
        Path(self.work, 'loop.json').write_text(json.dumps({**self.values, 'Test minutes': 7}))
        real_run = common.run_shell
        for entry in ('merge', 'drain'):
            with self.subTest(entry=entry), mock.patch.object(common, 'run_shell', wraps=real_run) as run:
                if entry == 'merge':
                    result = self.merge_candidate()
                    self.assertTrue(result.ok, result.reason)
                else:
                    with mock.patch.object(loop.report, 'render', return_value='Fixture report'), \
                            mock.patch.object(loop, 'hands_on', return_value=''), \
                            mock.patch.object(loop, 'decisions', return_value=''):
                        loop.drain(self.work, common.read_settings(self.work), loop.new_state())
                budgets = {call.args[0]: call.args[2] for call in run.call_args_list}
                self.assertEqual(budgets[self.values['Test command']], 420)
                self.assertEqual(budgets[self.values['Prepare command']], 1800)
                self.assertEqual(budgets[self.values['Check command']], 1800)

    def test_configured_timeout_keeps_output_and_names_setting(self):
        Path(self.work, 'loop.json').write_text(json.dumps({
            'Test command': "printf 'last output\\n'; sleep 30", 'Test minutes': 2}))
        # Scale a minute down for this test while retaining the configured ratio.
        with mock.patch.object(merge, 'TEST_TIMEOUT', 15):
            result = self.merge_candidate()
        self.assertFalse(result.ok)
        self.assertIn('limit 1.0 seconds', result.reason)
        self.assertIn('elapsed', result.reason)
        self.assertIn('Test minutes in loop.json', result.reason)
        self.assertIn('last output', result.reason)

    def test_pass_smoke_keeps_normal_priority_and_its_own_budget(self):
        settings = {**common.read_settings(self.work), 'Test minutes': 7,
                    'Smoke command': 'priority-probe smoke'}
        real_run = common.run_shell
        with mock.patch.object(common, 'run_shell', wraps=real_run) as run, \
                mock.patch.object(pass_, 'gh', return_value='[]'), \
                mock.patch.object(pass_.session, 'run', return_value=('FINDINGS:\nnone', 'fixture')):
            result, _ = pass_.run_pass(self.work, settings, 'origin/main', head=self.sha)
        self.assertEqual(result['smoke'], 'passed', result)
        self.assertEqual(result['errors'], [], result)
        smoke = [call for call in run.call_args_list if call.args[0] == settings['Smoke command']]
        self.assertEqual(len(smoke), 1)
        self.assertEqual(smoke[0].args[2], 1800)
        records = [json.loads(line) for line in self.trace.read_text().splitlines()]
        self.assertIn(['smoke', 'normal'], records)
