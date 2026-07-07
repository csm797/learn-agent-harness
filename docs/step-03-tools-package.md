# Step 3: Tools 包提取

> 从一个模块中的 5 个函数 ⟶ 一个子包中的 4 个模块

---

## 要解决的问题

原 `code.py` 中，工具函数和工具定义都混在文件顶层：

```
# 混在一起 —— 没有分离
run_bash()            # shell 命令执行
run_read() / write / edit    # 文件操作
run_glob()            # 文件搜索
TOOLS = [...]         # LLM 工具定义
TOOL_HANDLERS = {...} # 函数映射
safe_path()           # 路径安全校验（被文件工具共用）
```

问题：
1. **职责不分** —— 文件操作、命令执行、路径校验都在同一层
2. **全局依赖** —— 所有函数都依赖模块级变量 `WORKDIR`，无法独立测试
3. **修改困难** —— 加一个工具要在一堆函数中间插代码
4. **不可测试** —— `run_bash` 真的执行命令，没法做单元测试

## 分包策略

参考 nanobot 的 `agent/tools/` 结构，按工具类别分模块：

```
tools/
├── __init__.py      # 对外导出
├── base.py          # 共享工具（safe_path）
├── bash.py          # 命令执行类
├── file_ops.py      # 文件读写类
├── search.py        # 文件搜索类
└── registry.py      # 工具注册表
```

关键决策：**把 `safe_path` 放到 `base.py`**，因为它是所有文件类工具的共享依赖。bash 工具不需要它。

## 关键设计变更：从全局变量到参数传递

原来（依赖模块级全局）：

```python
WORKDIR = Path.cwd()

def run_read(path):
    file_path = safe_path(path)  # 内部引用 WORKDIR
    ...
```

重构后（显式传参）：

```python
def run_read(path, workdir):
    file_path = safe_path(path, workdir)  # 显式传入
    ...
```

**为什么这样做？**

1. **可测试** —— 测试时可以传入临时目录
2. **可追踪** —— 函数的输入输出很明确，不依赖「外部」状态
3. **可并行** —— 两个线程用不同的 workdir 不会冲突

代价是多写一个参数。但这是值得的 —— **显式优于隐式**。

## safe_path 的设计

```python
def safe_path(path: str, workdir: Path) -> Path:
    """将用户提供的路径转为绝对路径，并检查是否逃逸工作目录。"""
    full_path = (workdir / path).resolve()
    if not full_path.is_relative_to(workdir):
        raise ValueError(f"路径逃逸工作目录: {path}")
    return full_path
```

这是**安全边界** —— 防止 AI 读取 `~/.ssh/id_rsa` 或 `/etc/passwd`。

## 工具注册表的演变

原来一个 dict 搞定：

```python
TOOL_HANDLERS = {"bash": run_bash, "read_file": run_read, ...}
```

重构后，保持简单。引入一个 `ToolRegistry` 类来统一管理工具定义和分发：

```python
@dataclass
class ToolRegistry:
    handlers: dict[str, ToolFunc]

    def get_schemas(self) -> list[dict]: ...
    def dispatch(self, name: str, **kwargs) -> str: ...
```

这样 `TOOLS`（LLM 用的 schema）和 `TOOL_HANDLERS`（Python 函数映射）就不散了。

## 测试策略

| 工具 | 测试方法 | 关键点 |
|------|----------|--------|
| `safe_path` | 合法路径 / 逃逸路径 | 不碰文件系统 |
| `run_read` | `tmp_path` 创建临时文件 | 读存在/不存在/大文件 |
| `run_write` | `tmp_path` 然后验证文件存在 | 写新文件/覆盖/深路径 |
| `run_edit` | `tmp_path` 创建文件后编辑 | 找到/没找到/替换一次 |
| `run_glob` | `tmp_path` 创建文件结构 | 匹配模式 |
| `run_bash` | mock `subprocess.run` | 正常/超时/危险命令 |

`run_bash` 会 mock `subprocess.run`，因为：
1. 真的执行命令慢（pip install、编译…）
2. 可能破坏环境（rm -rf）
3. 不需要测 subprocess 本身，那是 Python 标准库的责任

## 本次变更

| 文件 | 操作 |
|------|------|
| `src/learn_cc/tools/__init__.py` | 新增，导出所有工具 |
| `src/learn_cc/tools/base.py` | 新增，safe_path |
| `src/learn_cc/tools/bash.py` | 新增，run_bash |
| `src/learn_cc/tools/file_ops.py` | 新增，run_read/write/edit |
| `src/learn_cc/tools/search.py` | 新增，run_glob |
| `src/learn_cc/tools/registry.py` | 新增，ToolRegistry |
| `tests/test_tools/` | 新增，测试目录 |
| `tests/test_config.py` | 不变 |

---

## 下一步

Step 4 提取 **Agent 循环** —— 把 `agent_loop` 从 `__main__.py` 中拆出，成为独立的 `agent.py` 模块，这是整个项目的核心。
