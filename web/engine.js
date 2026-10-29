/* Shared rule data is embedded by scripts/build_web.py. No network calls. */
(function (root) {
  'use strict';
  const keys = ['goal', 'scope', 'forbidden', 'success', 'output'];
  const sentences = /[。！？!?；;\n]+|\.(?:\s|$)/;
  const clauses = /[，,]+|但是|不过|然而|\bbut\b/i;
  const meaningful = value => typeof value === 'string' && !!value.trim() &&
    !/^\s*(?:【|\[)?(?:待补充|待确认|待定|未知|TODO|TBD|UNKNOWN|[?？]+)(?:[：:].*|】|\])?\s*$/i.test(value);
  const has = (pattern, value) => new RegExp(pattern, 'i').test(value);
  const unique = items => Array.from(new Set(items));
  const matches = (pattern, value) => Array.from(value.matchAll(new RegExp(pattern, 'gi')));
  function normalize(fields = {}) {
    if (!fields || Array.isArray(fields) || typeof fields !== 'object' ||
        Object.keys(fields).some(k => !keys.includes(k) || typeof fields[k] !== 'string')) {
      throw new Error('补充字段只支持五项文本字段');
    }
    return Object.fromEntries(keys.map(k => [k, (fields[k] || '').trim()]));
  }
  function dangerEvidence(text, rule) {
    const globalConfirm = text.split(sentences).some(s =>
      has(rule.global_confirm, s) && !has(rule.bypass, s));
    const found = [];
    for (const sentence of text.split(sentences)) {
      for (const clause of sentence.split(clauses)) {
        const confirmed = (globalConfirm || has(rule.confirm, clause)) && !has(rule.bypass, clause);
        let previousEnd = 0, prohibited = false;
        for (const m of matches(rule.pattern, clause)) {
          const prefix = clause.slice(previousEnd, m.index);
          prohibited = has(rule.negative, prefix) ||
            (prohibited && /^\s*(?:、|和|或|以及|and|or)\s*$/i.test(prefix));
          if (!prohibited && !confirmed) found.push(m[0]);
          previousEnd = m.index + m[0].length;
        }
      }
    }
    return unique(found);
  }
  function lint(text, fields, config) {
    if (typeof text !== 'string' || !text.trim()) throw new Error('输入不能为空');
    fields = normalize(fields);
    const combined = [text, ...Object.values(fields).filter(Boolean)].join('\n');
    const supplied = combined.split(sentences).filter(part =>
      meaningful(part.replace(/^[^:：\n]{1,24}[：:][ \t]*/, ''))).join('\n');
    const findings = [];
    for (const rule of config.rules) {
      if (rule.enabled === false || (rule.when && !has(rule.when, combined))) continue;
      let evidence = [], triggered = false;
      if (rule.kind === 'match') {
        evidence = unique(matches(rule.pattern, combined).map(m => m[0]));
        triggered = !!evidence.length;
      } else if (rule.kind === 'missing') {
        triggered = rule.field && fields[rule.field] ?
          !meaningful(fields[rule.field]) : !has(rule.pattern, supplied);
      } else if (rule.kind === 'multiple') {
        evidence = text.split(sentences).filter(s =>
          matches(rule.pattern, s).length > 1 && has(rule.connector, s)).map(s => s.trim());
        triggered = !!evidence.length;
      } else if (rule.kind === 'danger') {
        evidence = dangerEvidence(combined, rule);
        triggered = !!evidence.length;
      }
      if (triggered) {
        const item = {};
        for (const key of ['id', 'severity', 'title', 'why', 'suggestion']) item[key] = rule[key];
        findings.push({...item, evidence});
      }
    }
    return findings;
  }
  function build(text, fields, config) {
    if (!text.trim()) throw new Error('原始需求不能为空');
    const values = normalize(fields);
    const missing = config.fields.filter(f => !meaningful(values[f.key])).map(f => f.title);
    for (const field of config.fields) {
      if (!meaningful(values[field.key])) {
        const original = values[field.key];
        values[field.key] = '【待补充：' + field.prompt + '】' + (original ? '\n用户原填：' + original : '');
      }
    }
    values.status = missing.length ?
      '草稿：仍需补充「' + missing.join('、') + '」。先澄清这些字段，再执行依赖它们的工作。' :
      '五项字段已填写；请逐项检查原始需求与补充字段是否一致。此状态不代表通过验收。';
    const quote = value => value.split(/\r?\n/).map(line => '> ' + line).join('\n');
    for (const key of keys) values[key] = quote(values[key]);
    values.request = quote(text.trim());
    values.guardrails = config.guardrails.map(item => '- ' + item).join('\n');
    return config.template.replace(/\{(\w+)\}/g, (_, key) => values[key]).trimEnd() + '\n';
  }
  const api = {lint, build, meaningful};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.CodexBrief = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
