"""
bash — Shell 命令执行工具。

安全防线：
1. 正则 deny patterns（Gate 1 的加强版）
2. Allowlist 覆盖（用户配置可放行）
3. 超时自动终止（120s）
4. 输出截断（50000 chars）
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Sequence

# 正则 deny patterns — 参照 nanobot 的设计
# 使用 \b 单词边界防止误匹配
# 使用 \s+ 处理多个空格/tab
DENY_PATTERNS: list[str] = [
    r"\brm\s+-[rf]{1,2}\b",           # rm -r, rm -rf, rm -fr (Linux)
    r"\b(del|erase)\s+/[fq]",          # del /f, del /q (Windows)
    r"\brd\s+/[s]",                    # rd /s (Windows 删除目录)
    r"\brmdir\s+/[s]",                 # rmdir /s (Windows)
    r"\b(dd|diskpart|mkfs|format)\b",  # 磁盘操作
    r">\s*/dev/sd[a-z]",               # 写入磁盘设备
    r"\b(shutdown|reboot|poweroff|halt)\b",  # 系统电源
    r"\bwget\s+",                      # wget 下载
    r"\bcurl\s+",                      # curl 请求（危险变体）
    r":\(\)\s*\{.*\};\s*:",            # fork bomb
]

TIMEOUT_SECONDS = 120
MAX_OUTPUT_CHARS = 50_000


def run_bash(
    command: str,
    workdir: Path,
    *,
    deny_patterns: Sequence[str] | None = None,
    allow_patterns: Sequence[str] | None = None,
) -> str:
    """
    执行 shell 命令并返回输出。

    Args:
        command: 要执行的 shell 命令。
        workdir: 工作目录。
        deny_patterns: 覆盖默认的 deny 正则列表。
        allow_patterns: allow 正则列表，非空时启用白名单模式。

    Returns:
        命令输出文本。
    """
    # 安全检查
    blocked = _check_deny(
        command,
        deny_patterns=list(deny_patterns or DENY_PATTERNS),
        allow_patterns=list(allow_patterns or []),
    )
    if blocked:
        return f"错误: 命令被安全策略拦截 — {blocked}"

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


def _check_deny(
    command: str,
    *,
    deny_patterns: list[str],
    allow_patterns: list[str],
) -> str | None:
    """
    检查命令是否违反安全策略。

    - 如果 allow_patterns 非空，只有匹配 allow 的命令才能通过（白名单模式）
    - 否则任何匹配 deny_patterns 的命令被拦截（黑名单模式）

    Returns:
        被拦截的原因，或 None 表示通过。
    """
    lower = command.lower()

    # 白名单模式：只有匹配 allow 的才放行
    if allow_patterns:
        for pattern in allow_patterns:
            if re.search(pattern, lower):
                return None
        return "命令未在白名单中"

    # 黑名单模式：匹配 deny 的拦截
    for pattern in deny_patterns:
        if re.search(pattern, lower):
            return f"匹配危险模式: {pattern}"

    return None
