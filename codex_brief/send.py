"""Prepare argv without evaluating prompt text or launching a shell."""

import os
import shlex
import shutil
import subprocess
from pathlib import Path

SANDBOXES = ("read-only", "workspace-write", "danger-full-access")


def prepare_command(cwd=".", model=None, sandbox="read-only", executable="codex", skip_git_repo_check=False):
    if sandbox not in SANDBOXES:
        raise ValueError("不支持的沙箱参数")
    if not Path(cwd).is_dir():
        raise ValueError("工作目录不存在或不是目录")
    if not executable.strip() or "\x00" in executable:
        raise ValueError("Codex 可执行文件不能为空或含空字符")
    command = [executable, "exec", "--cd", str(cwd), "--sandbox", sandbox]
    if model is not None:
        if not model.strip() or "\x00" in model or model.startswith("-"):
            raise ValueError("模型参数不能为空、含空字符或以连字符开头")
        command.extend(["--model", model])
    if skip_git_repo_check:
        command.append("--skip-git-repo-check")
    return command + ["-"]


def display_command(command, windows=None):
    """Windows previews use PowerShell literal quoting; execution always uses argv."""
    if windows is None:
        windows = os.name == "nt"
    if windows:
        return "& " + " ".join("'" + part.replace("'", "''") + "'" for part in command)
    return shlex.join(command)


def run_command(command, brief):
    if not brief.strip():
        raise ValueError("brief 不能为空")
    executable = shutil.which(command[0])
    if executable is None:
        raise ValueError("未找到 Codex；请先安装，或用 --codex 指定可执行文件")
    # Windows can route .cmd/.bat through cmd.exe even with shell=False.
    if os.name == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
        raise ValueError("请用 --codex 指向原生 Codex .exe；不执行批处理启动器")
    return subprocess.run(
        [executable] + command[1:], input=brief, text=True,
        encoding="utf-8", shell=False, check=False,
    ).returncode
