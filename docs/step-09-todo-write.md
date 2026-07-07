# Step 9: TodoWrite 规划工具

> 让 AI 先计划，再执行

---

## 要解决的问题

AI 经常一上来就动手，缺乏规划。结果：
1. 做到一半忘了目标
2. 步骤顺序错乱
3. 做了多余的工作

s05 引入一个**规划工具** `todo_write`，让 AI 先列出任务清单，再逐个执行。

## 设计

### todo_write 工具

```python
run_todo_write([
    {"content": "读取配置文件", "status": "completed"},
    {"content": "修改数据库连接", "status": "in_progress"},
    {"content": "重启服务", "status": "pending"},
])
```

AI 通过调用此工具来创建和更新任务列表。它不执行任何实际操作——只是**做规划**。

### TodoTracker

原 s05 用全局变量 `CURRENT_TODOS`。我们封装成类：

```python
class TodoTracker:
    """管理当前任务列表和 nag 提醒。"""
    
    todos: list[dict]
    rounds_since_update: int
    
    def update(self, todos): ...
    def should_nag(self) -> bool: ...     # 超过 N 轮没更新？
    def build_reminder(self) -> str: ...  # 生成提醒消息
    def reset_counter(self): ...          # AI 更新了 → 重置
```

### Nag 提醒

如果 AI 连续 3 轮（`rounds_since_todo >= 3`）没有调用 `todo_write`，自动注入提醒消息：

```python
<reminder>请更新你的任务列表。</reminder>
```

### System Prompt 更新

```python
SYSTEM = "... Before starting any multi-step task, use todo_write to plan your steps."
```

### 与 Hook 系统的关系

s05 的 nag 检查放在 `agent_loop` 里。我们放到 `AgentLoop.run()` 的 `before_llm` hook 里？不——nag 是核心行为，不是扩展点。直接放进 `run()` 方法。

---

## 本次变更

| 文件 | 操作 |
|------|------|
| `src/learn_cc/todo.py` | 新增：TodoTracker |
| `src/learn_cc/tools/planning.py` | 新增：run_todo_write |
| `src/learn_cc/tools/registry.py` | 修改：注册 todo_write |
| `src/learn_cc/agent.py` | 修改：集成 nag 提醒 |
| `src/learn_cc/config.py` | 修改：SYSTEM prompt 增加规划引导 |
| `tests/test_todo.py` | 新增：测试 |
| `tests/test_tools/test_planning.py` | 新增：测试 |
