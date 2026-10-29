"""Rule engine shared in behavior with the offline browser implementation."""

import copy
import json
import re
from importlib import resources
from pathlib import Path
from string import Formatter

FIELD_KEYS = ("goal", "scope", "forbidden", "success", "output")
PLACEHOLDER = r"^\s*(?:【|\[)?(?:待补充|待确认|待定|未知|TODO|TBD|UNKNOWN|[?？]+)(?:[：:].*|】|\])?\s*$"
SENTENCES = r"[。！？!?；;\n]+|\.(?:\s|$)"
CLAUSES = r"[，,]+|但是|不过|然而|\bbut\b"


def meaningful(value):
    return isinstance(value, str) and bool(value.strip()) and not re.search(
        PLACEHOLDER, value, re.I
    )


def load_config(path=None):
    """Merge user rules by id; replace guardrails/template when supplied."""
    config = json.loads(resources.files(__package__).joinpath("defaults.json").read_text(encoding="utf-8"))
    if path is not None:
        custom = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        if not isinstance(custom, dict):
            raise ValueError("配置必须是 JSON 对象")
        if set(custom) - {"rules", "guardrails", "template"}:
            raise ValueError("配置只支持 rules、guardrails、template")
        config = merge_config(config, custom)
    validate_config(config)
    return config


def merge_config(base, custom):
    result = copy.deepcopy(base)
    if "rules" in custom:
        if not isinstance(custom["rules"], list):
            raise ValueError("rules 必须是数组")
        rules = {r["id"]: r for r in result["rules"]}
        seen = set()
        for rule in custom["rules"]:
            if not isinstance(rule, dict) or not isinstance(rule.get("id"), str):
                raise ValueError("每条规则必须有字符串 id")
            if rule["id"] in seen:
                raise ValueError("自定义规则 id 重复")
            seen.add(rule["id"])
            rules[rule["id"]] = {**rules.get(rule["id"], {}), **rule}
        result["rules"] = list(rules.values())
    for key in ("guardrails", "template"):
        if key in custom:
            result[key] = custom[key]
    return result


def validate_config(config):
    if not isinstance(config.get("guardrails"), list) or not all(
        isinstance(s, str) and s.strip() for s in config["guardrails"]
    ):
        raise ValueError("guardrails 必须是非空字符串组成的数组")
    template = config.get("template")
    if not isinstance(template, str) or not template.strip():
        raise ValueError("template 必须是非空 Markdown 字符串")
    allowed = set(FIELD_KEYS) | {"request", "guardrails", "status"}
    used = set()
    for _, name, spec, conversion in Formatter().parse(template):
        if name is not None:
            if name not in allowed or spec or conversion:
                raise ValueError("模板只能使用简单占位符：" + ", ".join(sorted(allowed)))
            used.add(name)
    if used != allowed:
        raise ValueError("模板必须保留全部占位符：" + ", ".join(sorted(allowed)))
    for rule in config["rules"]:
        if not isinstance(rule.get("enabled", True), bool):
            raise ValueError("enabled 必须是布尔值")
        if not rule.get("enabled", True):
            continue
        for key in ("id", "kind", "title", "why", "suggestion", "severity"):
            if not isinstance(rule.get(key), str) or not rule[key].strip():
                raise ValueError("规则缺少字符串字段：" + key)
        if rule["kind"] not in {"match", "missing", "multiple", "danger"}:
            raise ValueError("不支持的规则类型：" + rule["kind"])
        if rule["severity"] not in {"info", "warning", "error"}:
            raise ValueError("severity 必须是 info、warning 或 error")
        if rule.get("field") is not None and rule["field"] not in FIELD_KEYS:
            raise ValueError("未知的 field")
        required = {
            "match": ("pattern",), "missing": ("pattern",),
            "multiple": ("pattern", "connector"),
            "danger": ("pattern", "negative", "confirm", "bypass", "global_confirm"),
        }[rule["kind"]]
        for key in required:
            if not isinstance(rule.get(key), str) or not rule[key]:
                raise ValueError("规则缺少正则表达式：" + key)
        for key in ("pattern", "connector", "negative", "confirm", "bypass", "global_confirm", "when"):
            if key in rule:
                if not isinstance(rule[key], str):
                    raise ValueError("正则表达式必须是字符串：" + key)
                re.compile(rule[key], re.I)


def normalize_fields(fields=None):
    fields = {} if fields is None else fields
    if not isinstance(fields, dict) or set(fields) - set(FIELD_KEYS):
        raise ValueError("补充字段只支持 goal、scope、forbidden、success、output")
    if not all(isinstance(value, str) for value in fields.values()):
        raise ValueError("补充字段的值必须是字符串")
    return {key: fields.get(key, "").strip() for key in FIELD_KEYS}


