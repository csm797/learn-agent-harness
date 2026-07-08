"""测试 TodoTracker：目标 + 任务列表 + 持久化 + Runtime Context。"""

import json
from pathlib import Path

import pytest

from learn_cc.todo import Goal, TodoTracker
from learn_cc.tools.planning import (
    run_complete_goal,
    run_long_task,
    run_todo_write,
    set_tracker,
)


class TestGoal:
    def test_default_state(self):
        """新 Goal 默认是 active 状态。"""
        g = Goal()
        assert g.status == "active"
        assert g.objective == ""

    def test_set_goal(self):
        """设定目标后 has_active_goal 应该为 True。"""
        t = TodoTracker()
        t.set_goal("完成项目重构")
        assert t.has_active_goal
        assert t.goal.objective == "完成项目重构"

    def test_complete_goal(self):
        """完成目标后状态变为 completed。"""
        t = TodoTracker()
        t.set_goal("写测试")
        t.complete_goal("写了 50 个测试")
        assert t.goal.status == "completed"
        assert "50 个测试" in (t.goal.recap or "")

    def test_complete_goal_no_active(self):
        """没有活跃目标时 complete_goal 返回错误。"""
        t = TodoTracker()
        result = t.complete_goal("总结")
        assert "错误" in result


class TestTodoTracker:
    def test_empty_initially(self):
        t = TodoTracker()
        assert t.todos == []
        assert not t.has_active_goal

    def test_update_resets_counter(self):
        t = TodoTracker()
        t.tick()
        t.tick()
        t.update_todos([{"content": "任务1", "status": "pending"}])
        assert t.rounds_since_update == 0
        assert len(t.todos) == 1

    def test_nag_after_threshold(self):
        t = TodoTracker(nag_after_rounds=2)
        t.tick()
        t.tick()
        assert t.should_nag()

    def test_no_nag_before_threshold(self):
        t = TodoTracker(nag_after_rounds=3)
        t.tick()
        assert not t.should_nag()


class TestRuntimeContext:
    def test_build_with_goal(self):
        """活跃目标存在时，Runtime Context 应该包含目标。"""
        t = TodoTracker()
        t.set_goal("重构项目")
        ctx = t.build_runtime_context()
        assert "重构项目" in ctx
        assert "active" in ctx

    def test_build_with_todos(self):
        """任务列表存在时，Runtime Context 应该显示进度。"""
        t = TodoTracker()
        t.update_todos([
            {"content": "任务A", "status": "completed"},
            {"content": "任务B", "status": "pending"},
        ])
        ctx = t.build_runtime_context()
        assert "任务A" in ctx
        assert "1/2" in ctx  # 进度

    def test_build_empty(self):
        """没有目标和任务时，Runtime Context 为空。"""
        t = TodoTracker()
        assert t.build_runtime_context() == ""

    def test_build_goal_and_todos(self):
        """目标和任务列表同时存在时，都显示。"""
        t = TodoTracker()
        t.set_goal("完成发布")
        t.update_todos([{"content": "测试", "status": "in_progress"}])
        ctx = t.build_runtime_context()
        assert "完成发布" in ctx
        assert "测试" in ctx


class TestPersistence:
    def test_save_and_load(self, tmp_path):
        """目标应该能保存并恢复。"""
        p = tmp_path / "goals.json"
        t1 = TodoTracker(persistence_path=p)
        t1.set_goal("持久的任务")
        t1.update_todos([{"content": "继续干", "status": "pending"}])

        # 新建 tracker 从同一文件加载
        t2 = TodoTracker(persistence_path=p)
        assert t2.goal.objective == "持久的任务"
        assert t2.todos[0]["content"] == "继续干"

    def test_save_completed_goal(self, tmp_path):
        """已完成的目标应该保存完成时间和总结。"""
        p = tmp_path / "goals.json"
        t1 = TodoTracker(persistence_path=p)
        t1.set_goal("写文档")
        t1.complete_goal("写完了 README")

        t2 = TodoTracker(persistence_path=p)
        assert t2.goal.status == "completed"
        assert "README" in (t2.goal.recap or "")

    def test_no_persistence_path(self):
        """没有设置 persistence_path 时，不报错。"""
        t = TodoTracker()
        t.set_goal("测试")
        # 不应抛出异常


class TestPlanningTools:
    def test_run_long_task(self):
        """run_long_task 应该设定目标。"""
        t = TodoTracker()
        set_tracker(t)
        result = run_long_task("重构整个项目")
        assert "目标" in result
        assert t.has_active_goal

    def test_run_complete_goal(self):
        """run_complete_goal 应该完成目标。"""
        t = TodoTracker()
        set_tracker(t)
        run_long_task("写 100 个测试")
        result = run_complete_goal("写了 100 个单元测试")
        assert "已完成" in result
        assert not t.has_active_goal

    def test_run_todo_write(self):
        """run_todo_write 应该更新任务列表。"""
        t = TodoTracker()
        set_tracker(t)
        result = run_todo_write([
            {"content": "步骤1", "status": "pending"},
        ])
        assert "已更新" in result
        assert t.todos[0]["content"] == "步骤1"

    def test_long_task_empty_goal(self):
        """空目标应该报错。"""
        t = TodoTracker()
        set_tracker(t)
        result = run_long_task("")
        assert "错误" in result


class TestRegistry:
    def test_new_tools_registered(self):
        """long_task 和 complete_goal 应该在注册表中。"""
        from learn_cc.tools.registry import ToolRegistry
        reg = ToolRegistry.create_default()
        assert "long_task" in reg.handlers
        assert "complete_goal" in reg.handlers
        assert "todo_write" in reg.handlers
