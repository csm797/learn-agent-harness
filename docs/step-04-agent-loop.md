# Step 4: Agent 循环模块提取

> 核心中的核心 —— Agent Loop

---

## 要解决的问题

原文件的核心逻辑在 `agent_loop()` 函数（L150-170），CLI 交互在 `if __name__` 块（L173-190），两者混在一起：

```
agent_loop()          ← 核心逻辑 + 控制台输出混在一起
if __name__ == ...    ← CLI 交互逻辑
```

问题：
1. **职责混合** —— 循环控制、API 调用、打印输出全在一个函数里
2. **不可测试** —— 每次调用都真的请求 Anthropic API
3. **不可复用** —— 要加个 Web UI 或别的入口，得把函数整个复制
4. **全局依赖** —— 直接引用 `client`、`MODEL`、`SYSTEM`、`TOOL_HANDLERS` 等模块级变量

## 设计：AgentLoop 类

```python
class AgentLoop:
    def __init__(self, config, registry, *, verbose=True):
        # 通过依赖注入拿到配置和工具
        self.client = Anthropic(...)        # 从 config 创建
        self.registry = registry             # 工具注册表
        self.verbose = verbose               # 是否打印日志

    def run(self, messages):
        while True:
            response = self._call_api(messages)
            messages.append(response)
            if response.stop_reason != "tool_use":
                return
            results = self._execute_tools(response)
            messages.append(results)
```

### 为什么用类而不是函数？

原代码是一个函数 `agent_loop(messages)`，但重构后需要传入 `config`、`registry` 等多个依赖。两种方式：

```python
# 选项 A：函数 + 参数
def agent_loop(messages, config, registry, verbose=True):
    ...  # 每次调用都要传全部参数

# 选项 B：类 + __init__
loop = AgentLoop(config, registry)
loop.run(messages)   # 干净
loop.run(messages2)  # 复用
```

类的方式好在：
1. **一次构造，多次运行** —— 配置只传一次
2. **可复用实例** —— 同一个 loop 可以跑多个对话
3. **可继承** —— 以后可以继承 `AgentLoop` 加功能

### 为什么保持 `print` 在里面？

原代码在工具执行时打印日志：

```
> read_file
/path/to/file.py
```

在测试中我们可以用 `capsys` fixture 捕获 stdout 来验证这些输出。

对于生产代码，你可能会想用 callback（回调）或 log 库。但对于学习项目，**简单胜于精巧**。先让它跑起来，再考虑抽象。

## 与 nanobot 的对比

nanobot 将循环拆分得更细：

```
AgentLoop           ← 协调者（管理 session、hooks、上下文）
AgentRunner         ← 执行者（LLM 对话循环 + 工具执行）
```

learn-cc 当前规模不需要拆两层。一个 `AgentLoop` 类已经足够，等变复杂了再拆不迟。

**过早抽象是万恶之源。**

## 测试策略

测试 agent_loop 的关键：**Mock Anthropic API**。

```python
# 核心技巧：用 MagicMock 替代真正的 API 调用
mock_msg = MagicMock()
mock_msg.stop_reason = "end_turn"   # ← 告诉循环"不用再继续了"
mock_msg.content = [MagicMock(type="text", text="你好")]
mock_client.messages.create.return_value = mock_msg

loop = AgentLoop(config, registry)
loop.client = mock_client  # 注入 mock
loop.run(messages)

assert messages[-1]["content"][0].text == "你好"
```

三种测试场景：

| 场景 | mock 设置 | 验证 |
|------|-----------|------|
| 普通回复 | stop_reason="end_turn" | 消息列表增加助理回答 |
| 工具调用 | stop_reason="tool_use" → "end_turn" | 工具被执行，结果追加 |
| 连续工具 | tool_use → tool_use → end_turn | 循环多次直到结束 |

## 本次变更

| 文件 | 操作 |
|------|------|
| `src/learn_cc/agent.py` | 新增，AgentLoop 类 |
| `src/learn_cc/__main__.py` | 重写，使用 AgentLoop |
| `tests/test_agent.py` | 新增，mock API 测试 |
| `docs/step-04-agent-loop.md` | 新增，本文档 |

---

## 下一步

Step 5 完善 CLI 入口 —— 添加参数解析、彩色输出、REPL 循环。让 `python -m learn_cc` 真正可用。