def danger_evidence(text, rule):
    """Confirmations apply to their clause; unrelated prohibitions do not hide risk."""
    global_confirm = any(
        re.search(rule["global_confirm"], sentence, re.I)
        and not re.search(rule["bypass"], sentence, re.I)
        for sentence in re.split(SENTENCES, text)
    )
    found = []
    for sentence in re.split(SENTENCES, text):
        for clause in re.split(CLAUSES, sentence, flags=re.I):
            confirmed = (global_confirm or re.search(rule["confirm"], clause, re.I)) and not re.search(rule["bypass"], clause, re.I)
            previous_end = 0
            prohibited = False
            for match in re.finditer(rule["pattern"], clause, re.I):
                prefix = clause[previous_end:match.start()]
                # Carry a negation only across an explicit list of actions.
                prohibited = bool(re.search(rule["negative"], prefix, re.I)) or (
                    prohibited and bool(re.fullmatch(r"\s*(?:、|和|或|以及|and|or)\s*", prefix, re.I))
                )
                if not prohibited and not confirmed:
                    found.append(match.group())
                previous_end = match.end()
    return list(dict.fromkeys(found))


def lint(text, fields=None, config=None):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("输入不能为空")
    config = config if config is not None else load_config()
    fields = normalize_fields(fields)
    combined = "\n".join([text] + [value for value in fields.values() if value])
    # Placeholder lines never satisfy a missing-information rule.
    supplied = "\n".join(
        part for part in re.split(SENTENCES, combined)
        if meaningful(re.sub(r"^[^:：\n]{1,24}[：:][ \t]*", "", part))
    )
    findings = []
    for rule in config["rules"]:
        if not rule.get("enabled", True):
            continue
        if rule.get("when") and not re.search(rule["when"], combined, re.I):
            continue
        kind = rule["kind"]
        evidence = []
        triggered = False
        if kind == "match":
            evidence = list(dict.fromkeys(m.group() for m in re.finditer(rule["pattern"], combined, re.I)))
            triggered = bool(evidence)
        elif kind == "missing":
            field = rule.get("field")
            # An explicit but empty/unknown field cannot be rescued by a keyword elsewhere.
            if field and fields[field]:
                triggered = not meaningful(fields[field])
            else:
                triggered = not re.search(rule["pattern"], supplied, re.I)
        elif kind == "multiple":
            for sentence in re.split(SENTENCES, text):
                actions = list(re.finditer(rule["pattern"], sentence, re.I))
                if len(actions) > 1 and re.search(rule["connector"], sentence, re.I):
                    evidence.append(sentence.strip())
            triggered = bool(evidence)
        elif kind == "danger":
            evidence = danger_evidence(combined, rule)
            triggered = bool(evidence)
        if triggered:
            findings.append({key: rule[key] for key in ("id", "severity", "title", "why", "suggestion")})
            findings[-1]["evidence"] = evidence
    return findings


def build_brief(text, fields=None, config=None):
    if not text.strip():
        raise ValueError("原始需求不能为空")
    config = config if config is not None else load_config()
    values = normalize_fields(fields)
    missing = [f["title"] for f in config["fields"] if not meaningful(values[f["key"]])]
    for field in config["fields"]:
        if not meaningful(values[field["key"]]):
            original = values[field["key"]]
            values[field["key"]] = "【待补充：" + field["prompt"] + "】"
            if original:
                values[field["key"]] += "\n用户原填：" + original
    values["status"] = (
        "草稿：仍需补充「" + "、".join(missing) + "」。先澄清这些字段，再执行依赖它们的工作。"
        if missing else "五项字段已填写；请逐项检查原始需求与补充字段是否一致。此状态不代表通过验收。"
    )
    # Quote source prose so Markdown in it cannot impersonate a generated section.
    for key in FIELD_KEYS:
        values[key] = "\n".join("> " + line for line in values[key].splitlines())
    values["request"] = "\n".join("> " + line for line in text.strip().splitlines())
    values["guardrails"] = "\n".join("- " + item for item in config["guardrails"])
    return config["template"].format_map(values).rstrip() + "\n"


def format_findings(findings):
    if not findings:
        return "未发现规则命中的问题；这不代表需求已完整或可安全执行。"
    labels = {"info": "提醒", "warning": "建议补充", "error": "高风险"}
    lines = ["发现 {} 项可改进之处：".format(len(findings))]
    for i, item in enumerate(findings, 1):
        lines.append("\n{}. [{}] {} ({})".format(i, labels[item["severity"]], item["title"], item["id"]))
        if item["evidence"]:
            lines.append("   命中：" + " / ".join(item["evidence"]))
        lines.append("   为什么会让 Codex 误解：" + item["why"])
        lines.append("   建议怎么补：" + item["suggestion"])
    return "\n".join(lines)
