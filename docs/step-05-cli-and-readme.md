# Step 5: CLI 完善 + 项目收尾

> 最后一步：让重构后的项目真正可用、文档完整

---

## 回顾重构之路

| 步骤 | 做了什么 | 学会什么 |
|------|---------|---------|
| Step 1 | 项目骨架 | `pyproject.toml`、`src/` 布局、构建系统 |
| Step 2 | Config 模块 | frozen dataclass、环境变量管理、关注点分离 |
| Step 3 | Tools 子包 | 分包策略、参数显式化、安全边界 |
| Step 4 | Agent 循环 | 依赖注入、Mock 测试、类 vs 函数设计 |
| Step 5 | CLI + README | 入口设计、项目文档、完整交付 |

## CLI 参数设计

```bash
python -m learn-cc                    # 默认启动 REPL
python -m learn-cc --model claude-4   # 指定模型
python -m learn-cc --quiet            # 不打印工具调用日志
python -m learn-cc --version          # 显示版本号
```

用 `argparse` 而不是 `click`/`typer`，因为：
1. 零依赖 —— Python 自带
2. 够用 —— 只有 3-4 个参数
3. 学习价值 —— 了解标准库的 CLI 方案

## README 应该包含什么

好的 README 回答 4 个问题：

1. **这是什么？** —— 项目定位
2. **怎么用？** —— 快速上手指南
3. **怎么学的？** —— 重构思路（链接到 docs/）
4. **结构是怎样的？** —— 项目文件导航

## 测试现状

49 个测试覆盖了：

| 模块 | 测试数 | 覆盖范围 |
|------|--------|----------|
| config | 9 | 正常/缺失/文件加载/不可变 |
| agent | 8 | 文本/工具/多工具/verbose/各种 stop_reason |
| tools/base | 5 | 合法/逃逸/边界 |
| tools/bash | 5 | 正常/危险命令/超时/不存在 |
| tools/file_ops | 12 | read/write/edit + 错误路径 |
| tools/search | 4 | 匹配/递归/无匹配 |
| tools/registry | 6 | 注册/分发/未知工具/参数缺失 |

运行方式：

```bash
pytest tests/ -v          # 全部
pytest tests/ --cov       # 带覆盖率
```

---

## 与原始教学项目的关系

原始项目（learn-claude-code）的定位：**从零教你写一个 Agent**。
重构项目（learn-cc）的定位：**从单文件教你做一个工程**。

两者是互补的：
- 原始项目教你"**写什么**" —— Agent 的核心概念
- 重构项目教你"**怎么组织**" —— 工程化实践

建议学习路径：
1. 先通读原始项目的 s01~s20
2. 对照本重构项目看"如果我来组织这段代码会放哪里"
3. 动手加一个新工具（比如 `curl`），走一遍完整流程

---

## 本次变更

| 文件 | 操作 |
|------|------|
| `src/learn_cc/__main__.py` | 重写，添加 argparse 参数解析 |
| `README.md` | 重写，完整项目文档 |
| `.env.example` | 新增（不带真实 Key 的模板） |
| `docs/step-05-cli-and-readme.md` | 新增 |
