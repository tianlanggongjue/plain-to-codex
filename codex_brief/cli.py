"""Chinese CLI. No network clients, API keys, or model defaults."""

import argparse
import json
import re
import sys
from pathlib import Path

from . import __version__
from .core import FIELD_KEYS, build_brief, format_findings, lint, load_config, normalize_fields
from .send import SANDBOXES, display_command, prepare_command, run_command


def parser():
    root = argparse.ArgumentParser(prog="codex-brief", description="把大白话整理成边界清晰的 Codex brief；默认完全离线。")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command")
    for name, description in (("lint", "检查歧义和缺失"), ("build", "生成 Markdown brief"), ("interactive", "交互问答生成 brief")):
        sub = commands.add_parser(name, help=description, description=description)
        sub.add_argument("text", nargs="?", help="原始需求；也可从 --file 或标准输入读取")
        sub.add_argument("--file", type=Path, help="UTF-8 输入文件，- 表示标准输入")
        sub.add_argument("--config", type=Path, help="自定义规则及模板 JSON")
        sub.add_argument("--fields", type=Path, help="五项补充字段 JSON")
        for key, label in zip(FIELD_KEYS, ("目标", "范围白名单", "禁区", "成功标准", "输出位置及格式")):
            sub.add_argument("--" + key, help=label)
        if name == "lint":
            sub.add_argument("--json", action="store_true", help="输出 JSON 问题清单")
            sub.add_argument("--strict", action="store_true", help="有任何问题时返回退出码 1")
        else:
            sub.add_argument("-o", "--out", type=Path, help="brief 保存位置；省略则打印")
            sub.add_argument("--force", action="store_true", help="允许覆盖已有输出文件")
    send = commands.add_parser("send", help="预览 codex exec 命令；--run 才执行")
    send.add_argument("brief", type=Path, help="UTF-8 brief 文件，- 表示标准输入")
    send.add_argument("--model", help="原样传给 Codex；省略则使用本机 Codex 配置")
    send.add_argument("--cwd", default=".", help="Codex 工作目录，默认当前目录")
    send.add_argument("--sandbox", choices=SANDBOXES, default="read-only")
    send.add_argument("--codex", default="codex", help="Codex 可执行文件名或位置")
    send.add_argument("--skip-git-repo-check", action="store_true", help="允许在非 Git 目录运行")
    send.add_argument("--run", action="store_true", help="实际调用本机 Codex，可能联网并产生费用")
    return root


def read_path(path):
    return sys.stdin.read() if str(path) == "-" else path.read_text(encoding="utf-8-sig")


def read_text(args, interactive=False):
    if args.text is not None and args.file is not None:
        raise ValueError("text 与 --file 只能选择一个")
    if args.file is not None:
        text = read_path(args.file)
    elif args.text is not None:
        text = args.text
    elif interactive:
        print("想让 Codex 做什么？\n> ", end="", file=sys.stderr, flush=True)
        text = input()
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        raise ValueError("请提供需求文字、--file，或使用 interactive")
    if not text.strip():
        raise ValueError("输入不能为空")
    return text


def read_fields(args):
    fields = json.loads(args.fields.read_text(encoding="utf-8-sig")) if args.fields else {}
    fields = normalize_fields(fields)
    for key in FIELD_KEYS:
        if getattr(args, key) is not None:
            fields[key] = getattr(args, key)
    return fields


def write_brief(brief, out, force=False):
    if out is None:
        print(brief, end="")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with out.open("w" if force else "x", encoding="utf-8", newline="\n") as stream:
            stream.write(brief)
    except FileExistsError:
        raise ValueError("输出文件已存在；换一个文件名，或明确加 --force 覆盖") from None
    print("brief 已保存。", file=sys.stderr)


def main(argv=None):
    root = parser()
    args = root.parse_args(argv)
    if args.command is None:
        root.print_help()
        return 0
    try:
        if args.command == "send":
            brief = read_path(args.brief)
            if not brief.strip():
                raise ValueError("brief 不能为空")
            command = prepare_command(args.cwd, args.model, args.sandbox, args.codex, args.skip_git_repo_check)
            print(display_command(command), flush=True)
            print("brief 将通过 UTF-8 标准输入传入；上方命令仅用于预览参数。", flush=True)
            if not args.run:
                print("预览完成，未启动 Codex。加 --run 才执行；执行可能联网并产生费用。")
                return 0
            print("正在调用本机 Codex；使用其现有配置。", flush=True)
            return run_command(command, brief)
        config = load_config(args.config)
        text = read_text(args, args.command == "interactive")
        fields = read_fields(args)
        if args.command == "lint":
            findings = lint(text, fields, config)
            print(json.dumps(findings, ensure_ascii=False, indent=2) if args.json else format_findings(findings))
            return int(args.strict and bool(findings))
        if args.command == "interactive":
            print(format_findings(lint(text, fields, config)), file=sys.stderr)
            print("逐项补充；留空将保留待补充标记，不会替你猜。", file=sys.stderr)
            for field in config["fields"]:
                key = field["key"]
                suffix = "（回车保留已填内容）" if fields[key] else ""
                # Questions use stderr, so redirected stdout stays valid Markdown.
                print(field["title"] + "：" + field["prompt"] + suffix + "\n> ", end="", file=sys.stderr, flush=True)
                answer = input().strip()
                if answer:
                    fields[key] = answer
        write_brief(build_brief(text, fields, config), args.out, args.force)
        return 0
    except (ValueError, OSError, re.error) as error:
        print("错误：" + str(error), file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        print("\n已取消。", file=sys.stderr)
        return 130


def entrypoint():
    # Respect redirected UTF-8 files and Windows consoles without locale guessing.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
