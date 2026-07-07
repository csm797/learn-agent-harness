"""
todo — 任务跟踪器。

管理 AI 的任务列表（todos）和 nag 提醒机制。
当 AI 连续多轮不更新任务时自动提醒。
"""

from __future__ import annotations


class TodoTracker:
    """
    任务跟踪器。

    职责：
    1. 持有当前任务列表
    2. 跟踪"多少轮没更新了"
    3. 决定是否需要 nag
    """

    def __init__(self, nag_after_rounds: int = 3):
        self.todos: list[dict] = []
        self.rounds_since_update = 0
        self.nag_after_rounds = nag_after_rounds

    def update(self, todos: list[dict]) -> None:
        """更新任务列表并重置计数器。"""
        self.todos = todos
        self.rounds_since_update = 0

    def tick(self) -> None:
        """每轮调用一次，增加计数器。"""
        self.rounds_since_update += 1

    def should_nag(self) -> bool:
        """是否应该发送提醒。"""
        return self.rounds_since_update >= self.nag_after_rounds

    def build_reminder(self) -> str:
        """生成提醒消息。"""
        return (
            "<reminder>你已经有几轮没更新任务列表了。"
            "请用 todo_write 更新当前进度。</reminder>"
        )

    @property
    def has_todos(self) -> bool:
        return bool(self.todos)

    def format_todos(self) -> str:
        """格式化任务列表供显示。"""
        if not self.todos:
            return "(空)"
        lines = []
        for t in self.todos:
            icon = {"pending": " ", "in_progress": "▸", "completed": "✓"}.get(t["status"], "?")
            lines.append(f"  [{icon}] {t['content']}")
        return "\n".join(lines)
