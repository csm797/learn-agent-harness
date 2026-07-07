# 测试指南

> 什么时候测、怎么测、测什么

---

## 快速命令

```bash
# 运行全部测试
pytest tests/

# 运行单个文件
pytest tests/test_config.py

# 运行单个测试
pytest tests/test_config.py::TestConfigLoad::test_load_basic

# 运行匹配名字的测试（-k 模糊匹配）
pytest tests/ -k "missing"

# 详细输出（显示每个测试名）
pytest tests/ -v

# 看到 print 输出
pytest tests/ -v -s

# 遇到第一个失败就停
pytest tests/ -x

# 覆盖率报告
pip install pytest-cov
pytest tests/ --cov=src/learn_cc
pytest tests/ --cov=src/learn_cc --cov-report=term-missing  # 显示哪些行没覆盖
```

> 所有命令在项目根目录（`learn-cc/`）下运行。

---

## 测试理念

### 「测试不是验证，是设计」

大多数人的第一反应：代码写完了，跑个测试验证一下对不对。

错了。

好的测试思维是反过来的：**先想怎么测，再想怎么写代码。**

- 如果一段代码没法测 → 它的设计有问题（耦合太重、职责不清）
- 测试难写 → 重构的信号
- 测试好写 → 设计大概率不错

### 测试金字塔

```
     ╱╲
    ╱  ╲          E2E 测试（少）
   ╱    ╲
  ╱──────────╲   集成测试（适中）
 ╱──────────────╲
╱──────────────────╲  单元测试（多，快，可靠）
```

- **单元测试**：测一个函数/类，不依赖外部（网络、数据库、文件系统）
- **集成测试**：测多个模块的协作，可能依赖真实环境
- **E2E 测试**：测整个系统，从用户输入到输出

**本项目主要写单元测试 + 少量集成测试。**

### FIRST 原则

好测试的 5 个特征：

| 字母 | 含义 | 说明 |
|------|------|------|
| F | Fast（快） | 毫秒级运行 |
| I | Isolated（隔离） | 不依赖其他测试 |
| R | Repeatable（可重复） | 跑 100 次结果一样 |
| S | Self-validating（自验证） | 自动判对错，不需要人看 |
| T | Timely（及时） | 在写代码之前写（TDD） |

---

## pytest 核心概念

### 断言用 `assert` 就行

不用 `self.assertEqual()`、`self.assertTrue()` 那套。Python 原生的 `assert` 就够了——pytest 会自动增强错误信息。

```python
# pytest 会告诉你两边的值
assert config.api_key == "sk-xxx"
# 输出: AssertionError: assert 'sk-yyy' == 'sk-xxx'
```

### Fixture：测试的「食材」

需要测试一个需要数据库连接的函数 → 你总不能在测试里真的连数据库吧？

Fixture 就是**替你把环境准备好、用完再清理**的机制。

```python
import pytest

@pytest.fixture
def temp_dir(tmp_path):
    """每个测试独享的临时目录，用完自动删除。"""
    d = tmp_path / "workspace"
    d.mkdir()
    return d

def test_write_file(temp_dir):
    """test_write_file 拿到的是干净的临时目录。"""
    result = run_write(str(temp_dir / "test.txt"), "hello", workdir=temp_dir)
    assert "hello" in (temp_dir / "test.txt").read_text()
```

pytest 内置的常用 fixture：

| fixture | 作用 |
|---------|------|
| `tmp_path` | 临时目录（每个测试独立） |
| `monkeypatch` | 修改/恢复环境变量和对象属性 |
| `capsys` | 捕获 stdout/stderr |
| `caplog` | 捕获日志输出 |

### Monkeypatch：让代码「以为」环境变了

这是单元测试最重要的工具 —— **不碰真实环境，但让代码以为环境变了**。

```python
def test_missing_api_key(monkeypatch):
    # 删除环境变量
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("MODEL_ID", "claude-3")

    with pytest.raises(ConfigError):  # 期望抛出异常
        Config.load(env_file=None)

# monkeypatch 在测试结束后自动恢复所有改动 —— 不影响其他测试
```

---

## 本项目测试结构

```
tests/
├── __init__.py              # 空文件，标识 tests 是包
├── test_config.py           # 测试 config 模块
├── test_tools/              # 测试 tools 包（Step 3 后创建）
│   ├── __init__.py
│   ├── test_bash.py
│   └── test_file_ops.py
└── conftest.py              # 共享 fixture（可选）
```

**规则：**
- 文件名 `test_*.py` 或 `*_test.py`
- 测试函数名 `def test_*():`
- 测试类名 `class Test*:`
- 一个测试文件测一个模块
- 一个测试函数测一个行为

---

## 什么时候不需要测试

- **Getter/setter** —— 太简单，不可能错
- **框架样板代码** —— `__init__.py`、`main()` 入口
- **配置本身** —— 测试 Config 加载逻辑，而不是测试 .env 文件里的值

## 什么时候必须写测试

- **边界条件** —— 空字符串、0、None、超大值
- **错误路径** —— 文件不存在、网络超时、权限不足
- **业务逻辑** —— if/else 的每个分支
- **修复的 bug** —— 先写一个复现 bug 的测试，再修代码（防回归）

---

## 常见误区

### ❌ 测试依赖顺序

```python
# test_a.py
def test_create():
    item = create_item()
    assert item.id == 1

# test_b.py
def test_delete():
    delete_item(1)   # 依赖 test_a 先执行
    assert ...
```

**问题**：测试执行顺序不确定，依赖其他测试的测试不是好测试。

**解决**：每个测试自包含，自己创建需要的数据。

### ❌ 测试依赖外部服务

```python
def test_call_anthropic():
    client = Anthropic(api_key="real-key")
    response = client.messages.create(...)  # 真的调用 API
    assert response.content
```

**问题**：没网就挂、跑得慢、API 要钱、API 改了测试就挂。

**解决**：mock（模拟）外部调用。

### ❌ 测试太多断言

```python
def test_config():
    config = Config.load()
    assert config.api_key == "sk-xxx"
    assert config.model == "claude-3"
    assert config.base_url is None
    assert config.workdir == Path.cwd()
    assert config.system_prompt == "..."
```

**问题**：第一个断言失败就停了，你不知道后面的对不对。而且这是在测「当前环境的值」，不是测「逻辑」。

**解决**：每个场景一个测试函数。

### ❌ 只测正常路径（Happy Path）

只测"一切正常"的情况，不测"缺环境变量"、"文件不存在"、"非法输入"。

**解决**：**先测错误路径**，再测正常路径。

---

## Step 2 的测试解剖

看看 `test_config.py` 里写得最好的那个测试：

```python
def test_load_missing_both(self, monkeypatch):
    """同时缺少多个变量时，应该列出所有缺失项。"""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # Arrange
    monkeypatch.delenv("MODEL_ID", raising=False)

    with pytest.raises(ConfigError) as exc:                 # Act + Assert
        Config.load(env_file=None)

    assert "ANTHROPIC_API_KEY" in str(exc.value)            # Assert
    assert "MODEL_ID" in str(exc.value)
```

Arrange-Act-Assert（AAA）模式：

| 阶段 | 代码 | 含义 |
|------|------|------|
| **Arrange** | `monkeypatch.delenv(...)` | 准备测试环境 |
| **Act** | `Config.load(env_file=None)` | 执行被测代码 |
| **Assert** | `assert ... in str(exc.value)` | 验证结果 |

---

## 下一步

Step 3 提取 Tools 包时，会用到 `tmp_path`（临时文件）和 `monkeypatch` 来测试文件操作工具。到时会有更多测试示例。
