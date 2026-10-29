#!/usr/bin/env python3
"""Embed defaults and engine into a self-contained HTML file; no dependencies."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render():
    config = json.loads((ROOT / 'codex_brief' / 'defaults.json').read_text(encoding='utf-8'))
    embedded = json.dumps(config, ensure_ascii=False).replace('<', '\\u003c')
    engine = (ROOT / 'web' / 'engine.js').read_text(encoding='utf-8')
    template = (ROOT / 'web' / 'template.html').read_text(encoding='utf-8')
    return template.replace('__CONFIG__', embedded).replace('__ENGINE__', engine)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='检查已生成页面是否与源码一致')
    args = parser.parse_args()
    target = ROOT / 'web' / 'index.html'
    html = render()
    if args.check:
        if not target.exists() or target.read_text(encoding='utf-8') != html:
            raise SystemExit('页面需要更新：python scripts/build_web.py')
        print('离线页面与默认规则、引擎、模板一致。')
    else:
        target.write_text(html, encoding='utf-8')
        print('已生成 web/index.html。')
