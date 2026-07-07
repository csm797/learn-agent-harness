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
