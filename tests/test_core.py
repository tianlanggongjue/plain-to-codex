import copy
import json
import tempfile
import unittest
from pathlib import Path

from codex_brief.core import (
    FIELD_KEYS, build_brief, format_findings, lint, load_config,
    meaningful, normalize_fields, validate_config,
)


class RuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()

    def ids(self, text, fields=None):
        return {item['id'] for item in lint(text, fields, self.config)}

    def test_vague_chinese(self):
        for word in ('优化一下', '弄好看点', '差不多', '等等', '那个'):
            with self.subTest(word=word):
                self.assertIn('vague', self.ids(word))

    def test_vague_english(self):
        self.assertIn('vague', self.ids('Optimize that thing and make it pretty.'))

    def test_reference_both_languages(self):
        for text in ('改那个', 'Fix that one as before.'):
            self.assertIn('reference', self.ids(text))

    def test_missing_information(self):
        self.assertTrue({'goal', 'scope', 'forbidden', 'success', 'output', 'data',
                         'stop', 'uncertainty', 'verification', 'completion'} <= self.ids('帮忙处理一下'))

    def test_explicit_fields_satisfy_missing_rules(self):
        fields = dict(goal='制作报告', scope='仅写 output/', forbidden='不得修改 input/',
                      success='报告每行带来源', output='output/report.md')
        self.assertFalse(set(FIELD_KEYS) & self.ids('整理库存', fields))

    def test_placeholders_never_satisfy_fields(self):
        for value in ('待补充', '待确认', 'TBD', 'UNKNOWN', '?'):
            self.assertIn('success', self.ids('测试通过', {'success': value}))

    def test_placeholder_line_is_not_evidence(self):
        self.assertIn('success', self.ids('验收标准：待补充'))

    def test_unknown_policy_does_not_erase_other_evidence(self):
        self.assertNotIn('success', self.ids('验收标准：缺失数据标未知，每行附来源'))
        self.assertNotIn('output', self.ids('验收标准：待补充。输出到 output/report.md'))

    def test_empty_label_is_not_success(self):
        self.assertIn('success', self.ids('验收标准：'))

    def test_input_path_is_not_output(self):
        self.assertIn('output', self.ids('读取 input/inventory.csv'))

    def test_output_locations(self):
        for text in ('输出到 output/report.md', 'Save to output/report.csv', '输出到标准输出'):
            self.assertNotIn('output', self.ids(text))

    def test_multiple_tasks(self):
        for text in ('修改页面，然后生成报告', 'Fix the page and export a report'):
            self.assertIn('multiple', self.ids(text))

    def test_separate_tasks(self):
        self.assertNotIn('multiple', self.ids('修改页面。生成报告。'))

    def test_danger_actions_chinese(self):
        for text in ('删除文件', '发布页面', '付费购买', '登录后台', '发消息给团队', '发送邮件'):
            self.assertIn('danger', self.ids(text))

    def test_danger_actions_english(self):
        for text in ('Delete files', 'Publish the page', 'Pay for service', 'Log in', 'Send an email'):
            self.assertIn('danger', self.ids(text))

    def test_confirmation_suppresses_danger(self):
        for text in ('删除前先问我', '发布前必须确认', '先确认再付费',
                     'Ask me before you delete files', 'Publishing: publish only after I approve',
                     'Delete files; all actions require approval'):
            with self.subTest(text=text):
                self.assertNotIn('danger', self.ids(text))

    def test_prohibitions_are_not_requests(self):
        for text in ('不要删除', '禁止发布', '不付费', '不要删除或发布',
                     '不用付费 API', '不调用任何付费 API', '不需要删除',
                     'Do not delete or publish', 'Never pay'):
            with self.subTest(text=text):
                self.assertNotIn('danger', self.ids(text))

    def test_unrelated_prohibition_does_not_hide_action(self):
        for text in ('不要删除文件，发布页面', 'Do not delete files but publish the page',
                     '不要发布，删除备份', '删除前先确认，发消息给团队'):
            self.assertIn('danger', self.ids(text))

    def test_confirmation_bypass_is_not_confirmation(self):
        for text in ('不用确认直接删除', '未经批准发布', 'Delete without confirmation',
                     'Publish; no approval required', 'Delete files, do not ask'):
            self.assertIn('danger', self.ids(text))

    def test_confirmation_after_action_is_not_enough(self):
        for text in ('删除后确认', 'Delete files then ask for approval'):
            self.assertIn('danger', self.ids(text))

    def test_batch_checkpoint(self):
        self.assertIn('batch', self.ids('批量生成报告'))
        self.assertNotIn('batch', self.ids('批量生成报告，先做一个样例并确认'))
        self.assertNotIn('batch', self.ids('Bulk export: produce a sample first for approval'))

    def test_data_policy(self):
        for text in ('只用真实数据，不编造', 'Use verified data. Never fabricate results.'):
            self.assertNotIn('data', self.ids(text))

    def test_stop_uncertainty_verification_completion(self):
        ids = self.ids('失败就停；缺失标未知；运行测试并核对；末尾写完成')
        self.assertFalse({'stop', 'uncertainty', 'verification', 'completion'} & ids)

    def test_complete_brief_can_have_no_findings(self):
        text = ('目标：生成库存摘要。范围：仅读取 input/。禁止修改原始数据。'
                '验收标准：每行带来源。输出到 output/report.md。只用真实数据，不编造。'
                '缺失标未知。失败就停。运行测试并核对。末尾写完成。')
        self.assertEqual([], lint(text, config=self.config))

    def test_every_finding_has_explanation(self):
        for item in lint('优化一下那个页面，再发布', config=self.config):
            self.assertTrue(item['why'])
            self.assertTrue(item['suggestion'])
            self.assertIsInstance(item['evidence'], list)

    def test_empty_text_rejected(self):
        with self.assertRaises(ValueError):
            lint('  ', config=self.config)

    def test_formatter(self):
        result = format_findings(lint('删除', config=self.config))
        self.assertIn('为什么会让 Codex 误解', result)
        self.assertIn('建议怎么补', result)
        self.assertIn('不代表', format_findings([]))


