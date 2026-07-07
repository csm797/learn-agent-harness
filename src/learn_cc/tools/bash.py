"""
bash — Shell 命令执行工具。

安全注意：
- 危险命令（rm -rf /, sudo, shutdown）被拦截
- 超时 120 秒后自动终止
- 输出截断为 50000 字符
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# 危险命令模式 —— 只要命令中包含这些关键词就拦截
DANGEROUS_PATTERNS = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]

TIMEOUT_SECONDS = 120
MAX_OUTPUT_CHARS = 50_000


def run_bash(command: str, workdir: Path) -> str:
    """
    执行 shell 命令并返回输出。

    Args:
        command: 要执行的 shell 命令。
        workdir: 工作目录。

    Returns:
        命令输出文本（stdout + stderr），超出部分截断。
    """
    # 安全检查
    for pattern in DANGEROUS_PATTERNS:
        if pattern in command:
            return f"错误: 危险命令已被拦截（匹配模式: {pattern}）"

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=workdir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_SECONDS,
        )
        output = (result.stdout + result.stderr).strip()
        return output[:MAX_OUTPUT_CHARS] if output else "(无输出)"
    except subprocess.TimeoutExpired:
        return f"错误: 命令执行超时（{TIMEOUT_SECONDS}s）"
    except (FileNotFoundError, OSError) as e:
        return f"错误: {e}"
