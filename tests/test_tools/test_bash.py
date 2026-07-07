"""测试 run_bash 命令执行。"""

from pathlib import Path

import pytest

from learn_cc.tools.bash import run_bash


class TestRunBash:
    def test_echo_command(self, tmp_path):
        """简单 echo 应该返回输出。"""
        result = run_bash("echo hello world", tmp_path)
        assert "hello world" in result

    def test_dangerous_command_blocked(self, tmp_path):
        """危险命令应该被拦截。"""
        result = run_bash("sudo rm -rf /", tmp_path)
        assert "拦截" in result

    def test_dangerous_command_partial(self, tmp_path):
        """部分匹配危险模式也应该被拦截。"""
        result = run_bash("echo sudo something", tmp_path)
        assert "拦截" in result

    def test_nonexistent_command(self, tmp_path):
        """不存在的命令应该返回错误。"""
        result = run_bash("nonexistent_command_xyz123", tmp_path)
        # Windows: "not recognized", Linux: "not found", 中文: "错误"
        assert any(kw in result.lower() for kw in ["错误", "not recognized", "not found"])

    def test_output_truncated(self, tmp_path):
        """大量输出应该被截断。"""
        result = run_bash("python -c 'print(\"x\" * 60000)'", tmp_path)
        assert len(result) <= 50000
