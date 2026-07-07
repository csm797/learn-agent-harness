"""测试 Hook 系统。"""

from pathlib import Path

import pytest

from learn_cc.agent import AgentLoop
from learn_cc.config import Config
from learn_cc.hooks import Hook, HookRegistry
from learn_cc.tools.registry import ToolRegistry


# ── 辅助：mock 配置 ─────────────────────────────────


def make_config(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("MODEL_ID", "claude-test")
    return Config.load(env_file=None)


# ── 测试用 Hook ──────────────────────────────────────


class LogHook(Hook):
    """记录所有调用的 hook。"""

    def __init__(self):
        self.calls: list[str] = []

    def before_tool(self, name, args):
        self.calls.append(f"before:{name}")
        return None

    def after_tool(self, name, args, output):
        self.calls.append(f"after:{name}")

    def before_llm(self, messages):
        self.calls.append("before_llm")

    def after_llm(self, response):
        self.calls.append("after_llm")

    def on_stop(self, messages):
        self.calls.append("on_stop")
        return None


class BlockHook(Hook):
    """阻断特定工具的 hook。"""

    def __init__(self, block_name: str = "bash"):
        self.block_name = block_name

    def before_tool(self, name, args):
        if name == self.block_name:
            return f"blocked:{name}"
        return None


class ErrorHook(Hook):
    """故意抛异常的 hook（测试错误隔离）。"""

    def before_tool(self, name, args):
        raise RuntimeError("hook crashed!")


# ── HookRegistry 测试 ────────────────────────────────


class TestHookRegistry:
    def test_register_and_dispatch(self):
        """注册 hook 后，分发应该调用它。"""
        registry = HookRegistry()
        hook = LogHook()
        registry.register(hook)

        registry.before_tool("bash", {"command": "echo"})
        assert "before:bash" in hook.calls

    def test_before_tool_block(self):
        """before_tool 返回字符串应该阻断。"""
        registry = HookRegistry()
        registry.register(BlockHook("bash"))

        result = registry.before_tool("bash", {"command": "rm -rf /"})
        assert result is not None
        assert "blocked" in result

    def test_before_tool_pass(self):
        """before_tool 返回 None 应该允许。"""
        registry = HookRegistry()
        registry.register(BlockHook("bash"))

        result = registry.before_tool("read_file", {"path": "test.txt"})
        assert result is None

    def test_multiple_hooks_all_execute(self):
        """多个 hook 都应该执行。"""
        registry = HookRegistry()
        h1 = LogHook()
        h2 = LogHook()
        registry.register(h1)
        registry.register(h2)

        registry.before_llm([])
        assert "before_llm" in h1.calls
        assert "before_llm" in h2.calls

    def test_error_isolation(self):
        """一个 hook 抛异常不应该影响其他 hook。"""
        registry = HookRegistry()
        error_hook = ErrorHook()
        log_hook = LogHook()
        registry.register(error_hook)
        registry.register(log_hook)

        # should not raise
        registry.before_tool("bash", {"command": "echo"})
        assert "before:bash" in log_hook.calls

    def test_unregister(self):
        """注销后 hook 不再被调用。"""
        registry = HookRegistry()
        hook = LogHook()
        registry.register(hook)
        registry.unregister(hook)

        registry.before_llm([])
        assert "before_llm" not in hook.calls

    def test_before_tool_first_block_wins(self):
        """多个 hook 中第一个返回阻断的生效。"""
        registry = HookRegistry()
        block = BlockHook("bash")
        log = LogHook()
        registry.register(block)
        registry.register(log)

        result = registry.before_tool("bash", {"command": "echo"})
        assert result is not None
        # log hook 的 before_tool 不应被调用（已阻断）
        assert "before:bash" not in log.calls

    def test_on_stop_inject(self):
        """on_stop 返回字符串应该注入消息。"""
        class InjectHook(Hook):
            def on_stop(self, messages):
                return "继续干活"

        registry = HookRegistry()
        registry.register(InjectHook())

        result = registry.on_stop([])
        assert result == "继续干活"


# ── AgentLoop 集成测试 ───────────────────────────────


class TestAgentLoopHooks:
    def test_hooks_called_during_loop(self, monkeypatch):
        """hooks 应该在 Agent 循环中被调用。"""
        from unittest.mock import MagicMock, patch

        config = make_config(monkeypatch)
        registry = ToolRegistry.create_default()
        log_hook = LogHook()
        hooks = HookRegistry()
        hooks.register(log_hook)

        loop = AgentLoop(config, registry, verbose=False, hooks=hooks)
        loop.client = MagicMock()

        # Mock API 返回文本
        mock_msg = MagicMock()
        mock_msg.stop_reason = "end_turn"
        mock_msg.content = [MagicMock(type="text", text="ok")]
        loop.client.messages.create.return_value = mock_msg

        loop.run([{"role": "user", "content": "hi"}])

        assert "before_llm" in log_hook.calls
        assert "after_llm" in log_hook.calls
        assert "on_stop" in log_hook.calls

    def test_hook_blocks_tool(self, monkeypatch):
        """hook 阻断工具调用。"""
        from unittest.mock import MagicMock

        config = make_config(monkeypatch)
        registry = ToolRegistry.create_default()
        hooks = HookRegistry()
        hooks.register(BlockHook("bash"))

        loop = AgentLoop(config, registry, verbose=False, hooks=hooks)
        loop.client = MagicMock()

        # 先返回 tool_use，再返回 end_turn
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "call_1"
        tool_block.name = "bash"
        tool_block.input = {"command": "rm -rf /"}

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "被拦截了"

        loop.client.messages.create.side_effect = [
            MagicMock(stop_reason="tool_use", content=[tool_block]),
            MagicMock(stop_reason="end_turn", content=[text_block]),
        ]

        messages = [{"role": "user", "content": "执行命令"}]
        loop.run(messages)

        # tool_result 应该是阻断消息，而不是命令输出
        tool_results = messages[2]["content"]
        assert "blocked" in tool_results[0]["content"]

    def test_hook_after_tool_receives_output(self, monkeypatch):
        """after_tool 应该收到工具执行结果。"""
        from unittest.mock import MagicMock

        class CaptureOutputHook(Hook):
            def __init__(self):
                self.captured: list[str] = []

            def after_tool(self, name, args, output):
                self.captured.append(f"{name}:{output[:20]}")

        config = make_config(monkeypatch)
        registry = ToolRegistry.create_default()
        capture = CaptureOutputHook()
        hooks = HookRegistry()
        hooks.register(capture)

        loop = AgentLoop(config, registry, verbose=False, hooks=hooks)
        loop.client = MagicMock()

        mock_msg = MagicMock()
        mock_msg.stop_reason = "end_turn"
        mock_msg.content = [MagicMock(type="text", text="done")]
        loop.client.messages.create.return_value = mock_msg

        # 单次 tool_use
        mock_msg2 = MagicMock()
        mock_msg2.stop_reason = "tool_use"
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "call_1"
        tool_block.name = "bash"
        tool_block.input = {"command": "echo hello"}
        mock_msg2.content = [tool_block]

        end_msg = MagicMock()
        end_msg.stop_reason = "end_turn"
        end_msg.content = [MagicMock(type="text", text="ok")]

        loop.client.messages.create.side_effect = [mock_msg2, end_msg]

        loop.run([{"role": "user", "content": "echo"}])

        assert "bash:hello" in capture.captured or "bash:错误" in capture.captured

    def test_hook_error_does_not_crash_loop(self, monkeypatch):
        """hook 异常不应该导致循环崩溃。"""
        from unittest.mock import MagicMock

        config = make_config(monkeypatch)
        registry = ToolRegistry.create_default()
        hooks = HookRegistry()
        hooks.register(ErrorHook())  # 这个 hook 会抛异常

        loop = AgentLoop(config, registry, verbose=False, hooks=hooks)
        loop.client = MagicMock()

        mock_msg = MagicMock()
        mock_msg.stop_reason = "end_turn"
        mock_msg.content = [MagicMock(type="text", text="ok")]
        loop.client.messages.create.return_value = mock_msg

        # 应该不抛异常
        loop.run([{"role": "user", "content": "hi"}])
