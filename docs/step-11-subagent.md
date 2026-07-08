# Step 11: Subagent（子 Agent）

> 参考 s06 + nanobot 的 SubagentManager

---

## 架构

```
父 Agent                             子 Agent
+---------------------+              +---------------------+
| messages=[...]      |              | messages=[task]     | ← 全新
|                     |  task tool   |                     |
| tool: task          | -----------> | AgentLoop (独立)    |
|   description="..." |              |   bash/read/write   |
|                     |  最终摘要    |   edit/glob         |
| result = "摘要"     | <----------- |   (30轮限制)        |
+---------------------+              +---------------------+
                                          ↑ 继承安全系统
                                       PermissionChecker
                                       HookRegistry
```

## 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 安全 | 继承父 agent 的安全系统 | 不能让子 agent 绕过权限检查 |
| 错误处理 | 返回错误消息，不重试 | 保持简单，父 agent 自己决定怎么做 |
| 工具 | 限制子集（无 task/todo/long_task） | 防止递归创建子 agent |
| 轮数限制 | 30 轮 | 原 s06 的设计，够用 |
| 历史 | 丢弃中间过程，只返回最终文本 | 上下文隔离，父 agent 不会被干扰 |

## 与 nanobot 的对比

nanobot 的 SubagentManager 复杂得多：
- 异步执行（asyncio.Task）
- 任务队列 + 并发限制
- 完整的 AgentRunner 实例
- 运行时状态追踪（SubagentStatus）

我们的实现保持同步（sync），因为整个 learn-cc 不是异步框架。核心概念一致。

---

## 实现

```python
class SubagentManager:
    """子 agent 管理器。"""
    
    def __init__(self, config, registry, permission, hooks):
        self.config = config
        self.registry = registry
        self.permission = permission
        self.hooks = hooks
    
    def spawn(self, description: str, max_turns: int = 30) -> str:
        """创建子 agent，返回最终文本。"""
        # 子 agent 使用限制后的工具
        sub_registry = ToolRegistry.create_subagent_default()
        
        sub_loop = AgentLoop(
            config=self.config,
            registry=sub_registry,
            permission=self.permission,
            hooks=self.hooks,
        )
        
        messages = [{"role": "user", "content": description}]
        sub_loop.run(messages)
        
        return extract_text(messages)
```

---

## 测试策略

| 测试 | 方法 |
|------|------|
| 子 agent 独立运行 | mock API，验证 sub_loop.run() 被调用 |
| 工具限制 | 验证 sub_registry 没有 task/todo_write |
| 轮数限制 | mock API 一直返回 tool_use，验证 30 轮后停止 |
| 安全继承 | 验证子 agent 走了权限检查 |
