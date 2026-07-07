"""测试 AgentLoop 核心逻辑。"""

from unittest.mock import MagicMock

import pytest

from learn_cc.agent import AgentLoop
from learn_cc.config import Config
from learn_cc.tools.registry import ToolRegistry


# ── 测试辅助函数 ────────────────────────────────────────


def make_config(monkeypatch):
    """创建一个测试用的最小配置。"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("MODEL_ID", "claude-test")
    return Config.load(env_file=None)


def make_mock_content_block(block_type, **kwargs):
    """创建一个 mock 的 content block（text 或 tool_use）。"""
    block = MagicMock()
    block.type = block_type
    for k, v in kwargs.items():
        setattr(block, k, v)
    return block


def make_mock_response(stop_reason="end_turn", content=None):
    """创建一个 mock 的 Message 对象。"""
    msg = MagicMock()
    msg.stop_reason = stop_reason
    msg.content = content or []
    return msg


# ── 测试类 ──────────────────────────────────────────────


class TestAgentLoop:
    def test_responds_with_text(self, monkeypatch):
        """普通文本回复：stop_reason=end_turn 应该直接返回。"""
        config = make_config(monkeypatch)
        registry = ToolRegistry()
        loop = AgentLoop(config, registry, verbose=False)

        # Mock API 返回文本
        mock_msg = make_mock_response(
            stop_reason="end_turn",
            content=[make_mock_content_block("text", text="你好！我是助手。")],
        )
        loop.client = MagicMock()
        loop.client.messages.create.return_value = mock_msg

        messages: list = [{"role": "user", "content": "你好"}]
        loop.run(messages)

        # 应该追加了助理消息
        assert len(messages) == 2
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"][0].text == "你好！我是助手。"

    def test_single_tool_use_then_text(self, monkeypatch):
        """一次工具调用后出文本：tool_use → tool_result → end_turn。"""
        config = make_config(monkeypatch)
        registry = ToolRegistry.create_default()
        loop = AgentLoop(config, registry, verbose=False)
        loop.client = MagicMock()

        # 第一轮：tool_use
        tool_block = make_mock_content_block(
            "tool_use",
            id="call_1",
            name="bash",
            input={"command": "echo hello"},
        )
        # 第二轮：end_turn
        text_block = make_mock_content_block("text", text="执行完毕")

        loop.client.messages.create.side_effect = [
            make_mock_response(stop_reason="tool_use", content=[tool_block]),
            make_mock_response(stop_reason="end_turn", content=[text_block]),
        ]

        messages: list = [{"role": "user", "content": "执行 echo hello"}]
        loop.run(messages)

        # 应该：user → assistant(tool_use) → user(tool_result) → assistant(text)
        assert len(messages) == 4
        assert messages[3]["content"][0].text == "执行完毕"
        # tool_result 的内容应该包含命令输出
        assert "hello" in messages[2]["content"][0]["content"]

    def test_multiple_tools_in_one_turn(self, monkeypatch):
        """一轮中多个工具调用：全部执行后合并结果。"""
        config = make_config(monkeypatch)
        registry = ToolRegistry.create_default()
        loop = AgentLoop(config, registry, verbose=False)
        loop.client = MagicMock()

        tool_1 = make_mock_content_block(
            "tool_use", id="call_1", name="bash",
            input={"command": "echo first"},
        )
        tool_2 = make_mock_content_block(
            "tool_use", id="call_2", name="bash",
            input={"command": "echo second"},
        )
        text = make_mock_content_block("text", text="两个都执行了")

        loop.client.messages.create.side_effect = [
            make_mock_response(stop_reason="tool_use", content=[tool_1, tool_2]),
            make_mock_response(stop_reason="end_turn", content=[text]),
        ]

        messages: list = [{"role": "user", "content": "执行两个命令"}]
        loop.run(messages)

        # 应该有两个 tool_result
        results = messages[2]["content"]
        assert len(results) == 2
        assert results[0]["tool_use_id"] == "call_1"
        assert results[1]["tool_use_id"] == "call_2"

    def test_verbose_output(self, monkeypatch, capsys):
        """verbose=True 应该打印工具调用日志。"""
        config = make_config(monkeypatch)
        registry = ToolRegistry.create_default()
        loop = AgentLoop(config, registry, verbose=True)
        loop.client = MagicMock()

        tool_block = make_mock_content_block(
            "tool_use", id="call_1", name="bash",
            input={"command": "echo hi"},
        )
        text_block = make_mock_content_block("text", text="完成")

        loop.client.messages.create.side_effect = [
            make_mock_response(stop_reason="tool_use", content=[tool_block]),
            make_mock_response(stop_reason="end_turn", content=[text_block]),
        ]

        loop.run([{"role": "user", "content": "hi"}])

        captured = capsys.readouterr()
        assert "bash" in captured.out
        assert "hi" in captured.out  # 工具执行输出

    def test_verbose_false_suppresses_output(self, monkeypatch, capsys):
        """verbose=False 应该不打印工具调用日志。"""
        config = make_config(monkeypatch)
        registry = ToolRegistry.create_default()
        loop = AgentLoop(config, registry, verbose=False)
        loop.client = MagicMock()

        tool_block = make_mock_content_block(
            "tool_use", id="call_1", name="bash",
            input={"command": "echo hi"},
        )
        text_block = make_mock_content_block("text", text="完成")

        loop.client.messages.create.side_effect = [
            make_mock_response(stop_reason="tool_use", content=[tool_block]),
            make_mock_response(stop_reason="end_turn", content=[text_block]),
        ]

        loop.run([{"role": "user", "content": "hi"}])

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_loop_stops_on_stop_sequence(self, monkeypatch):
        """stop_reason 是 'stop_sequence' 也应该结束。"""
        config = make_config(monkeypatch)
        registry = ToolRegistry()
        loop = AgentLoop(config, registry, verbose=False)
        loop.client = MagicMock()

        mock_msg = make_mock_response(
            stop_reason="stop_sequence",
            content=[make_mock_content_block("text", text="好的")],
        )
        loop.client.messages.create.return_value = mock_msg

        messages = [{"role": "user", "content": "停止"}]
        loop.run(messages)
        assert len(messages) == 2

    def test_loop_stops_on_max_tokens(self, monkeypatch):
        """stop_reason 是 'max_tokens' 也应该结束。"""
        config = make_config(monkeypatch)
        registry = ToolRegistry()
        loop = AgentLoop(config, registry, verbose=False)
        loop.client = MagicMock()

        mock_msg = make_mock_response(
            stop_reason="max_tokens",
            content=[make_mock_content_block("text", text="部分回复")],
        )
        loop.client.messages.create.return_value = mock_msg

        messages = [{"role": "user", "content": "长文本"}]
        loop.run(messages)
        assert len(messages) == 2

    def test_get_last_text(self, monkeypatch):
        """获取助理消息中的最后文本。"""
        config = make_config(monkeypatch)
        registry = ToolRegistry()
        loop = AgentLoop(config, registry, verbose=False)
        loop.client = MagicMock()

        text_block = make_mock_content_block("text", text="最后回复")

        loop.client.messages.create.return_value = make_mock_response(
            stop_reason="end_turn", content=[text_block],
        )

        messages = [{"role": "user", "content": "你好"}]
        loop.run(messages)

        # 提取文本的代码（与 __main__.py 一致）
        last_text = ""
        for block in messages[-1]["content"]:
            if getattr(block, "type", None) == "text":
                last_text = block.text
        assert last_text == "最后回复"
