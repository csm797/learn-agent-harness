"""
hooks — Hook 系统。

把横切关注点（日志、权限、审计……）从 Agent 循环中解耦。
参考 nanobot 的 AgentHook + CompositeHook 设计，保持简单。

Hook 基类 + HookRegistry（组合模式）。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class Hook:
    """
    Hook 基类。

    重写需要的方法即可，不需要的保持原样（默认 no-op）。
    所有方法都是同步的 —— 保持简单。

    生命周期（按调用顺序）：

    before_llm(messages)         LLM 调用前
        ↓
    LLM API call
        ↓
    after_llm(response)          LLM 返回后
        ↓
    for each tool_use:
        before_tool(name, args)  工具执行前 → 返回 str 阻断
        tool execution
        after_tool(name, args, output)  工具执行后
        ↓
    on_stop(messages)            循环结束时
    """

    def before_llm(self, messages: list[dict]) -> None:
        """调用 LLM 之前触发。可在此修改 messages。"""

    def after_llm(self, response: Any) -> None:
        """LLM 返回响应后触发。"""

    def before_tool(self, tool_name: str, args: dict) -> str | None:
        """
        工具执行前触发。

        Returns:
            None = 允许执行。
            str = 拒绝执行，返回该字符串作为错误消息。
        """
        return None

    def after_tool(self, tool_name: str, args: dict, output: str) -> None:
        """工具执行后触发。"""

    def on_stop(self, messages: list[dict]) -> str | None:
        """
        循环结束时触发（stop_reason != "tool_use"）。

        Returns:
            None = 正常结束。
            str = 注入该消息作为 user 消息，继续循环。
        """
        return None


class HookRegistry:
    """
    Hook 注册表 —— 管理多个 Hook 的顺序和执行。

    组合模式（Composite Pattern）：它本身看起来像一个 Hook，
    内部持有多个 Hook，逐个调用。

    错误隔离：某个 Hook 抛异常不影响其他 Hook。
    """

    def __init__(self) -> None:
        self._hooks: list[Hook] = []

    def register(self, hook: Hook) -> None:
        """注册一个 Hook。按注册顺序调用。"""
        self._hooks.append(hook)

    def unregister(self, hook: Hook) -> None:
        """注销一个 Hook。"""
        self._hooks.remove(hook)

    # ── 生命周期分发 ─────────────────────────────────

    def before_llm(self, messages: list[dict]) -> None:
        for hook in self._hooks:
            try:
                hook.before_llm(messages)
            except Exception:
                logger.exception("Hook.before_llm 出错: %s", type(hook).__name__)

    def after_llm(self, response: Any) -> None:
        for hook in self._hooks:
            try:
                hook.after_llm(response)
            except Exception:
                logger.exception("Hook.after_llm 出错: %s", type(hook).__name__)

    def before_tool(self, tool_name: str, args: dict) -> str | None:
        """
        按顺序调用所有 hook 的 before_tool。

        Returns:
            第一个非 None 返回值（阻断消息），或 None（全部允许）。
        """
        for hook in self._hooks:
            try:
                result = hook.before_tool(tool_name, args)
                if result is not None:
                    return result
            except Exception:
                logger.exception("Hook.before_tool 出错: %s", type(hook).__name__)
        return None

    def after_tool(self, tool_name: str, args: dict, output: str) -> None:
        for hook in self._hooks:
            try:
                hook.after_tool(tool_name, args, output)
            except Exception:
                logger.exception("Hook.after_tool 出错: %s", type(hook).__name__)

    def on_stop(self, messages: list[dict]) -> str | None:
        for hook in self._hooks:
            try:
                result = hook.on_stop(messages)
                if result is not None:
                    return result
            except Exception:
                logger.exception("Hook.on_stop 出错: %s", type(hook).__name__)
        return None

    @property
    def count(self) -> int:
        return len(self._hooks)
