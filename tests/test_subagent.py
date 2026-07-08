"""测试 SubagentManager 和 task 工具。"""

from unittest.mock import MagicMock

import pytest

from learn_cc.subagent import SubagentManager, _extract_text
from learn_cc.tools.registry import ToolRegistry


class TestExtractText:
    def test_extract_from_list_content(self):
        """从 assistant 消息的 content list 中提取文本。"""
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "最终结果"
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": [text_block]},
        ]
        assert _extract_text(messages) == "最终结果"

    def test_extract_empty_content(self):
        """没有文本时返回超时提示。"""
        messages = [{"role": "user", "content": "hi"}]
        result = _extract_text(messages)
        assert "错误" in result
        assert "子 agent" in result

    def test_extract_prefers_last_assistant(self):
        """应该取最后一条 assistant 消息。"""
        text1 = MagicMock()
        text1.type = "text"
        text1.text = "中间结果"
        text2 = MagicMock()
        text2.type = "text"
        text2.text = "最终结果"
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": [text1]},
            {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]},
            {"role": "assistant", "content": [text2]},
        ]
        assert _extract_text(messages) == "最终结果"

    def test_extract_skips_tool_blocks(self):
        """跳过非 text 类型的 content block。"""
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "结果"
        messages = [
            {"role": "assistant", "content": [tool_block, text_block]},
        ]
        assert _extract_text(messages) == "结果"


class TestSubagentManager:
    def test_spawn_empty_description(self, monkeypatch):
        """空描述应该返回错误。"""
        from learn_cc.config import Config

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("MODEL_ID", "claude-test")
        config = Config.load(env_file=None)

        mgr = SubagentManager(config)
        result = mgr.spawn("")
        assert "错误" in result
        assert "不能为空" in result

    def test_spawn_runs_agent_loop(self, monkeypatch):
        """spawn 应该创建 AgentLoop 并运行。"""
        from learn_cc.config import Config

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("MODEL_ID", "claude-test")
        config = Config.load(env_file=None)

        mgr = SubagentManager(config)

        # Mock AgentLoop
        original_init = __import__("learn_cc.agent", fromlist=["AgentLoop"]).AgentLoop.__init__
        original_run = __import__("learn_cc.agent", fromlist=["AgentLoop"]).AgentLoop.run

        try:
            called = False

            def mock_init(self, config, registry, **kwargs):
                nonlocal called
                called = True
                # 检查子 agent 没有 task 工具
                assert "task" not in registry.handlers
                # 手动设置必要属性
                self.config = config
                self.registry = registry
                self.verbose = kwargs.get("verbose", False)
                self.permission = kwargs.get("permission")
                self.hooks = kwargs.get("hooks", __import__("learn_cc.hooks", fromlist=["HookRegistry"]).HookRegistry())
                self.todo_tracker = kwargs.get("todo_tracker")
                self.max_iterations = kwargs.get("max_iterations")
                self.client = MagicMock()

            def mock_run(self, messages):
                text_block = MagicMock()
                text_block.type = "text"
                text_block.text = "子任务完成"
                messages.append({"role": "assistant", "content": [text_block]})

            import learn_cc.agent as agent_mod
            agent_mod.AgentLoop.__init__ = mock_init
            agent_mod.AgentLoop.run = mock_run

            result = mgr.spawn("帮我查一下日志")
            assert "子任务完成" in result
            assert called
        finally:
            import learn_cc.agent as agent_mod
            agent_mod.AgentLoop.__init__ = original_init
            agent_mod.AgentLoop.run = original_run


class TestToolRegistrySubagent:
    def test_subagent_tools_limited(self):
        """子 agent 的工具应该有限制。"""
        reg = ToolRegistry.create_subagent_default()
        assert "bash" in reg.handlers
        assert "read_file" in reg.handlers
        assert "write_file" in reg.handlers
        assert "edit_file" in reg.handlers
        assert "glob" in reg.handlers
        # 不能有这些
        assert "task" not in reg.handlers
        assert "todo_write" not in reg.handlers
        assert "long_task" not in reg.handlers
        assert "complete_goal" not in reg.handlers

    def test_subagent_schemas_match(self):
        """子 agent 的 schemas 应该与工具匹配。"""
        reg = ToolRegistry.create_subagent_default()
        schemas = reg.get_schemas()
        schema_names = {s["name"] for s in schemas}
        assert schema_names == {"bash", "read_file", "write_file", "edit_file", "glob"}
