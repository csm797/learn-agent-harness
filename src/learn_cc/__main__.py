"""
CLI 入口：learn-cc

用法：
    python -m learn_cc              # 启动 REPL
    python -m learn_cc --model xxx  # 指定模型
    python -m learn_cc --quiet      # 静默模式
    python -m learn_cc --version    # 版本号
"""

from __future__ import annotations

import argparse
import sys

from learn_cc import __version__
from learn_cc.agent import AgentLoop
from learn_cc.config import Config, ConfigError
from learn_cc.hooks import Hook, HookRegistry
from learn_cc.permission import PermissionChecker
from learn_cc.todo import TodoTracker
from learn_cc.subagent import SubagentManager
from learn_cc.tools.planning import set_tracker
from learn_cc.tools.registry import ToolRegistry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="learn-cc",
        description="从零学习 Claude Code 核心机制 — 模块化重构版",
    )
    parser.add_argument(
        "--model",
        help="模型 ID（覆盖环境变量 MODEL_ID）",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="不打印工具调用日志",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="显示版本号",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"learn-cc v{__version__}")
        return

    # 加载配置
    try:
        config = Config.load()
    except ConfigError as e:
        print(f"\033[31m配置错误: {e}\033[0m", file=sys.stderr)
        sys.exit(1)

    # 允许 CLI 覆盖模型
    if args.model:
        config = Config(
            api_key=config.api_key,
            base_url=config.base_url,
            model=args.model,
            workdir=config.workdir,
            system_prompt=config.system_prompt,
        )

    # 初始化 Hook 系统
    hooks = HookRegistry()

    if not args.quiet:
        class VerboseHook(Hook):
            """显示 hook 生命周期事件。"""
            def before_llm(self, messages):
                print(f"\033[90m[hook] before_llm: 发送 {len(messages)} 条消息\033[0m")
            def after_llm(self, response):
                reason = getattr(response, "stop_reason", "?")
                tools = sum(1 for b in (getattr(response, "content", []) or []) if getattr(b, "type", None) == "tool_use")
                print(f"\033[90m[hook] after_llm: stop={reason}, tools={tools}\033[0m")
            def before_tool(self, name, args):
                print(f"\033[90m[hook] before_tool: {name}\033[0m")
                return None
            def after_tool(self, name, args, output):
                print(f"\033[90m[hook] after_tool: {name} → {len(output)} chars\033[0m")
            def on_stop(self, messages):
                print(f"\033[90m[hook] on_stop: 共 {len(messages)} 条消息\033[0m")
                return None

        hooks.register(VerboseHook())

    # 初始化 TodoTracker（与 tools/planning.py 共享）
    from pathlib import Path
    persistence_path = Path(config.workdir) / "goals.json"
    todo_tracker = TodoTracker(persistence_path=persistence_path)
    set_tracker(todo_tracker)

    registry = ToolRegistry.create_default()
    permission = PermissionChecker.from_config(config)

    # 初始化子 agent 管理器并注册 task 工具
    subagent_mgr = SubagentManager(
        config, permission=permission, hooks=hooks,
        verbose=not args.quiet,
    )
    registry.register("task", subagent_mgr.spawn)

    loop = AgentLoop(
        config, registry,
        verbose=not args.quiet,
        permission=permission,
        hooks=hooks,
        todo_tracker=todo_tracker,
    )

    # REPL
    print(f"\033[32mlearn-cc v{__version__} — 输入问题，回车发送。输入 q 退出。\033[0m\n")

    history: list = []
    while True:
        try:
            query = input("\033[36m>> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break

        if query.strip().lower() in ("q", "exit", ""):
            break

        history.append({"role": "user", "content": query})
        loop.run(history)

        # 打印助理最后回复文本
        for block in history[-1]["content"]:
            if getattr(block, "type", None) == "text":
                print(block.text)
        print()


if __name__ == "__main__":
    main()
