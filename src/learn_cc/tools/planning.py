"""
planning — 规划工具 (todo_write)。

AI 用来创建和管理任务列表。不执行实际操作，只是做规划。
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from learn_cc.todo import TodoTracker

# 全局 tracker — 所有工具共享同一个任务列表
_current_tracker: TodoTracker | None = None


def _get_tracker() -> TodoTracker:
    global _current_tracker
    if _current_tracker is None:
        _current_tracker = TodoTracker()
    return _current_tracker


def set_tracker(tracker: TodoTracker) -> None:
    """设置全局 tracker（用于测试/集成）。"""
    global _current_tracker
    _current_tracker = tracker


def _normalize_todos(todos: list | str) -> tuple[list | None, str | None]:
    """
    校验并规范化任务列表。

    Returns:
        (todos, error) — 成功时 error=None，失败时 todos=None。
    """
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


# 工具 Schema
TODO_WRITE_SCHEMA = {
    "name": "todo_write",
    "description": "创建并管理当前编码会话的任务列表。"
                   "开始多步骤任务前先用此工具规划步骤，并随着进度更新状态。",
    "input_schema": {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "任务描述"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                            "description": "任务状态",
                        },
                    },
                    "required": ["content", "status"],
                },
            },
        },
        "required": ["todos"],
    },
}


def run_todo_write(todos: list, workdir: Path | None = None) -> str:
    """
    更新任务列表。

    Args:
        todos: 任务列表。
        workdir: 兼容接口（未使用）。

    Returns:
        操作结果描述。
    """
    todos, error = _normalize_todos(todos)
    if error:
        return error

    tracker = _get_tracker()
    tracker.update(todos)

    lines = [f"\n## 当前任务 ({len(todos)} 项)"]
    for t in todos:
        icon = {
            "pending": " ",
            "in_progress": "\033[36m▸\033[0m",
            "completed": "\033[32m✓\033[0m",
        }[t["status"]]
        lines.append(f"  [{icon}] {t['content']}")

    print("\n".join(lines))
    return f"已更新 {len(todos)} 项任务"
