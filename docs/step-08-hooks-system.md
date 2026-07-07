# Step 8: Hooks 系统

> 把"扩展逻辑"从循环中移出，放到 Hooks 上

---

## 要解决的问题

当前 Agent 循环里混了 3 种职责：

```python
def _execute_tool_calls(self, content):
    for block in content:
        # 职责 1: 权限检查 ← 横切关注点
        if self.permission:
            ...
        
        # 职责 2: 日志 ← 横切关注点
        if self.verbose:
            print(...)
        
        # 职责 3: 工具执行 ← 核心逻辑
        output = self.registry.dispatch(...)
```

每加一个新功能就要改循环体。Hooks 把"横切关注点"变成**插件**，循环只做核心逻辑。

## s04 的设计

原始 s04 的实现很简洁：

```python
HOOKS = {"PreToolUse": [], "PostToolUse": [], ...}

def register_hook(event, callback):
    HOOKS[event].append(callback)

def trigger_hooks(event, *args):
    for callback in HOOKS[event]:
        result = callback(*args)
        if result is not None:  # 非 None = 阻断
            return result
    return None
```

事件有 4 个：`UserPromptSubmit` / `PreToolUse` / `PostToolUse` / `Stop`

## nanobot 的设计

nanobot 的 hooks 复杂得多：

```
AgentHook (基类)
├── before_run() / after_run()
├── before_iteration() / after_iteration()
├── before_execute_tools()
├── on_error() / on_finally()
├── on_stream() / on_stream_end()
└── finalize_content()

CompositeHook (组合模式)
  └── 包装多个 Hook，错误隔离（一个挂了不影响其他）

AgentHookContext (迭代上下文)
  ├── iteration, messages, response
  ├── tool_calls, tool_results
  └── stop_reason, error, session_key
```

关键设计差异：

| 维度 | s04 | nanobot |
|------|-----|---------|
| 事件机制 | 字符串名 + 回调 | 类方法重写 |
| 注册方式 | `register_hook("event", fn)` | `CompositeHook([hook1, hook2])` |
| 阻断 | 返回值非 None | 修改 context.tool_results |
| 错误隔离 | ❌ 一个挂全挂 | ✅ `_for_each_hook_safe` |
| 上下文 | 参数散落 | `AgentHookContext` 统一传递 |
| 异步 | sync | async |

## 我们的设计：中间路线

吸取两个项目的优点：

```python
class Hook:
    """Hook 基类。重写需要的方法即可。"""
    
    def before_tool(self, tool_name, args) -> str | None:
        """返回非 None 字符串 = 阻断工具执行。"""
        return None
    
    def after_tool(self, tool_name, args, output) -> None:
        """工具执行后回调。"""
    
    def before_llm(self, messages) -> None:
        """调用 LLM 前回调。"""
    
    def on_stop(self, messages) -> str | None:
        """循环结束时回调。返回字符串 = 注入消息后继续。"""

class HookRegistry:
    """管理多个 Hook 的注册和分发。"""
    
    def register(self, hook): ...
    def before_tool(self, ...) -> str | None: ...
```

设计要点：
1. **类方法而不是事件字符串** —— IDE 补全友好，不容易拼错
2. **Composite 模式**（像 nanobot）—— 而不是全局 dict（像 s04）
3. **`before_tool` 返回值阻断**（像 s04）—— 而不是改 context（像 nanobot）
4. **错误隔离**（像 nanobot）—— 一个 hook 崩溃不影响其他

---

## 通俗解释：设计差异逐条拆解

> 上面那个对比表太干了，这里用大白话+例子讲清楚每一条。

### 1. 「事件机制」：字符串 vs 类方法

**s04 的方式 —— 事件字符串：**

```python
# 注册时说 "我要监听 PreToolUse 这个事件"
register_hook("PreToolUse", my_function)

# 触发时根据事件名找到回调
def trigger_hooks(event, *args):
    for cb in HOOKS[event]:
        cb(*args)
```

像**广播电台** —— 注册时说"我要听 FM 100.8"，触发时说"FM 100.8 发信号了"。
问题是：事件名是字符串，打错字了也不会报错 —— `"PreToolUes"` 静默不生效。

**nanobot 和我们的方式 —— 类方法：**

```python
class MyHook(Hook):
    def before_tool(self, name, args):  # ← 这是方法名，不是字符串
        ...

# 触发时直接调方法
for hook in hooks:
    hook.before_tool(name, args)  # ← IDE 能自动补全
```

