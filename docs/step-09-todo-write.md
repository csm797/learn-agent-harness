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

## 深入理解：TodoTracker 的核心机制

### 关键控制变量

整个 todo 系统的行为由**一个变量**控制：

```python
class TodoTracker:
    def __init__(self, nag_after_rounds: int = 3):
        self.todos: list[dict] = []          # 当前任务列表
        self.rounds_since_update = 0          # ★ 核心控制变量
        self.nag_after_rounds = nag_after_rounds  # 阈值
```

`rounds_since_update` 是什么？  
是"AI **主动更新**任务列表后，已经过了多少轮 LLM 调用"的计数。

### 整个逻辑就是 3 个步骤的循环

```
                  初始: rounds_since_update = 0
                         │
                         ▼
              ┌─────────────────────┐
     ┌───────│   AI 调用 LLM 一轮   │
     │       └──────────┬──────────┘
     │                  │
     │           tick() → +1
     │                  │
     │        ┌─────────┴──────────┐
     │        │                    │
     │   AI 调了 todo_write?   没调？
     │        │                    │
     │   rounds = 0         rounds ≥ 3?
     │        │              ┌──┴──┐
     │        │             是    否
     │        │             │     │
     │        │   注入提醒 ──┘     │
     │        │   继续循环         │
     └────────┘                    │
                                 继续
```

### 具体例子

**场景：你让 AI "帮我重构这个项目"**

```
第 1 轮：
  rounds_since_update = 0
  AI 调用了 todo_write([{重构readme, pending}, {拆分utils, pending}])
  → round_since_update 重置为 0
  → todos = [重构readme, 拆分utils]

第 2 轮：
  tick() → rounds_since_update = 1
  AI 正在读文件 ……

第 3 轮：
  tick() → rounds_since_update = 2
  AI 还在读文件 ……

第 4 轮：
  tick() → rounds_since_update = 3
  nag_after_rounds 是 3，所以 should_nag() = True
  → 注入 "<reminder>请更新你的任务列表</reminder>"
  → rounds_since_update 不变（注意：nag 不会重置计数器）
```

**关键规则：**
- AI 调 `todo_write` → `rounds_since_update = 0`（重置）
- 每轮 LLM 调用开始 → `rounds_since_update += 1`（递增）
- 当值 ≥ `nag_after_rounds` → 注入提醒（但计数器继续增加）
- AI 不更新，提醒会每轮都注入，直到 AI 更新

### 为什么在 AgentLoop.run() 循环体里控制？

因为它需要**读两个东西的状态**：

```python
# agent.py run() 方法里
while True:
    # ① 读 TodoTracker 的状态 → 决定是否注入提醒
    if self.todo_tracker is not None and self.todo_tracker.should_nag():
        messages.append({"role": "user", "content": reminder})
    
    # ② 写 TodoTracker 的状态 → 这一轮过了
    if self.todo_tracker is not None:
        self.todo_tracker.tick()
    
    response = self._call_api(messages)
    results = self._execute_tool_calls(response.content)
    
    # ③ 在 _execute_tool_calls 里，如果 AI 调了 todo_write
    # → rounds_since_update = 0（重置）
```

如果放到 hook 里，hook 只有"读"没有"写"——hook 不能决定 AI 的调用是否重置计数器。

### 和原始 s05 的对比

| 方面 | s05（原始） | learn-cc（我们的） |
|------|-----------|-------------------|
| 存储方式 | 全局变量 `CURRENT_TODOS` + `rounds_since_todo` | `TodoTracker` 类 |
| 生命周期 | 模块级，整个进程共享 | 可创建多个实例，注入到 AgentLoop |
| 与其他模块共享 | 直接引用全局变量 | `set_tracker()` 显式设置 |
| 可测试性 | 难（全局变量跨测试污染） | 易（每次 new 一个） |
| 扩展性 | 加功能就要加全局变量 | 加功能就加方法 |

**全局变量的痛点：**
```python
# s05 的方式 — 两个全局变量散落
CURRENT_TODOS = []
rounds_since_todo = 0

def run_todo_write(todos):
    global CURRENT_TODOS    # 到处 global
    CURRENT_TODOS = todos

def agent_loop(messages):
    global rounds_since_todo  # 到处 global
    if rounds_since_todo >= 3:
        ...
```

问题：
1. 测试时上一个测试改了 `CURRENT_TODOS`，下一个测试拿到脏数据
2. 要加第二个 tracker（比如同时管理两个任务列表）不可能——都是全局的
3. 代码里到处是 `global` 关键字

**类的方式：**
```python
tracker = TodoTracker()        # 新实例，干净的
tracker.update(todos)          # 方法调用，没有 global
if tracker.should_nag():       # 读状态
    tracker.tick()             # 写状态

# 第二个 tracker，完全独立
tracker2 = TodoTracker(nag_after_rounds=5)
```

这就是"全局变量 → 封装成类"的典型重构——**把散落的数据 + 操作数据的逻辑，打包成一个有清晰接口的类。**

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
