"""
permission — 三关卡权限系统。

Gate 1: 硬拒绝列表 —— 匹配即拦截
Gate 2: 规则匹配 —— 上下文相关检查
Gate 3: 用户确认 —— 交互式审批

所有工具调用统一经过此模块，不侵入工具函数本身。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Callable


class Decision(Enum):
    """权限检查结果。"""
    ALLOW = auto()       # 允许执行
    DENY = auto()        # 拒绝执行
    ASK = auto()         # 需要用户确认


@dataclass
class PermissionResult:
    """权限检查结果。"""
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


# Gate 1: 硬拒绝列表 — 匹配即拦截，不过问
DEFAULT_DENY_LIST = [
    "rm -rf /",
    "sudo",
    "shutdown",
    "reboot",
    "mkfs",
    "dd if=",
    "> /dev/sda",
]

# Gate 2: 规则列表 — (工具名, 检查函数, 提示信息)
# 检查函数签名为 (args: dict, workdir: Path) -> bool，返回 True 表示命中
Rule = tuple[list[str], Callable[[dict, Path], bool], str]

DEFAULT_RULES: list[Rule] = [
    (
        ["write_file", "edit_file"],
        lambda args, workdir: not (workdir / args.get("path", "")).resolve().is_relative_to(workdir),
        "写入工作目录之外",
    ),
    (
        ["bash"],
        lambda args, workdir: any(
            kw in args.get("command", "")
            for kw in ["rm ", "> /etc/", "chmod 777", "chown ", "wget ", "curl "]
        ),
        "潜在破坏性命令",
    ),
    (
        ["read_file"],
        lambda args, workdir: not (workdir / args.get("path", "")).resolve().is_relative_to(workdir),
        "读取工作目录之外",
    ),
]


class PermissionChecker:
    """
    三关卡权限检查器。

    Args:
        deny_list: Gate 1 硬拒绝列表。None 用默认。
        rules: Gate 2 规则列表。None 用默认。
    """

    def __init__(
        self,
        deny_list: list[str] | None = None,
        rules: list[Rule] | None = None,
    ):
        self.deny_list = deny_list if deny_list is not None else DEFAULT_DENY_LIST
        self.rules = rules if rules is not None else DEFAULT_RULES

    def check(self, tool_name: str, args: dict, workdir: Path) -> PermissionResult:
        """
        检查工具调用是否允许。

        Args:
            tool_name: 工具名（如 "bash"）。
            args: 工具参数（如 {"command": "rm -rf /"}）。
            workdir: 工作目录。

        Returns:
            PermissionResult: ALLOW / DENY / ASK。
        """
        # Gate 1: 硬拒绝（仅 bash）
        if tool_name == "bash":
            command = args.get("command", "")
            for pattern in self.deny_list:
                if pattern in command:
                    return PermissionResult.deny(f"命中硬拒绝列表: {pattern}")

        # Gate 2: 规则匹配
        for tools, check_fn, message in self.rules:
            if tool_name in tools and check_fn(args, workdir):
                return PermissionResult.ask(f"{message} ({tool_name})")

        # 通过所有关卡
        return PermissionResult.allow()

    @staticmethod
    def ask_user(tool_name: str, args: dict, reason: str) -> bool:
        """
        交互式询问用户是否允许。
        返回 True=允许，False=拒绝。
        """
        args_summary = ", ".join(f"{k}={v!r}" for k, v in args.items())
        print(f"\n\033[33m⚠  {reason}\033[0m")
        print(f"   工具: {tool_name}({args_summary})")
        choice = input("   允许? [y/N] ").strip().lower()
        return choice in ("y", "yes")