像**对讲机** —— 你直接跟对方说"准备执行工具了"。
好处：方法名拼错了 IDE 立刻红线报错，不会静默失效。

### 2. 「注册方式」：全局 dict vs Composite 模式

**s04 —— 全局字典：**

```python
HOOKS = {"PreToolUse": [], "PostToolUse": []}   # 全局变量

def register_hook(event, callback):
    HOOKS[event].append(callback)  # 往全局变量里塞
```

问题：全局变量到处都能改，你不知道谁往里面加了什么。测试也不方便 —— 上一个测试注册的 hook 会影响下一个测试。

**nanobot —— Composite 模式：**

```python
# Composite 就是"打包成一串"的意思
hooks = CompositeHook([LogHook(), PermissionHook()])

# AgentLoop 只认这一个 hooks 变量
loop = AgentLoop(hooks=hooks)
```

像**排插** —— 你把所有插头（hook）插到一个排插上，然后只把这个排插递给 AgentLoop。
好处：没有全局变量，每个 loop 实例有自己的 hooks，互不干扰。

---

### 深入理解：Composite 到底怎么"灵活"？

你说得对，**代码本身是写死的** —— `HookRegistry` 的代码写死了调用 `before_tool()`，`PermissionHook` 的代码写死了检查命令。那"灵活"在哪？

**灵活在「组装」这一步是运行时决定的，而不是编译时决定的。**

看两个极端：

**极端 1：硬编码（最不灵活）**

```python
class AgentLoop:
    def _execute_tool_calls(self, content):
        for block in content:
            # 所有逻辑写死在循环体里
            if block.name == "bash" and "rm -rf" in block.input.get("command", ""):
                output = "权限拒绝"
            elif self.verbose:
                print(f"> {block.name}")
            else:
                output = self.registry.dispatch(...)
```

要加新功能？改这个函数。要删功能？改这个函数。测试？只能测整个函数。

**极端 2：插件系统（最灵活）**

```python
# main.py —— 用户自己决定装什么插件
from my_hooks import LogHook, AuditHook, MetricsHook

hooks = HookRegistry()
hooks.register(LogHook())        # 要日志？
hooks.register(AuditHook())      # 要审计？
hooks.register(MetricsHook())    # 要监控？
# 不用就注销
# hooks.unregister(MetricsHook())

loop = AgentLoop(config, registry, hooks=hooks)
```

不用改 `agent.py` 一行代码，就实现了不同的行为组合。

**关键区别：**

| | 硬编码 | Composite |
|---|---|---|
| 改行为要改哪里 | `agent.py` 的循环体 | `main.py` 的组装代码 |
| 加新功能 | 改 `agent.py`（风险大） | 写一个新 Hook 类，注册（风险小） |
| 测试 | 只能测整个循环 | 可以单独测每个 Hook |
| 复用 | ❌ 每个项目都得改 agent.py | ✅ 写一次 Hook，到处注册 |

**所以 Composite 的「灵活」不是说代码自己能变，而是说「组装权」从库的作者转移到了用户手里。** agent.py 的作者不需要预判用户想要什么功能，用户自己组装。

再举个现实例子：**VS Code 的插件系统。**
- VS Code 的代码是写死的（它不知道你要装什么插件）
- 但你可以装 Python 插件、Git 插件、Vim 插件
- 这些插件通过 VS Code 的扩展接口（类似 Hook 基类）与编辑器交互
- 你决定装什么、不装什么（类似 `register` / `unregister`）

这就是 Composite 模式 —— **框架提供接口和容器，用户决定里面装什么。**

### 3. 「阻断」：return str vs 改 context

这是 s04 和我们 vs nanobot 的最大区别。

**s04 和我们 —— 返回字符串=阻断：**

```python
class PermissionHook(Hook):
    def before_tool(self, name, args):
        if name == "bash" and "rm -rf" in args.get("command", ""):
            return "权限拒绝: 危险命令"  # ← 返回非 None = 阻断
        return None  # ← 返回 None = 放行
```

简单直接：hook 说「我不同意」，循环就听它的。

**nanobot —— 改 context：**

```python
async def before_execute_tools(self, context: AgentHookContext):
    for call in context.tool_calls:
        if call.name == "bash" and "rm -rf" in call.args.get("command", ""):
            context.tool_results.append("权限拒绝")  # ← 往上下文里塞结果
            context.tool_calls.remove(call)  # ← 从待执行列表移除
```

