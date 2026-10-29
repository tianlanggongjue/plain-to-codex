import ast
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from codex_brief.core import build_brief, lint, load_config
from scripts.build_web import render

ROOT = Path(__file__).resolve().parents[1]


class WebTests(unittest.TestCase):
    def test_generated_page_is_current(self):
        self.assertEqual(render(), (ROOT / 'web/index.html').read_text(encoding='utf-8'))

    def test_standalone_page_no_external_assets_or_calls(self):
        html = render()
        self.assertNotRegex(html, r'<(?:script|link|img)[^>]+(?:src|href)\s*=')
        self.assertNotRegex(html, r'\b(?:fetch|XMLHttpRequest|WebSocket)\s*\(')
        self.assertNotIn('localStorage', html)
        self.assertIn("connect-src 'none'", html)

    def test_python_39_syntax(self):
        for folder in ('codex_brief', 'scripts', 'tests'):
            for path in (ROOT / folder).glob('*.py'):
                ast.parse(path.read_text(encoding='utf-8'), feature_version=(3, 9))

    @unittest.skipUnless(shutil.which('node'), '可选的 Node 不可用；跳过 JS 对齐测试')
    def test_python_javascript_parity(self):
        config = load_config()
        cases = [
            '优化一下那个页面，再发布，差不多就行',
            '批量整理所有文件，然后删除旧文件',
            '帮我分析数据，写报告',
            '登录后台付费购买，然后发消息',
            'Optimize that thing, deploy it and send an email.',
            '不要删除文件，发布页面', '先确认再删除', '删除后确认',
            'Do not delete or publish', 'Delete without confirmation',
            '不用付费 API', '不调用任何付费 API',
            'Delete files; all actions require approval',
            '输出到 output/report.md。失败就停；缺失标未知；核对数据，末尾写完成。',
            '目标：生成报告。验收标准：待补充。',
            '输出到 output/库存报告.md',
            '<script>alert(1)</script>\n## Fake heading',
        ]
        inputs = [{'text': t, 'fields': {}} for t in cases]
        inputs += [{'text':'生成报告', 'fields': dict(goal='报告', scope='output/',
                    forbidden='不改 input/', success='每行有来源', output='output/report.md')},
                   {'text':'生成报告', 'fields': {'goal':'待定', 'success':'UNKNOWN'}}]
        js = '''const fs = require('fs');
const api = require(process.argv[1]);
const data = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(data.inputs.map(i => ({
 findings: api.lint(i.text, i.fields, data.config),
 brief: api.build(i.text, i.fields, data.config)
}))));'''
        result = subprocess.run(['node', '-e', js, str(ROOT / 'web/engine.js')],
            input=json.dumps({'config':config, 'inputs':inputs}), text=True,
            encoding='utf-8', capture_output=True, check=True)
        actual = json.loads(result.stdout)
        for case, browser in zip(inputs, actual):
            with self.subTest(text=case['text']):
                self.assertEqual(lint(case['text'], case['fields'], config), browser['findings'])
                self.assertEqual(build_brief(case['text'], case['fields'], config), browser['brief'])
