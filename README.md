# learn-cc

从零学习 Claude Code 核心机制，**同时学会工程化编程**。

---

## 这是什么？

本项目是开源教学项目 [learn-claude-code](https://github.com/csm797/learn-claude-code) 的**模块化重构版本**。

原始项目通过 20 个章节（s01~s20）从单文件逐步构建一个简易 Agent Harness。
本重构项目将其拆分为标准 Python 包结构 —— **用同一个代码，展示工程的写法。**

```
原始项目：教你"写什么"           → Agent 核心概念
本重构版：教你"怎么组织"         → 工程化实践
```

## 快速开始

```bash
# 1. 安装
cd learn-cc
pip install -e .

# 2. 配置
cp .env.example .env
# 编辑 .env 填入你的 ANTHROPIC_API_KEY 和 MODEL_ID

# 3. 运行
python -m learn_cc

# 4. 测试
pytest tests/ -v
```

## 项目结构

```
learn-cc/
├── src/learn_cc/
│   ├── __init__.py          # 包标识 + 版本号
│   ├── __main__.py          # CLI 入口（REPL + 参数解析）
│   ├── config.py            # 配置管理（环境变量 → frozen dataclass）
│   ├── agent.py             # Agent 循环核心（依赖注入）
│   └── tools/
│       ├── base.py          # 路径安全校验
│       ├── bash.py          # Shell 命令执行
│       ├── file_ops.py      # 文件读写编辑
│       ├── search.py        # 文件搜索 (glob)
│       └── registry.py      # 工具注册表
├── tests/
│   ├── test_config.py       # 配置测试
│   ├── test_agent.py        # Agent 循环测试（mock API）
│   └── test_tools/          # 工具测试
├── docs/                    # 每步的编程思路文档
└── pyproject.toml           # 项目配置
```

## 重构路线图（5 步）

| 步骤 | 内容 | 核心概念 |
|------|------|----------|
| [Step 1](docs/step-01-project-skeleton.md) | 项目骨架 | `pyproject.toml`、`src/` 布局、构建系统 |
| [Step 2](docs/step-02-config-module.md) | Config 模块 | frozen dataclass、关注点分离 |
| [Step 3](docs/step-03-tools-package.md) | Tools 子包 | 分包策略、显式参数、安全边界 |
| [Step 4](docs/step-04-agent-loop.md) | Agent 循环 | 依赖注入、Mock 测试、类设计 |
| [Step 5](docs/step-05-cli-and-readme.md) | CLI + 收尾 | 入口设计、项目文档 |

每步都有对应的编程思路文档在 `docs/` 下。

## CLI 用法

```bash
python -m learn_cc              # 启动交互式 REPL
python -m learn_cc --model claude-sonnet-4-20250514  # 指定模型
python -m learn_cc --quiet      # 不打印工具调用日志
python -m learn_cc --version    # 显示版本号
```

## 测试

```bash
pytest tests/ -v            # 运行全部 49 个测试
pytest tests/ -v -k "bash"  # 只测 bash 相关
pytest tests/ --cov         # 带覆盖率
```

## 学习建议

1. **先读原始项目** —— `learn-claude-code/` 的 s01~s20，理解 Agent 是什么
2. **对照本项目的 docs/** —— 每一步的编程思路文档解释了为什么这样组织
3. **动手扩展** —— 自己加一个新工具（比如 `curl`），走一遍完整流程

## 与原始项目的关系

原始项目位于 `../learn-claude-code-main/`。两者代码功能等价，但组织方式不同：

| 方面 | 原始项目 | 本重构版 |
|------|---------|---------|
| 组织 | 20 个单文件 | 1 个包 + 模块 |
| 配置 | 模块级全局变量 | frozen dataclass |
| 工具 | 全局函数 + dict | 子包 + 注册表 |
| 测试 | 少量 smoke test | 49 个单元测试 |
| 构建 | requirements.txt | pyproject.toml |
