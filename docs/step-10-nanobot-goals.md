# Step 10: 学习 nanobot 升级规划系统

> 从 todo_write（手动规划 + nag）→ long_task（自动注入 + 持久化）

---

## 升级了什么

| 维度 | 之前（Step 9） | 现在（Step 10） |
|------|--------------|----------------|
| 目标数量 | 任务列表（多个） | **单目标 + 任务列表**，参考 nanobot |
| 可见性 | 3 轮不更新 → nag | **每轮自动注入 Runtime Context** |
| 持久化 | 内存，重启丢 | **JSON 文件持久化** |
| 完成仪式 | 直接改状态 | `complete_goal(recap=...)` 写总结 |
| 工具 | 1 个：`todo_write` | 3 个：`long_task` + `complete_goal` + `todo_write` |

详见 `docs/step-09-todo-write.md` 的 nanobot 对比章节。

---

## Runtime Context 注入

这是最关键的改进。

原来：AI 要自己记住目标，或者等 nag 提醒。

现在：每轮调用 API 前，在消息列表里注入一行：

```
[Runtime Context]
当前目标: 把项目重构完并推送到 GitHub（active）
进度: 2/5 项任务完成
```

```python
# agent.py
while True:
    # 注入 Runtime Context（如果活跃目标存在）
    if self.todo_tracker and self.todo_tracker.has_active_goal:
        context = self.todo_tracker.build_runtime_context()
        messages.append({"role": "user", "content": context})
    
    response = self._call_api(messages)
    ...
```

---

## 持久化

目标保存到 `learn-cc/goals.json`：

```json
{
  "objective": "把项目重构完并推送到 GitHub",
  "status": "active",
  "created_at": "2026-07-08T10:30:00",
  "completed_at": null,
  "recap": null,
  "todos": [
    {"content": "重构模块A", "status": "completed"},
    {"content": "重构模块B", "status": "in_progress"}
  ]
}
```

重启 `python -m learn_cc` 后目标还在。

---

## 本次变更

| 文件 | 操作 |
|------|------|
| `src/learn_cc/todo.py` | 重写：Goal 数据类 + 文件持久化 + Runtime Context |
| `src/learn_cc/tools/planning.py` | 修改：添加 long_task + complete_goal |
| `src/learn_cc/tools/registry.py` | 修改：注册新工具 |
| `src/learn_cc/agent.py` | 修改：Runtime Context 注入 |
| `src/learn_cc/__main__.py` | 修改：传 persistence_path |
| `tests/test_todo.py` | 更新：持久化 + complete_goal 测试 |
