"""
registry — 工具注册表。

集中管理：
1. 工具 Schema（发给 LLM 的 JSON 定义）
2. 工具名到函数的映射
3. 统一的执行入口
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# 所有工具的签名一致：(**kwargs, workdir=Path) -> str
ToolFunc = Callable[..., str]

# ── LLM 工具 Schema ──────────────────────────────────────────

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "bash",
        "description": "执行 shell 命令。危险命令会被拦截。",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "读取文件内容。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "写入文件。父目录不存在时自动创建。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "替换文件中的文本（仅替换第一次出现）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "glob",
        "description": "搜索匹配 glob 模式的文件。",
        "input_schema": {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        },
    },
    {
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
    },
]


@dataclass
class ToolRegistry:
    """
    工具注册表。

    每个工具是一个 (name, func) 对。register() 注册后自动可用。
    """

    handlers: dict[str, ToolFunc] = field(default_factory=dict)

    def register(self, name: str, func: ToolFunc) -> None:
        """注册一个工具。"""
        self.handlers[name] = func

    def get_schemas(self) -> list[dict]:
        """返回所有已注册工具的 LLM Schema。"""
        return [s for s in TOOL_SCHEMAS if s["name"] in self.handlers]

    def dispatch(self, name: str, workdir: Path, **kwargs: object) -> str:
        """
        执行工具调用。

        Args:
            name: 工具名。
            workdir: 工作目录。
            **kwargs: 工具参数。

        Returns:
            工具执行结果文本。
        """
        handler = self.handlers.get(name)
        if handler is None:
            return f"错误: 未知工具 '{name}'"
        return handler(**kwargs, workdir=workdir)

    @classmethod
    def create_default(cls) -> ToolRegistry:
        """
        创建包含所有内置工具的注册表。

        工厂方法模式 —— 隐藏注册细节。
        """
        from learn_cc.tools.bash import run_bash
        from learn_cc.tools.file_ops import run_read, run_write, run_edit
        from learn_cc.tools.planning import run_todo_write
        from learn_cc.tools.search import run_glob

        registry = cls()
        registry.register("bash", run_bash)
        registry.register("read_file", run_read)
        registry.register("write_file", run_write)
        registry.register("edit_file", run_edit)
        registry.register("glob", run_glob)
        registry.register("todo_write", run_todo_write)
        return registry
