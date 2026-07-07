"""
CLI 入口：learn-cc

当前为 Step 2 —— 已经提取 Config 模块。
后续步骤会逐步将工具、Agent 循环、CLI 界面分离。
"""

from learn_cc.config import Config, ConfigError


def main():
    try:
        config = Config.load()
    except ConfigError as e:
        print(f"\033[31m配置错误: {e}\033[0m")
        return

    print(f"learn-cc v0.1.0 — 重构进行中 🚧")
    print(f"当前: Step 2 — Config 模块已提取")
    print(f"模型: {config.model}")
    print(f"工作目录: {config.workdir}")
    print()


if __name__ == "__main__":
    main()
