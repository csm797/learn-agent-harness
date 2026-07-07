"""
agent — Agent 循环核心。

将 LLM 调用 + 工具执行循环封装为 AgentLoop 类。
通过依赖注入接收 Config 和 ToolRegistry，不依赖全局变量。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from anthropic import Anthropic
from anthropic.types import Message

from learn_cc.config import Config
from learn_cc.hooks import HookRegistry
from learn_cc.permission import PathPolicy
from learn_cc.todo import TodoTracker
from learn_cc.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from learn_cc.permission import PermissionChecker


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
        permission: PermissionChecker | None = None,
        hooks: HookRegistry | None = None,
        todo_tracker: TodoTracker | None = None,
    ):
        """
        初始化 Agent 循环。

        Args:
            config: 应用配置（API Key、模型、工作目录……）。
            registry: 工具注册表。
            verbose: 是否在 stdout 打印工具调用日志。
            permission: 可选的权限检查器。
            hooks: 可选的 HookRegistry。
            todo_tracker: 可选的 TodoTracker。传入后启用 nag 提醒。
        """
        self.config = config
        self.registry = registry
        self.verbose = verbose
        self.permission = permission
        self.hooks = hooks or HookRegistry()
        self.todo_tracker = todo_tracker

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
        3. 如果 stop_reason != "tool_use"，on_stop 后结束
        4. 否则执行工具，追加结果，继续循环

        Args:
            messages: 消息历史列表（会被原地修改）。
        """
        while True:
            # Nag 提醒：如果 AI 太久没更新任务列表，注入提醒
            if self.todo_tracker is not None and self.todo_tracker.should_nag():
                reminder = self.todo_tracker.build_reminder()
                if self.verbose:
                    print(f"\033[33m[todo] nag: 提醒 AI 更新任务\033[0m")
                messages.append({"role": "user", "content": reminder})

            # 每轮增加 nag 计数
            if self.todo_tracker is not None:
                self.todo_tracker.tick()

            self.hooks.before_llm(messages)
            response = self._call_api(messages)
            self.hooks.after_llm(response)
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                injected = self.hooks.on_stop(messages)
                if injected:
                    messages.append({"role": "user", "content": injected})
                    continue
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

            # 权限检查（如果启用了）
            if self.permission is not None:
                policy = PathPolicy(workdir=self.config.workdir)
                perm_result = self.permission.check(
                    block.name, block.input, policy,
                )
                if perm_result.decision.name == "DENY":
                    output = f"权限拒绝: {perm_result.reason}"
                    if self.verbose:
                        print(f"\033[31m⛔ {output}\033[0m")
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                    })
                    continue

                if perm_result.decision.name == "ASK":
                    allowed = self.permission.ask_user(
                        block.name, block.input, perm_result.reason or "",
                    )
                    if not allowed:
                        output = f"用户拒绝: {perm_result.reason}"
                        if self.verbose:
                            print(f"\033[33m🚫 {output}\033[0m")
                        results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": output,
                        })
                        continue

            # Hook: before_tool（可以阻断）
            blocked = self.hooks.before_tool(block.name, block.input)
            if blocked:
                if self.verbose:
                    print(f"\033[31m⛔ Hook 阻断: {blocked}\033[0m")
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(blocked),
                })
                continue

            # 执行工具
            output = self.registry.dispatch(
                block.name,
                self.config.workdir,
                **block.input,
            )

            # Nag: AI 更新了任务 → 重置计数器
            if self.todo_tracker is not None and block.name == "todo_write":
                self.todo_tracker.rounds_since_update = 0

            # Hook: after_tool
            self.hooks.after_tool(block.name, block.input, output)

            if self.verbose:
                print(str(output)[:200])

            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output,
            })

        return results
