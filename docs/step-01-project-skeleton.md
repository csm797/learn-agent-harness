# Step 1: 项目骨架搭建

> 重构目标：`learn-claude-code-main` 的 s02_tool_use  
> 对应概念：项目配置、包结构、Python 构建系统

---

## 要解决的问题

原始教学项目有 20 个章节（s01~s20），每章都是一个**可独立运行的单文件**。比如 s02 就是 `s02_tool_use/code.py`，190 行，里面混了：

- 环境加载
- 5 个工具函数
- 工具 Schema 定义
- Agent 循环
- CLI 交互

这种组织方式**对教学是好的** —— 每个文件自包含，读者从头读到尾。但对工程来说是噩梦：

- 无法单独测试某个函数
- 无法复用模块（s03 要把 s02 全部复制一遍）
- 无法做类型检查（函数分散在全局作用域）
- 新人不知道在哪里加新文件

重构的目标就是把"单文件教学"变成"可维护的工程"。

## 参考 nanobot 的做法

nanobot 的项目根目录结构：

```
nanobot/
├── pyproject.toml        # 一切从这里开始
├── nanobot/              # 源码包（src/ 或不 src/ 都可以）
│   ├── __init__.py
│   ├── __main__.py
│   ├── agent/            # 按功能拆分子包
│   │   ├── tools/
│   │   │   ├── base.py
│   │   │   ├── filesystem.py
│   │   │   └── ...
│   │   ├── loop.py
│   │   └── runner.py
│   ├── config/
│   ├── channels/
│   └── ...
├── tests/                # 测试目录
├── docs/                 # 文档
└── pyproject.toml
```

关键模式：
1. **单入口配置**：`pyproject.toml` 包含所有元数据
2. **按职责分包**：`agent/tools/` 而不是 `tools.py`
3. **`__init__.py` 只做标识**：不在这写业务逻辑
4. **测试与源码对齐**：`tests/` 结构镜像 `nanobot/`

## 现代 Python 项目配置解读

```toml
[project]
name = "learn-cc"           # PyPI 包名（如果是库的话）
version = "0.1.0"           # 语义版本号
requires-python = ">=3.11"  # Python 版本下限

[project.scripts]
learn-cc = "learn_cc.__main__:main"   # 安装后获得 learn-cc 命令

[build-system]
requires = ["hatchling"]               # 构建引擎
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel.sources]
"src" = "."                            # src/ 布局映射
```

`[project.scripts]` 是 Python 的 **console_scripts** 入口点。`pip install` 后，系统会在 PATH 中生成一个 `learn-cc` 可执行文件，等价于运行 `python -m learn_cc`。

## src/ 布局 vs 扁平布局

```
# 扁平布局（不推荐）
my-package/
├── my_package/
├── tests/
└── pyproject.toml
# 问题：pytest 时 tests/ 直接导入源码，可能绕过安装

# src/ 布局（推荐）
my-package/
├── src/
│   └── my_package/
├── tests/
└── pyproject.toml
# 优点：强制 `pip install -e .` 后才能导入，环境与用户一致
```

## 本次具体操作

| 文件 | 作用 |
|------|------|
| `pyproject.toml` | 项目元数据、依赖、构建、lint、测试配置 |
| `src/learn_cc/__init__.py` | 包标识，导出版本号 |
| `src/learn_cc/__main__.py` | CLI 入口桩 |
| `tests/__init__.py` | 测试包标识 |
| `.gitignore` | 忽略规则 |
| `docs/step-01-project-skeleton.md` | 本文档 |

安装验证：

```bash
cd learn-cc
pip install -e .
python -c "import learn_cc; print(learn_cc.__version__)"
```

## 与原始教学项目的对应关系

原始项目是"从零写一个 Agent"，重构项目是"把写好的 Agent 整理好"。

重构不改变功能 —— 跑 `learn-cc` 的效果在最终完成时应该和 `python s02_tool_use/code.py` 完全一样。但内部结构不同。

---

## 下一步

Step 2 将提取 **Config 模块**。把原本散落在文件顶部的环境变量读取、API 客户端初始化，封装成 `learn_cc/config.py`，这是关注点分离的第一步。
