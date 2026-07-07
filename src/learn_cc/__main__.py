"""
CLI 入口：learn-cc REPL

使用 AgentLoop 提供交互式命令行界面。
"""

from learn_cc.agent import AgentLoop
from learn_cc.config import Config, ConfigError
from learn_cc.tools.registry import ToolRegistry


def main():
    # 1. 加载配置
    try:
        config = Config.load()
    except ConfigError as e:
        print(f"\033[31m配置错误: {e}\033[0m")
        return

    # 2. 初始化工具和 Agent
    registry = ToolRegistry.create_default()
    loop = AgentLoop(config, registry)

    # 3. REPL 循环
    print("\033[32mlearn-cc Agent — 输入问题，回车发送。输入 q 退出。\033[0m\n")

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

        # 打印助理的最后回复文本
        for block in history[-1]["content"]:
            if getattr(block, "type", None) == "text":
                print(block.text)
        print()


if __name__ == "__main__":
    main()
