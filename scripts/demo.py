#!/usr/bin/env python3
"""Run five CLI lint demos and build generic, reproducible examples."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    sys.path.insert(0, str(ROOT))
    from codex_brief.core import build_brief
    cases = json.loads((ROOT / 'examples/cases.json').read_text(encoding='utf-8'))
    report = ['# 五条典型输入的 lint 演示', '',
              '以下为实际 CLI 输出。普通 lint 返回 0；使用 --strict 时，有提示则返回 1。', '']
    examples = ['# 从大白话到可检查的 brief', '',
                '全部是通用虚构任务场景，不代表真实业务或运行数据。', '',
                '改写时由用户补充明确字段；原始需求保留供核对，冲突处需澄清。', '']
    for index, case in enumerate(cases, 1):
        result = subprocess.run([sys.executable, '-m', 'codex_brief', 'lint', case['text']],
            cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        if result.returncode:
            raise SystemExit('lint 演示执行失败')
        brief = build_brief(case['text'], case['fields'])
        (ROOT / 'examples' / (case['id'] + '.md')).write_text(brief, encoding='utf-8')
        title = '## {}. {}'.format(index, case['text'])
        report += [title, '', '退出码：{}'.format(result.returncode), '', '```text', result.stdout.rstrip(), '```', '']
        examples += [title, '', '### 检查结果', '', '```text', result.stdout.rstrip(), '```', '',
                     '### 补充字段后生成的 brief', '', '```markdown', brief.rstrip(), '```', '']
        print('示例 {}：{}；退出码 {}'.format(index, result.stdout.splitlines()[0], result.returncode))
    out = ROOT / 'out/qa'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'lint-demo.md').write_text('\n'.join(report), encoding='utf-8')
    (ROOT / 'examples/README.md').write_text('\n'.join(examples), encoding='utf-8')


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main()
