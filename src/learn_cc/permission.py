"""
permission — 安全策略引擎。

架构参考 nanobot 的 security/ 包，包含：
1. PathPolicy — 读写分离的路径安全策略
2. PermissionChecker — 三关卡权限检查（正则 deny + 规则 + 用户确认）

Gate 1: 硬拒绝列表 —— 正则匹配，可 allowlist 覆盖
Gate 2: 规则匹配 —— 路径逃逸、破坏性命令上下文检查
Gate 3: 用户确认 —— 交互式审批
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Sequence


# ── 路径策略 ──────────────────────────────────────────────


@dataclass(frozen=True)
class PathPolicy:
    """
    路径安全策略 —— 参考 nanobot 的读写分离设计。

    区分只读和可写路径，防止意外修改只读区域。

    Attributes:
        workdir: 主工作区（可读写）。
        extra_read_only: 额外可读目录（如媒体目录）。
        extra_writable: 额外可写目录（如输出目录）。
    """
    workdir: Path
    extra_read_only: Sequence[Path] = field(default_factory=list)
    extra_writable: Sequence[Path] = field(default_factory=list)

    def resolve_read(self, path: str) -> Path:
        """
        解析读取路径。允许 workdir + extra_read_only。

        Raises PathEscapeError
        """
        full = (self.workdir / path).resolve()
        if full.is_relative_to(self.workdir):
            return full
        for d in self.extra_read_only:
            if full.is_relative_to(d.resolve()):
                return full
        raise _PathEscapeError(f"读取路径逃逸安全边界: {path}")

    def resolve_write(self, path: str) -> Path:
        """
        解析写入路径。只允许 workdir + extra_writable。

        Raises PathEscapeError
        """
        full = (self.workdir / path).resolve()
        if full.is_relative_to(self.workdir):
            return full
        for d in self.extra_writable:
            if full.is_relative_to(d.resolve()):
                return full
        raise _PathEscapeError(f"写入路径逃逸安全边界: {path}")


class _PathEscapeError(PermissionError):
    """路径逃逸安全边界。"""


# ── 权限检查结果 ──────────────────────────────────────────


class Decision(Enum):
    ALLOW = auto()
    DENY = auto()
    ASK = auto()


@dataclass
class PermissionResult:
    decision: Decision
    reason: str | None = None

    @classmethod
    def allow(cls) -> PermissionResult:
        return cls(decision=Decision.ALLOW)

    @classmethod
    def deny(cls, reason: str) -> PermissionResult:
        return cls(decision=Decision.DENY, reason=reason)

    @classmethod
    def ask(cls, reason: str) -> PermissionResult:
        return cls(decision=Decision.ASK, reason=reason)


# ── 默认 deny 正则列表（参考 nanobot） ────────────────────

DEFAULT_DENY_PATTERNS: list[str] = [
    r"\brm\s+-[rf]{1,2}\b",           # rm -r, rm -rf, rm -fr
    r"\brmdir\s+/s\b",                 # rmdir /s
    r"\b(dd|diskpart|mkfs)\b",         # 磁盘操作
    r">\s*/dev/sd[a-z]",               # 写入磁盘设备
    r"\b(shutdown|reboot|poweroff|halt)\b",  # 系统电源
]

# ── 规则列表 ──────────────────────────────────────────────

# 每条规则: (匹配工具列表, 检查函数, 提示信息)
# 检查函数签名: (args: dict, policy: PathPolicy) -> bool
Rule = tuple[list[str], Callable[[dict, PathPolicy], bool], str]

DEFAULT_RULES: list[Rule] = [
    (
        ["write_file", "edit_file"],
        lambda args, policy: not (policy.workdir / args.get("path", "")).resolve().is_relative_to(policy.workdir),
        "写入工作目录之外",
    ),
    (
        ["bash"],
        lambda args, policy: any(
            kw in args.get("command", "").lower()
            for kw in ["rm ", "> /etc/", "chmod 777", "chown "]
        ),
        "潜在破坏性命令",
    ),
    (
        ["read_file"],
        lambda args, policy: not (policy.workdir / args.get("path", "")).resolve().is_relative_to(policy.workdir),
        "读取工作目录之外",
    ),
]


# ── 权限检查器 ────────────────────────────────────────────


class PermissionChecker:
    """
    权限检查器。

    支持：
    - 正则 deny patterns（可被 allowlist 覆盖）
    - 上下文规则匹配（Gate 2）
    - 交互式用户确认（Gate 3）
    - 读写分离路径策略（PathPolicy）
    """

    def __init__(
        self,
        deny_patterns: list[str] | None = None,
        allow_patterns: list[str] | None = None,
        rules: list[Rule] | None = None,
    ):
        self.deny_patterns = deny_patterns if deny_patterns is not None else DEFAULT_DENY_PATTERNS
        self.allow_patterns = allow_patterns or []
        self.rules = rules if rules is not None else DEFAULT_RULES

    def check(
        self,
        tool_name: str,
        args: dict,
        policy: PathPolicy,
    ) -> PermissionResult:
        """
        检查工具调用是否允许。

        Args:
            tool_name: 工具名。
            args: 工具参数。
            policy: 路径安全策略。

        Returns:
            ALLOW / DENY / ASK。
        """
        # Gate 1: 正则 deny（仅 bash）
        if tool_name == "bash":
            command = args.get("command", "")
            denied = self._check_deny(command)
            if denied:
                return PermissionResult.deny(denied)

        # Gate 2: 规则匹配
        for tools, check_fn, message in self.rules:
            if tool_name in tools and check_fn(args, policy):
                return PermissionResult.ask(f"{message} ({tool_name})")

        return PermissionResult.allow()

    def _check_deny(self, command: str) -> str | None:
        """
        检查命令是否匹配 deny patterns。
        allow_patterns 非空时启用白名单模式。
        """
        lower = command.lower()

        # 白名单模式
        if self.allow_patterns:
            for pattern in self.allow_patterns:
                if re.search(pattern, lower):
                    return None
            return "命令未在白名单中"

        # 黑名单模式
        for pattern in self.deny_patterns:
            if re.search(pattern, lower):
                return f"匹配危险模式: {pattern}"

        return None

    @staticmethod
    def ask_user(tool_name: str, args: dict, reason: str) -> bool:
        """交互式询问用户是否允许操作。返回 True=允许。"""
        args_summary = ", ".join(f"{k}={v!r}" for k, v in args.items())
        print(f"\n\033[33m⚠  {reason}\033[0m")
        print(f"   工具: {tool_name}({args_summary})")
        choice = input("   允许? [y/N] ").strip().lower()
        return choice in ("y", "yes")
