"""
subagent — 子 Agent 管理器。

参考 s06 + nanobot SubagentManager 设计。
子 agent 继承父 agent 的安全系统，但工具限制为子集。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from learn_cc.agent import AgentLoop
from learn_cc.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from learn_cc.config import Config
    from learn_cc.hooks import HookRegistry
    from learn_cc.permission import PermissionChecker

MAX_SUBAGENT_TURNS = 30


def _extract_text(messages: list) -> str:
    """
    从消息列表中提取最终文本。

    回溯查找最后一条 assistant 的文本内容。
    """
    for msg in reversed(messages):
        if msg["role"] == "assistant":
            content = msg.get("content", "")
            if isinstance(content, list):
                texts = [
                    getattr(b, "text", "") for b in content
                    if getattr(b, "type", None) == "text"
                ]
                result = "\n".join(texts).strip()
                if result:
                    return result
            elif isinstance(content, str) and content.strip():
                return content.strip()
    return f"错误: 子 agent 超过 {MAX_SUBAGENT_TURNS} 轮限制，未返回最终结果。"


class SubagentManager:
    """
    子 agent 管理器。

    每次 spawn() 创建一个新的 AgentLoop 实例，独立运行。
    子 agent 继承父 agent 的安全系统和 hooks，但工具限制为子集。
    """

    def __init__(
        self,
        config: Config,
        *,
        permission: PermissionChecker | None = None,
        hooks: HookRegistry | None = None,
        verbose: bool = False,
    ):
        self.config = config
        self.permission = permission
        self.hooks = hooks
        self.verbose = verbose

    def spawn(self, description: str, workdir: object = None) -> str:
        """
        启动子 agent 执行任务。

        Args:
            description: 任务描述。
            workdir: 工作目录（兼容接口，与 registry.dispatch 签名一致）。

        Returns:
            子 agent 的最终回复文本。
        """
        if not description.strip():
            return "错误: task 描述不能为空"

        sub_registry = ToolRegistry.create_subagent_default()

        sub_loop = AgentLoop(
            config=self.config,
            registry=sub_registry,
            verbose=self.verbose,
            permission=self.permission,
            hooks=self.hooks,
            max_iterations=MAX_SUBAGENT_TURNS,
        )

        messages: list = [{"role": "user", "content": description}]
        sub_loop.run(messages)

        return _extract_text(messages)
