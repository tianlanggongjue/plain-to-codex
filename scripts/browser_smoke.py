#!/usr/bin/env python3
"""Optional file:// smoke test using an existing Chromium browser (no download)."""
import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
<script>
(async () => {
  const checks = [];
  checks.push({name: 'viewport width ' + innerWidth, ok: innerWidth === __EXPECTED_WIDTH__});
  const check = (name, ok) => { checks.push({name, ok: Boolean(ok)}); };
  try {
    check('file protocol', location.protocol === 'file:');
    check('empty input disables generation', document.getElementById('generate').disabled);
    const input = document.getElementById('request');
    input.value = '优化一下那个页面，然后发布';
    input.dispatchEvent(new Event('input'));
    check('live lint', document.getElementById('findings').children.length > 0);
    check('danger action visible', document.getElementById('findings').textContent.includes('危险动作'));
    document.getElementById('generate').click();
    const output = document.getElementById('brief');
    check('draft placeholders', output.value.includes('【待补充：'));
    check('copy enabled', !document.getElementById('copy').disabled);
    const saved = {};
    Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {
      writeText: async value => { saved.text = value; }
    }});
    document.getElementById('copy').click();
    await Promise.resolve(); await Promise.resolve();
    check('copy receives complete brief', saved.text === output.value);
    navigator.clipboard.writeText = async () => { throw new Error('blocked'); };
    document.execCommand = command => { saved.fallback = command; return true; };
    document.getElementById('copy').click();
    await Promise.resolve(); await Promise.resolve();
    check('clipboard fallback', saved.fallback === 'copy');
    for (const [key, value] of Object.entries({goal:'库存报告', scope:'仅写 output/',
       forbidden:'禁止修改 input/', success:'逐行附来源', output:'output/report.md'})) {
      document.getElementById(key).value = value;
      document.getElementById(key).dispatchEvent(new Event('input'));
    }
    check('edited input invalidates old copy', document.getElementById('copy').disabled);
    document.getElementById('generate').click();
    check('complete fields preserved', output.value.includes('> 逐行附来源') && !output.value.includes('【待补充：'));
    input.value = '优化一下 <img src=x onerror="window.injected=true">';
    input.dispatchEvent(new Event('input'));
    document.getElementById('generate').click();
    check('user input is text', !document.querySelector('img') && !window.injected);
    check('no horizontal overflow', document.documentElement.scrollWidth <= innerWidth);
  } catch (error) { checks.push({name:'browser exception', ok:false}); }
  const result = document.createElement('pre');
  result.id = 'qa-result'; result.textContent = JSON.stringify(checks); document.body.append(result);
})();
</script>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', help='已安装 Chromium 类浏览器的可执行文件')
    args = parser.parse_args()
    browser = args.browser or next((shutil.which(name) for name in
        ('chromium', 'chromium-browser', 'google-chrome', 'chrome', 'msedge') if shutil.which(name)), None)
    if not browser:
        parser.error('未找到浏览器，请用 --browser 指定；不会自动安装')
    source = (ROOT / 'web/index.html').read_text(encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='brief-browser-') as folder:
        base = Path(folder)
        page = base / 'check.html'
        for width in (1280, 500):
            harness = HARNESS.replace('__EXPECTED_WIDTH__', str(width))
            page.write_text(source.replace('</body>', harness + '</body>'), encoding='utf-8')
            try:
                result = subprocess.run([browser, '--headless', '--no-sandbox', '--disable-gpu',
                    '--disable-dev-shm-usage', '--disable-background-networking',
                    '--disable-extensions', '--no-first-run',
                    '--window-size=' + str(width) + ',900', '--virtual-time-budget=3000',
                    '--dump-dom', page.as_uri()], capture_output=True, text=True, encoding='utf-8', timeout=30)
            except subprocess.TimeoutExpired:
                raise SystemExit('FAIL: 本地浏览器检查超时；可尝试另一个已安装的 Chromium 浏览器') from None
            match = re.search(r'<pre id="qa-result">(.*?)</pre>', result.stdout, re.S)
            if result.returncode or not match:
                raise SystemExit('FAIL: 浏览器未完成本地页面检查')
            checks = json.loads(match.group(1))
            for item in checks:
                print('{} {}px: {}'.format('PASS' if item['ok'] else 'FAIL', width, item['name']))
            if not all(item['ok'] for item in checks):
                return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
