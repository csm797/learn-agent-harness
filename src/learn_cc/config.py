"""
配置管理模块。

集中管理所有环境变量读取、校验和默认值。
没有模块级副作用 —— Config.load() 需要显式调用。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    """配置错误 —— 环境变量缺失或格式不正确时抛出。"""


@dataclass(frozen=True)
class Config:
    """
    应用程序配置，从环境变量加载。

    使用 frozen=True 确保配置在运行时不可变 ——
    一旦创建就不能修改，防止运行时被意外篡改。
    """

    api_key: str
    """Anthropic API Key（或兼容接口的 Key）"""

    base_url: str | None
    """API 基础地址。None 表示使用 Anthropic 官方地址。"""

    model: str
    """模型 ID。"""

    workdir: Path
    """工作目录 —— 所有文件操作的安全边界。"""

    system_prompt: str
    """系统提示词。"""

    deny_patterns: tuple[str, ...] = ()
    """权限系统：自定义 deny 正则列表（逗号分隔）。空=用代码默认值。"""

    allow_patterns: tuple[str, ...] = ()
    """权限系统：自定义 allow 正则列表。非空时启用白名单模式。"""

    @classmethod
    def load(cls, env_file: str = ".env") -> Config:
        """
        从环境变量加载配置。

        参数:
            env_file: .env 文件路径。传 None 跳过文件加载（仅用环境变量）。

        返回:
            Config 实例。

        抛出:
            ConfigError: 缺少必要的环境变量。
        """
        if env_file:
            load_dotenv(dotenv_path=env_file, override=True)

        # 兼容 Anthropic 的非标准 Base URL 场景
        if os.getenv("ANTHROPIC_BASE_URL"):
            os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        model = os.environ.get("MODEL_ID")
        workdir = Path.cwd()

        # 校验 —— 给明确的错误信息，而不是 KeyError
        missing: list[str] = []
        if not api_key:
            missing.append("ANTHROPIC_API_KEY")
        if not model:
            missing.append("MODEL_ID")
        if missing:
            raise ConfigError(
                f"缺少必要的环境变量: {', '.join(missing)}\n"
                f"请确保 .env 文件或系统环境中已设置这些变量。"
            )

        system_prompt = (
            f"You are a coding agent at {workdir}. "
            f"Use tools to solve tasks. Act, don't explain. "
            f"Before starting any multi-step task, use todo_write to plan your steps. "
            f"Update todo status as you go."
        )

        # 权限配置（分号分隔的正则列表）
        # 例子: PERMISSION_DENY_PATTERNS="\brm\s+-[rf]{1,2}\b;\bshutdown\b"
        deny_raw = os.getenv("PERMISSION_DENY_PATTERNS")
        allow_raw = os.getenv("PERMISSION_ALLOW_PATTERNS")

        deny_patterns: tuple[str, ...] = ()
        allow_patterns: tuple[str, ...] = ()

        if deny_raw:
            deny_patterns = tuple(p.strip() for p in deny_raw.split(";") if p.strip())
        if allow_raw:
            allow_patterns = tuple(p.strip() for p in allow_raw.split(";") if p.strip())

        return cls(
            api_key=api_key,
            base_url=base_url or None,
            model=model,
            workdir=workdir,
            system_prompt=system_prompt,
            deny_patterns=deny_patterns,
            allow_patterns=allow_patterns,
        )
