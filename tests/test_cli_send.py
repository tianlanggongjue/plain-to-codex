import contextlib
import io
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from codex_brief.cli import main
from codex_brief.send import display_command, prepare_command, run_command


class CliTests(unittest.TestCase):
    def run_cli(self, args, stdin=''):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch('sys.stdin', io.StringIO(stdin)), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_json_lint(self):
        code, out, _ = self.run_cli(['lint', '优化一下', '--json'])
        self.assertEqual(0, code)
        self.assertIsInstance(json.loads(out), list)

    def test_strict_lint_status(self):
        self.assertEqual(1, self.run_cli(['lint', '优化一下', '--strict'])[0])

    def test_stdin_lint(self):
        self.assertEqual(0, self.run_cli(['lint'], '生成报告')[0])

    def test_empty_input(self):
        code, _, err = self.run_cli(['lint'], '')
        self.assertEqual(2, code)
        self.assertIn('输入不能为空', err)

    def test_mutually_exclusive_input(self):
        self.assertEqual(2, self.run_cli(['lint', '文字', '--file', '-'])[0])

    def test_build_file_and_no_accidental_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'nested' / 'brief.md'
            args = ['build', '制作报告', '--out', str(path)]
            self.assertEqual(0, self.run_cli(args)[0])
            original = path.read_text(encoding='utf-8')
            self.assertEqual(2, self.run_cli(args)[0])
            self.assertEqual(original, path.read_text(encoding='utf-8'))
            self.assertEqual(0, self.run_cli(args + ['--force'])[0])

    def test_fields_file_and_override(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fields.json'
            path.write_text(json.dumps({'goal':'first'}), encoding='utf-8-sig')
            code, out, _ = self.run_cli(['build', '制作报告', '--fields', str(path), '--goal', 'second'])
            self.assertEqual(0, code)
            self.assertIn('> second', out)
            self.assertNotIn('> first', out)

    def test_interactive_stdout_is_only_markdown(self):
        answers = '制作报告\n目标\n范围\n禁区\n成功标准\n输出\n'
        code, out, err = self.run_cli(['interactive'], answers)
        self.assertEqual(0, code)
        self.assertTrue(out.startswith('# Codex 执行 brief'))
        self.assertIn('想让 Codex 做什么', err)
        self.assertNotIn('想让 Codex 做什么', out)

    def test_interactive_blank_answers_keep_placeholders(self):
        code, out, _ = self.run_cli(['interactive', '制作报告'], '\n' * 5)
        self.assertEqual(0, code)
        self.assertEqual(5, out.count('【待补充：'))

    def test_interactive_eof(self):
        self.assertEqual(130, self.run_cli(['interactive'], '')[0])

    @patch('codex_brief.cli.run_command')
    def test_send_dry_run_never_calls_codex(self, run):
        code, out, _ = self.run_cli(['send', '-', '--codex', 'not-installed'], '# brief')
        self.assertEqual(0, code)
        self.assertIn('未启动 Codex', out)
        run.assert_not_called()

    @patch('codex_brief.cli.run_command', return_value=7)
    def test_send_run_passes_stdin_and_exit_status(self, run):
        code, _, _ = self.run_cli(['send', '-', '--run'], '# brief\n中文内容')
        self.assertEqual(7, code)
        self.assertEqual('# brief\n中文内容', run.call_args.args[1])


class SendTests(unittest.TestCase):
    def test_defaults_and_no_model(self):
        command = prepare_command()
        self.assertEqual(['codex', 'exec', '--cd', '.', '--sandbox', 'read-only', '-'], command)
        self.assertNotIn('--model', command)

    def test_configurable_options(self):
        command = prepare_command(model='chosen-model', sandbox='workspace-write', skip_git_repo_check=True)
        self.assertIn('chosen-model', command)
        self.assertIn('workspace-write', command)
        self.assertIn('--skip-git-repo-check', command)

    def test_reject_invalid_parameters(self):
        for kwargs in ({'sandbox':'bad'}, {'model':''}, {'model':'--unsafe-option'},
                       {'executable':''}, {'cwd':'missing-folder-for-test'}):
            with self.assertRaises(ValueError):
                prepare_command(**kwargs)

    def test_windows_preview_quotes(self):
        result = display_command(['codex', "chosen model's name"], windows=True)
        self.assertEqual("& 'codex' 'chosen model''s name'", result)

    def test_posix_preview_quotes(self):
        self.assertIn("'chosen model'", display_command(['codex', 'chosen model'], windows=False))

    @patch('codex_brief.send.subprocess.run')
    @patch('codex_brief.send.shutil.which', return_value='codex.exe')
    def test_payload_only_via_stdin_and_no_shell(self, which, run):
        run.return_value.returncode = 4
        payload = '中文\n$(echo unsafe) `echo unsafe` ; & <tag>'
        self.assertEqual(4, run_command(prepare_command(), payload))
        self.assertNotIn(payload, run.call_args.args[0])
        self.assertEqual(payload, run.call_args.kwargs['input'])
        self.assertFalse(run.call_args.kwargs['shell'])
        self.assertEqual('utf-8', run.call_args.kwargs['encoding'])

    @patch('codex_brief.send.shutil.which', return_value=None)
    def test_missing_codex_is_clear(self, which):
        with self.assertRaisesRegex(ValueError, '未找到 Codex'):
            run_command(prepare_command(), 'brief')

    def test_empty_brief_rejected(self):
        with self.assertRaises(ValueError):
            run_command(prepare_command(), '')

    @patch('codex_brief.send.os', SimpleNamespace(name='nt'))
    @patch('codex_brief.send.shutil.which', return_value='codex.cmd')
    @patch('codex_brief.send.subprocess.run')
    def test_windows_batch_launchers_are_not_executed(self, run, which):
        with self.assertRaisesRegex(ValueError, '原生 Codex'):
            run_command(['codex', 'exec', '-'], 'brief')
        run.assert_not_called()