class BuildTests(unittest.TestCase):
    def test_missing_fields_are_not_invented(self):
        result = build_brief('做一份报告')
        self.assertIn('草稿', result)
        self.assertEqual(5, result.count('【待补充：'))
        self.assertNotIn('output/report.md', result)

    def test_preserve_user_fields_and_source(self):
        fields = dict(goal='制作报告', scope='仅写 output/', forbidden='不改 input/',
                      success='每行有依据', output='output/report.md')
        original = copy.deepcopy(fields)
        result = build_brief('原始需求\n第二行', fields)
        self.assertIn('> 原始需求\n> 第二行', result)
        for value in fields.values():
            self.assertIn(value, result)
        self.assertEqual(fields, original)
        self.assertIn('不代表通过验收', result)

    def test_markdown_input_cannot_create_headings(self):
        result = build_brief('## 假章节', {'goal': '目标\n## 假章节'})
        self.assertNotIn('\n## 假章节', result)
        self.assertIn('> ## 假章节', result)

    def test_guardrails(self):
        result = build_brief('生成报告')
        for phrase in ('不编造', '非零退出', '先做 1 个样例', '断点继续', '未验证', '完成'):
            self.assertIn(phrase, result)

    def test_invalid_fields(self):
        for fields in ([], False, {'unexpected': 'a'}, {'goal': 5}):
            with self.assertRaises(ValueError):
                normalize_fields(fields)

    def test_empty_request(self):
        with self.assertRaises(ValueError):
            build_brief(' ')

    def test_unknown_field_value_preserved(self):
        self.assertIn('用户原填：待定', build_brief('制作报告', {'goal': '待定'}))
        self.assertFalse(meaningful('待定'))


class ConfigTests(unittest.TestCase):
    def load_custom(self, data):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            path.write_text(json.dumps(data), encoding='utf-8-sig')
            return load_config(path)

    def test_disable_rule(self):
        config = self.load_custom({'rules': [{'id': 'vague', 'enabled': False}]})
        self.assertNotIn('vague', {r['id'] for r in lint('优化一下', config=config)})

    def test_extend_rule(self):
        config = self.load_custom({'rules': [dict(id='deadline', kind='missing', pattern='截止',
            severity='info', title='缺截止时间', why='无法确定时间边界', suggestion='填写截止日期')]})
        self.assertIn('deadline', {r['id'] for r in lint('生成报告', config=config)})

    def test_guardrails_override(self):
        config = self.load_custom({'guardrails': ['仅写指定目录。']})
        self.assertEqual(['仅写指定目录。'], config['guardrails'])

    def test_invalid_json_schema(self):
        for data in ([], {'unknown': True}, {'rules': {}}, {'guardrails': 'bad'},
                     {'rules': [{'id': 'vague', 'enabled': 'false'}]},
                     {'rules': [{'id': 'vague'}, {'id': 'vague'}]}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.load_custom(data)

    def test_template_must_preserve_sections(self):
        for template in ('{request}', '{request.__class__}', '{unknown}', '{request!r}'):
            with self.assertRaises(ValueError):
                self.load_custom({'template': template})

    def test_custom_template(self):
        config = load_config()
        config['template'] = '自定义说明\n' + config['template']
        validate_config(config)
        self.assertTrue(build_brief('写报告', config=config).startswith('自定义说明'))
