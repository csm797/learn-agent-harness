"""
agent — Agent 循环核心。

将 LLM 调用 + 工具执行循环封装为 AgentLoop 类。
通过依赖注入接收 Config 和 ToolRegistry，不依赖全局变量。
"""

from __future__ import annotations

from anthropic import Anthropic
from anthropic.types import Message

from learn_cc.config import Config
from learn_cc.tools.registry import ToolRegistry


class AgentLoop:
    """
    Agent 主循环。

    职责：
    1. 调用 LLM API（消息 + 工具 Schema）
    2. 解析 stop_reason，判断是否继续
    3. 分发 tool_use 到 ToolRegistry
    4. 将结果放回消息列表

    用法：
        loop = AgentLoop(config, registry)
        loop.run(messages)
    """

    def __init__(
        self,
        config: Config,
        registry: ToolRegistry,
        *,
        verbose: bool = True,
    ):
        """
        初始化 Agent 循环。

        Args:
            config: 应用配置（API Key、模型、工作目录……）。
            registry: 工具注册表。
            verbose: 是否在 stdout 打印工具调用日志。
        """
        self.config = config
        self.registry = registry
        self.verbose = verbose

        # 从配置创建 API 客户端
        self.client = Anthropic(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    def run(self, messages: list) -> None:
        """
        运行 Agent 循环。

        每轮：
        1. 调用 API
        2. 追加助理回复到消息列表
        3. 如果 stop_reason != "tool_use"，结束
        4. 否则执行工具，追加结果，继续循环

        Args:
            messages: 消息历史列表（会被原地修改）。
        """
        while True:
            response = self._call_api(messages)
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                return

            results = self._execute_tool_calls(response.content)
            messages.append({"role": "user", "content": results})

    def _call_api(self, messages: list) -> Message:
        """调用 LLM API。"""
        return self.client.messages.create(
            model=self.config.model,
            system=self.config.system_prompt,
            messages=messages,
            tools=self.registry.get_schemas(),
            max_tokens=8000,
        )

    def _execute_tool_calls(self, content: list) -> list[dict]:
        """
        执行模型请求的工具调用。

        Args:
            content: API 返回的 content blocks。

        Returns:
            tool_result 列表，可直接追加为 user 消息。
        """
        results: list[dict] = []
        for block in content:
            if block.type != "tool_use":
                continue

            if self.verbose:
                args_summary = str(block.input)[:100]
                print(f"\033[33m> {block.name}({args_summary})\033[0m")

            output = self.registry.dispatch(
                block.name,
                self.config.workdir,
                **block.input,
            )

            if self.verbose:
                print(str(output)[:200])

            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output,
            })

        return results
