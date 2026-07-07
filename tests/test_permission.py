"""测试三关卡权限系统。"""

from pathlib import Path

import pytest

from learn_cc.permission import (
    Decision,
    PermissionChecker,
    PermissionResult,
)


class TestPermissionResult:
    def test_allow(self):
        r = PermissionResult.allow()
        assert r.decision == Decision.ALLOW
        assert r.reason is None

    def test_deny(self):
        r = PermissionResult.deny("bad")
        assert r.decision == Decision.DENY
        assert r.reason == "bad"

    def test_ask(self):
        r = PermissionResult.ask("sure?")
        assert r.decision == Decision.ASK
        assert r.reason == "sure?"


class TestGate1DenyList:
    """Gate 1: 硬拒绝列表"""

    def test_deny_rm_rf(self):
        checker = PermissionChecker()
        result = checker.check("bash", {"command": "rm -rf /"}, Path("/tmp"))
        assert result.decision == Decision.DENY

    def test_deny_sudo(self):
        checker = PermissionChecker()
        result = checker.check("bash", {"command": "sudo apt install"}, Path("/tmp"))
        assert result.decision == Decision.DENY

    def test_allow_safe_command(self):
        """普通命令应该通过 Gate 1。"""
        checker = PermissionChecker()
        result = checker.check("bash", {"command": "echo hello"}, Path("/tmp"))
        assert result.decision != Decision.DENY

    def test_deny_only_applies_to_bash(self):
        """Gate 1 只检查 bash 工具。"""
        checker = PermissionChecker()
        result = checker.check("write_file", {"path": "/etc/passwd"}, Path("/tmp"))
        assert result.decision != Decision.DENY  # 跳过 Gate 1


class TestGate2Rules:
    """Gate 2: 规则匹配"""

    def test_write_outside_workspace(self, tmp_path):
        """写入工作目录外应触发 ASK。"""
        checker = PermissionChecker()
        result = checker.check(
            "write_file", {"path": "../outside.txt", "content": "x"}, tmp_path,
        )
        assert result.decision == Decision.ASK
        assert "写入" in (result.reason or "")

    def test_write_inside_workspace(self, tmp_path):
        """写入工作目录内应通过 Gate 2。"""
        checker = PermissionChecker()
        result = checker.check(
            "write_file", {"path": "safe.txt", "content": "x"}, tmp_path,
        )
        assert result.decision == Decision.ALLOW

    def test_read_outside_workspace(self, tmp_path):
        """读取外部文件应触发 ASK。"""
        checker = PermissionChecker()
        result = checker.check("read_file", {"path": "/etc/passwd"}, tmp_path)
        assert result.decision == Decision.ASK

    def test_destructive_bash(self, tmp_path):
        """破坏性 bash 命令应触发 ASK。"""
        checker = PermissionChecker()
        result = checker.check("bash", {"command": "rm important.txt"}, tmp_path)
        assert result.decision == Decision.ASK
        assert "破坏" in (result.reason or "")

    def test_destructive_bash_with_chmod(self, tmp_path):
        """chmod 777 应触发 ASK。"""
        checker = PermissionChecker()
        result = checker.check("bash", {"command": "chmod 777 file"}, tmp_path)
        assert result.decision == Decision.ASK

    def test_safe_bash_passes_rules(self, tmp_path):
        """安全命令应通过 Gate 2。"""
        checker = PermissionChecker()
        result = checker.check("bash", {"command": "echo hello"}, tmp_path)
        assert result.decision == Decision.ALLOW

    def test_glob_always_allowed(self, tmp_path):
        """glob 不匹配任何规则，应始终 ALLOW。"""
        checker = PermissionChecker()
        result = checker.check("glob", {"pattern": "*.py"}, tmp_path)
        assert result.decision == Decision.ALLOW


class TestGate3AskUser:
    """Gate 3: 用户确认"""

    def test_user_allows(self, monkeypatch):
        """输入 y 表示允许。"""
        monkeypatch.setattr("builtins.input", lambda _: "y")
        assert PermissionChecker.ask_user("bash", {"command": "rm file"}, "危险") is True

    def test_user_allows_yes(self, monkeypatch):
        """输入 yes 也表示允许。"""
        monkeypatch.setattr("builtins.input", lambda _: "yes")
        assert PermissionChecker.ask_user("bash", {"command": "rm file"}, "危险") is True

    def test_user_denies(self, monkeypatch):
        """输入 n 表示拒绝。"""
        monkeypatch.setattr("builtins.input", lambda _: "n")
        assert PermissionChecker.ask_user("bash", {"command": "rm file"}, "危险") is False

    def test_user_denies_default(self, monkeypatch):
        """回车（空输入）默认拒绝。"""
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert PermissionChecker.ask_user("bash", {"command": "rm file"}, "危险") is False

    def test_user_denies_capital(self, monkeypatch):
        """大小写不敏感。"""
        monkeypatch.setattr("builtins.input", lambda _: "N")
        assert PermissionChecker.ask_user("bash", {"command": "rm file"}, "危险") is False


class TestCustomRules:
    """自定义规则"""

    def test_custom_deny_list(self):
        """可以传入自定义拒绝列表。"""
        checker = PermissionChecker(deny_list=["docker"])
        result = checker.check("bash", {"command": "docker run"}, Path("/tmp"))
        assert result.decision == Decision.DENY

        # 默认列表中的 sudo 不再拦截
        result2 = checker.check("bash", {"command": "sudo echo"}, Path("/tmp"))
        assert result2.decision != Decision.DENY

    def test_custom_rules(self):
        """可以传入自定义规则。"""
        checker = PermissionChecker(rules=[
            (["bash"], lambda args, wd: "danger" in args.get("command", ""), "自定义规则"),
        ])
        result = checker.check("bash", {"command": "danger"}, Path("/tmp"))
        assert result.decision == Decision.ASK
        assert "自定义" in (result.reason or "")
