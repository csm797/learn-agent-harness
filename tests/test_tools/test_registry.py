"""测试 ToolRegistry 注册表和分发。"""

from pathlib import Path

import pytest

from learn_cc.tools.bash import run_bash
from learn_cc.tools.registry import ToolRegistry


class TestToolRegistry:
    def test_create_default_has_all_tools(self):
        """create_default 应该注册所有内置工具。"""
        registry = ToolRegistry.create_default()
        expected = {"bash", "read_file", "write_file", "edit_file", "glob",
                     "long_task", "complete_goal", "todo_write"}
        # task 工具由 SubagentManager 动态注册，不在 create_default 中
        assert "task" not in registry.handlers
        assert set(registry.handlers.keys()) == expected

    def test_get_schemas_only_registered(self):
        """get_schemas 只返回已注册的工具。"""
        registry = ToolRegistry()
        registry.register("bash", run_bash)
        schemas = registry.get_schemas()
        names = [s["name"] for s in schemas]
        assert names == ["bash"]

    def test_dispatch_unknown_tool(self):
        """未知工具名称应返回错误。"""
        registry = ToolRegistry()
        result = registry.dispatch("nonexistent", Path("/tmp"))
        assert "未知工具" in result

    def test_dispatch_bash_tool(self, tmp_path):
        """分发 bash 工具应该执行命令。"""
        registry = ToolRegistry()
        registry.register("bash", run_bash)
        result = registry.dispatch("bash", tmp_path, command="echo ok")
        assert "ok" in result

    def test_dispatch_missing_argument(self, tmp_path):
        """缺少必要参数应该抛出 TypeError。"""
        registry = ToolRegistry()
        registry.register("bash", run_bash)
        with pytest.raises(TypeError):
            registry.dispatch("bash", tmp_path)  # 缺少 command 参数

    def test_register_twice_overwrites(self):
        """重复注册同名工具应该覆盖。"""
        registry = ToolRegistry()
        registry.register("bash", run_bash)
        registry.register("bash", run_bash)  # 再次注册
        assert len(registry.handlers) == 1
