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

    # 初始化
    registry = ToolRegistry.create_default()
    loop = AgentLoop(config, registry, verbose=not args.quiet)

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
