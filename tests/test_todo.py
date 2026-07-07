"""测试 TodoTracker 和 todo_write 工具。"""

import pytest

from learn_cc.todo import TodoTracker
from learn_cc.tools.planning import run_todo_write, set_tracker


class TestTodoTracker:
    def test_empty_initially(self):
        """新 tracker 应该无任务、不 nag。"""
        t = TodoTracker()
        assert t.todos == []
        assert t.rounds_since_update == 0
        assert not t.should_nag()

    def test_update_resets_counter(self):
        """update 应该设置任务并重置计数器。"""
        t = TodoTracker()
        t.tick()
        t.tick()
        assert t.rounds_since_update == 2

        t.update([{"content": "任务1", "status": "pending"}])
        assert t.rounds_since_update == 0
        assert len(t.todos) == 1

    def test_nag_after_threshold(self):
        """超过阈值应该 nag。"""
        t = TodoTracker(nag_after_rounds=3)
        t.tick()
        t.tick()
        t.tick()
        assert t.should_nag()

    def test_no_nag_before_threshold(self):
        """未达阈值不应该 nag。"""
        t = TodoTracker(nag_after_rounds=3)
        t.tick()
        t.tick()
        assert not t.should_nag()

    def test_build_reminder(self):
        """提醒消息应该包含提示。"""
        t = TodoTracker()
        reminder = t.build_reminder()
        assert "reminder" in reminder.lower()
        assert "todo_write" in reminder

    def test_format_todos(self):
        """格式化输出应该包含任务内容。"""
        t = TodoTracker()
        t.update([
            {"content": "第一步", "status": "completed"},
            {"content": "第二步", "status": "in_progress"},
        ])
        output = t.format_todos()
        assert "第一步" in output
        assert "第二步" in output

    def test_format_todos_empty(self):
        """空任务列表应该显示提示。"""
        t = TodoTracker()
        assert t.format_todos() == "(空)"


class TestRunTodoWrite:
    def test_valid_todos(self):
        """有效的任务列表应该更新成功。"""
        t = TodoTracker()
        set_tracker(t)
        result = run_todo_write([
            {"content": "读文件", "status": "pending"},
        ])
        assert "已更新" in result
        assert len(t.todos) == 1

    def test_invalid_todos_not_list(self):
        """非列表应该报错。"""
        t = TodoTracker()
        set_tracker(t)
        result = run_todo_write("not a list")
        assert "错误" in result
        assert len(t.todos) == 0  # 未修改

    def test_invalid_todos_missing_fields(self):
        """缺少必填字段应该报错。"""
        t = TodoTracker()
        set_tracker(t)
        result = run_todo_write([{"content": "不完整"}])  # 缺 status
        assert "错误" in result

    def test_invalid_status(self):
        """无效状态应该报错。"""
        t = TodoTracker()
        set_tracker(t)
        result = run_todo_write([
            {"content": "任务", "status": "invalid_status"},
        ])
        assert "错误" in result

    def test_json_string_input(self):
        """JSON 字符串输入应该被解析。"""
        t = TodoTracker()
        set_tracker(t)
        result = run_todo_write('[{"content": "JSON任务", "status": "pending"}]')
        assert "已更新" in result
        assert t.todos[0]["content"] == "JSON任务"


class TestAgentLoopNagIntegration:
    def test_nag_injects_reminder(self, monkeypatch):
        """AgentLoop 应该在 tracker 触发 nag 时注入提醒。"""
        from unittest.mock import MagicMock

        from learn_cc.agent import AgentLoop
        from learn_cc.config import Config

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("MODEL_ID", "claude-test")
        config = Config.load(env_file=None)

        reg = MagicMock()
        reg.get_schemas.return_value = []
        reg.dispatch.return_value = "ok"

        t = TodoTracker(nag_after_rounds=2)
        t.tick()
        t.tick()  # 达到阈值

        loop = AgentLoop(config, reg, verbose=False, todo_tracker=t)
        loop.client = MagicMock()

        mock_msg = MagicMock()
        mock_msg.stop_reason = "end_turn"
        mock_msg.content = [MagicMock(type="text", text="ok")]
        loop.client.messages.create.return_value = mock_msg

        messages: list = [{"role": "user", "content": "hi"}]
        loop.run(messages)

        # 应该注入了提醒消息
        reminders = [m for m in messages if "reminder" in str(m.get("content", ""))]
        assert len(reminders) > 0

    def test_todo_write_resets_nag(self, monkeypatch):
        """调用 todo_write 后应该重置 nag 计数器。"""
        from unittest.mock import MagicMock

        from learn_cc.agent import AgentLoop
        from learn_cc.config import Config
        from learn_cc.tools.planning import set_tracker

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("MODEL_ID", "claude-test")
        config = Config.load(env_file=None)

        reg = MagicMock()
        reg.get_schemas.return_value = []
        reg.dispatch.return_value = "已更新 1 项任务"

        t = TodoTracker(nag_after_rounds=2)
        set_tracker(t)

        loop = AgentLoop(config, reg, verbose=False, todo_tracker=t)
        loop.client = MagicMock()

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "call_1"
        tool_block.name = "todo_write"
        tool_block.input = {"todos": [{"content": "任务", "status": "pending"}]}

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "好的"

        loop.client.messages.create.side_effect = [
            MagicMock(stop_reason="tool_use", content=[tool_block]),
            MagicMock(stop_reason="end_turn", content=[text_block]),
        ]

        loop.run([{"role": "user", "content": "规划任务"}])

        # tracker 被重置后又 tick() 了一次（第二轮开始），所以是 1
        assert t.rounds_since_update == 1

    def test_todo_schema_in_registry(self):
        """todo_write 的 schema 应该在注册表中。"""
        from learn_cc.tools.registry import ToolRegistry

        reg = ToolRegistry.create_default()
        schemas = reg.get_schemas()
        todo_schema = [s for s in schemas if s["name"] == "todo_write"]
        assert len(todo_schema) == 1
        assert "todos" in todo_schema[0]["input_schema"]["required"]
