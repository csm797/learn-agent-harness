"""
planning — 规划工具集。

参考 nanobot 的 Sustained Goals 设计：
  - long_task: 设定持续目标
  - complete_goal: 完成目标并写总结
  - todo_write: 任务列表微规划
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from learn_cc.todo import TodoTracker

_current_tracker: TodoTracker | None = None


def _get_tracker() -> TodoTracker:
    global _current_tracker
    if _current_tracker is None:
        _current_tracker = TodoTracker()
    return _current_tracker


def set_tracker(tracker: TodoTracker) -> None:
    global _current_tracker
    _current_tracker = tracker


# ── 数据校验 ──


def _normalize_todos(todos: list | str) -> tuple[list | None, str | None]:
    if isinstance(todos, str):
        try:
            todos = json.loads(todos)
        except json.JSONDecodeError:
            try:
                todos = ast.literal_eval(todos)
            except (SyntaxError, ValueError):
                return None, "错误: todos 必须是列表或 JSON 数组字符串"
    if not isinstance(todos, list):
        return None, "错误: todos 必须是列表"
    for i, t in enumerate(todos):
        if not isinstance(t, dict):
            return None, f"错误: todos[{i}] 必须是对象"
        if "content" not in t or "status" not in t:
            return None, f"错误: todos[{i}] 缺少 'content' 或 'status'"
        if t["status"] not in ("pending", "in_progress", "completed"):
            return None, f"错误: todos[{i}] 状态无效 '{t['status']}'"
    return todos, None


# ── 工具 Schema ──


LONG_TASK_SCHEMA = {
    "name": "long_task",
    "description": "为当前对话设定一个持续目标。调用后目标每轮自动注入上下文，"
                   "AI 始终能看到目标和进度。完成时调用 complete_goal。",
    "input_schema": {
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": "持续目标描述。应幂等（自包含、可重复执行）、有明确的完成条件。",
            },
        },
        "required": ["goal"],
    },
}

COMPLETE_GOAL_SCHEMA = {
    "name": "complete_goal",
    "description": "完成当前活跃的持续目标，并写一份简短总结。"
                   "用户取消或重定向目标时也要调用，recap 如实说明。",
    "input_schema": {
        "type": "object",
        "properties": {
            "recap": {
                "type": "string",
                "description": "完成总结：做了什么、结果如何。纯文本。",
            },
        },
        "required": [],
    },
}

TODO_WRITE_SCHEMA = {
    "name": "todo_write",
    "description": "创建或更新当前会话的任务列表。调用后重置 nag 计数器。",
    "input_schema": {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                        },
                    },
                    "required": ["content", "status"],
                },
            },
        },
        "required": ["todos"],
    },
}


# ── 工具函数 ──


def run_long_task(goal: str, workdir: Path | None = None) -> str:
    """
    设定持续目标（参考 nanobot long_task）。

    Args:
        goal: 目标描述。应幂等、自包含、有明确完成条件。
        workdir: 兼容接口。
    """
    if not goal or not goal.strip():
        return "错误: goal 不能为空"

    tracker = _get_tracker()
    tracker.set_goal(goal)

    # 打印展示
    print(f"\n\033[36m🎯 新目标:\033[0m {goal}")
    return f"目标已设定。使用普通工具推进目标，完成后调用 complete_goal。"


def run_complete_goal(recap: str = "", workdir: Path | None = None) -> str:
    """
    完成持续目标并写总结（参考 nanobot complete_goal）。

    Args:
        recap: 完成总结。
        workdir: 兼容接口。
    """
    tracker = _get_tracker()
    result = tracker.complete_goal(recap)

    # 打印展示
    icon = "\033[32m✅\033[0m"
    print(f"\n{icon} {result}")
    if recap:
        print(f"   总结: {recap}")

    return result


def run_todo_write(todos: list, workdir: Path | None = None) -> str:
    """
    更新任务列表。

    Args:
        todos: 任务列表。
        workdir: 兼容接口。
    """
    todos, error = _normalize_todos(todos)
    if error:
        return error

    tracker = _get_tracker()
    tracker.update_todos(todos)

    completed = sum(1 for t in todos if t["status"] == "completed")
    lines = [f"\n## 当前任务 ({completed}/{len(todos)} 完成)"]
    for t in todos:
        icon = {
            "pending": " ",
            "in_progress": "\033[36m▸\033[0m",
            "completed": "\033[32m✓\033[0m",
        }[t["status"]]
        lines.append(f"  [{icon}] {t['content']}")

    print("\n".join(lines))
    return f"已更新 {len(todos)} 项任务"
