"""
todo — 目标与任务跟踪。

参考 nanobot 的 long_task / complete_goal 设计：
- 单目标（Goal）：long_task 设定，complete_goal 完成
- 任务列表（todos）：todo_write 管理（微规划）
- Runtime Context：每轮自动注入
- 文件持久化：重启不丢
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

GoalStatus = Literal["active", "completed"]


@dataclass
class Goal:
    """一个持续目标（参考 nanobot Sustained Goal）。"""

    objective: str = ""
    status: GoalStatus = "active"
    created_at: str = ""
    completed_at: str | None = None
    recap: str | None = None


class TodoTracker:
    """
    目标与任务跟踪器。

    核心功能：
    1. 管理一个活跃目标（long_task / complete_goal）
    2. 管理任务列表（todo_write）
    3. 构建 Runtime Context 注入文本
    4. 文件持久化
    """

    def __init__(self, persistence_path: str | Path | None = None):
        self.goal = Goal()
        self.todos: list[dict] = []
        self._persistence_path = Path(persistence_path) if persistence_path else None
        self._load()

    # ── 目标管理（参考 nanobot long_task / complete_goal） ──

    @property
    def has_active_goal(self) -> bool:
        return bool(self.goal.objective) and self.goal.status == "active"

    def set_goal(self, objective: str) -> None:
        """设定一个新的持续目标。"""
        now = datetime.now().isoformat()
        self.goal = Goal(
            objective=objective.strip(),
            status="active",
            created_at=now,
        )
        self._save()

    def complete_goal(self, recap: str = "") -> str:
        """完成当前目标，记录总结。"""
        if not self.has_active_goal:
            return "错误: 没有活跃目标需要完成"
        now = datetime.now().isoformat()
        self.goal.status = "completed"
        self.goal.completed_at = now
        self.goal.recap = (recap or "").strip()
        self._save()
        return f"目标已完成。{recap}" if recap else "目标已完成。"

    # ── 任务列表管理 ──

    def update_todos(self, todos: list[dict]) -> None:
        """更新任务列表。"""
        self.todos = todos
        self._save()

    # ── Runtime Context（参考 nanobot goal_state_runtime_lines） ──

    def build_runtime_context(self) -> str:
        """
        构建 Runtime Context 文本。
        每轮注入到消息列表中，让 AI 始终看到目标和进度。
        """
        lines: list[str] = []

        if self.has_active_goal:
            lines.append(f"## 当前目标 (active)")
            lines.append(self.goal.objective)

        if self.todos:
            completed = sum(1 for t in self.todos if t["status"] == "completed")
            lines.append(f"\n进度: {completed}/{len(self.todos)} 项任务完成")
            for t in self.todos:
                icon = {"pending": " ", "in_progress": "▸", "completed": "✓"}.get(t["status"], "?")
                lines.append(f"  [{icon}] {t['content']}")

        return "\n".join(lines) if lines else ""

    # ── 持久化 ──

    def _persistence_path(self) -> Path | None:
        return self._persistence_path

    def _save(self) -> None:
        if not self._persistence_path:
            return
        try:
            data = {
                "goal": {
                    "objective": self.goal.objective,
                    "status": self.goal.status,
                    "created_at": self.goal.created_at,
                    "completed_at": self.goal.completed_at,
                    "recap": self.goal.recap,
                },
                "todos": self.todos,
            }
            self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
            self._persistence_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass  # 持久化失败不中断程序

    def _load(self) -> None:
        if not self._persistence_path or not self._persistence_path.exists():
            return
        try:
            data = json.loads(self._persistence_path.read_text(encoding="utf-8"))
            g = data.get("goal", {})
            self.goal = Goal(
                objective=g.get("objective", ""),
                status=g.get("status", "active"),
                created_at=g.get("created_at", ""),
                completed_at=g.get("completed_at"),
                recap=g.get("recap"),
            )
            self.todos = data.get("todos", [])
        except (json.JSONDecodeError, OSError):
            pass