不直接说「我阻断」，而是**修改共享的数据对象**（context）：把某个 tool_call 从「待执行」改成「已拒绝」。

为什么 nanobot 要这么复杂？
因为 nanobot 要处理**异步并发** —— 多个 hook 可能同时修改 context，return 这种同步方式不够灵活。我们的场景简单，return 就够用了。

> 类比：s04 的方式像**保安拦住人** —— "你不能进"。nanobot 的方式像**在考勤表上改记录** —— 把人从「未签到」改成「已请假」。

### 4. 「错误隔离」：一个挂了，其他的还跑不跑？

想象你有两个 hook：

```python
hooks.register(ErrorHook())   # 这个会抛异常
hooks.register(LogHook())     # 这个要记录日志
```

**没有错误隔离（s04 的方式）：**

```python
def trigger_hooks(event, *args):
    for cb in HOOKS[event]:
        cb(*args)  # ErrorHook 抛异常 → 整个循环崩溃 → LogHook 没机会执行
```

ErrorHook 一炸，LogHook 也跟着遭殃。

**有错误隔离（nanobot 和我们的方式）：**

```python
def before_tool(self, name, args):
    for hook in self._hooks:
        try:
            result = hook.before_tool(name, args)
        except Exception:
            logger.exception("hook 出错了")  # 记个日志，继续跑下一个
            continue
```

ErrorHook 炸了 → 记日志 → 跳过它 → LogHook 正常运行。

### 5. 「上下文」：参数散落 vs 统一对象

**s04 —— 参数散落：**

```python
# 不同事件传不同参数，hook 函数签名不统一
trigger_hooks("PreToolUse", block)           # 传一个 block
trigger_hooks("PostToolUse", block, output)   # 传 block + output
trigger_hooks("UserPromptSubmit", query)      # 传字符串
```

你的 hook 函数得记住每个事件传几个参数、是什么类型。

**nanobot —— 统一 `AgentHookContext`：**

```python
# 所有事件都传同一个对象
async def before_iteration(self, context: AgentHookContext):
    print(context.messages)       # 消息列表
    print(context.iteration)      # 第几轮
    print(context.tool_calls)     # 待执行的工具

async def after_iteration(self, context: AgentHookContext):
    print(context.tool_results)   # 执行结果
    print(context.stop_reason)    # 为什么停止
```

好处：你不需要记每个方法传什么参数 —— context 里什么都有。想加新信息只需要往 context 加字段，不需要改所有 hook 的方法签名。

### 6. 「异步」：sync vs async

```python
# s04: 同步 —— 顺序执行
result = callback(*args)  # 这个跑完才跑下一个

# nanobot: 异步 —— 可以同时跑多个
await asyncio.gather(hook1.before_tool(...), hook2.before_tool(...))
```

对于 learn-cc（本地 REPL 工具），同步足够了。nanobot 要同时服务多个聊天渠道（Telegram、Discord、Web…），异步是刚需。

---

## 我们的设计选择

综合以上，我们的取舍：

| 设计点 | 选择 | 为什么 |
|--------|------|--------|
| 事件标识 | 类方法（像 nanobot） | IDE 补全，防手误 |
| 注册 | Composite（像 nanobot） | 无全局变量，可测试 |
| 阻断 | return str（像 s04） | 简单够用 |
| 错误隔离 | try/except（像 nanobot） | 防止一个 hook 坏了整个系统 |
| 上下文 | 方法参数（像 s04） | 我们方法少，不需要统一 context |
| 异步 | sync（像 s04） | 本地工具不需要 async |

---

## 测试策略

| 测试 | 方法 |
|------|------|
| 注册 + 分发 | 注册一个 hook，验证被调用 |
| before_tool 阻断 | hook 返回字符串，验证工具被阻止 |
| 多个 hook | 注册 2 个，验证都执行 |
| 错误隔离 | 一个 hook 抛异常，验证另一个仍执行 |
| 集成 | 将 log_hook 注册到 AgentLoop，验证输出 |

---

## 本次变更

| 文件 | 操作 |
|------|------|
| `src/learn_cc/hooks.py` | 新增：Hook 基类 + HookRegistry |
| `src/learn_cc/agent.py` | 修改：集成 HookRegistry |
| `tests/test_hooks.py` | 新增：测试 |
