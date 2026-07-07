"""测试安全体系：PathPolicy + 三关卡权限。"""

from pathlib import Path

import pytest

from learn_cc.permission import (
    Decision,
    PathPolicy,
    PermissionChecker,
    PermissionResult,
    _PathEscapeError,
)


# ── PathPolicy 测试 ────────────────────────────────────


class TestPathPolicy:
    def test_resolve_read_within_workdir(self, tmp_path):
        """读取 workdir 内的文件应该允许。"""
        policy = PathPolicy(workdir=tmp_path)
        result = policy.resolve_read("sub/file.txt")
        assert result == (tmp_path / "sub/file.txt").resolve()

    def test_resolve_read_outside_denied(self, tmp_path):
        """读取 workdir 外的文件应该拒绝。"""
        policy = PathPolicy(workdir=tmp_path)
        with pytest.raises(_PathEscapeError):
            policy.resolve_read("../outside.txt")

    def test_resolve_read_extra_allowed(self, tmp_path):
        """extra_read_only 内的路径允许读取。"""
        extra = tmp_path / "media"
        extra.mkdir()
        policy = PathPolicy(workdir=tmp_path, extra_read_only=[extra])
        result = policy.resolve_read(str(extra / "image.png"))
        assert result == (extra / "image.png").resolve()

    def test_resolve_write_outside_denied(self, tmp_path):
        """写入 workdir 外应该拒绝。"""
        policy = PathPolicy(workdir=tmp_path)
        with pytest.raises(_PathEscapeError):
            policy.resolve_write("../malicious.txt")

    def test_resolve_write_extra_writable_allowed(self, tmp_path):
        """extra_writable 内的路径允许写入。"""
        out = tmp_path / "output"
        out.mkdir()
        policy = PathPolicy(workdir=tmp_path, extra_writable=[out])
        result = policy.resolve_write(str(out / "result.txt"))
        assert result == (out / "result.txt").resolve()

    def test_resolve_read_only_not_writable(self, tmp_path):
        """extra_read_only 中的路径不应可写（路径在 workdir 外时）。"""
        extra = tmp_path.parent / "media"
        extra.mkdir(exist_ok=True)
        policy = PathPolicy(workdir=tmp_path, extra_read_only=[extra])
        with pytest.raises(_PathEscapeError):
            policy.resolve_write(str(extra / "hack.txt"))


# ── PermissionResult 测试 ──────────────────────────────


class TestPermissionResult:
    def test_allow(self):
        r = PermissionResult.allow()
        assert r.decision == Decision.ALLOW
        assert r.reason is None

    def test_deny(self):
        r = PermissionResult.deny("blocked")
        assert r.decision == Decision.DENY
        assert r.reason == "blocked"

    def test_ask(self):
        r = PermissionResult.ask("sure?")
        assert r.decision == Decision.ASK
        assert r.reason == "sure?"


# ── Gate 1: 正则 deny 测试 ──────────────────────────────


class TestGate1RegexDeny:
    def test_deny_rm_rf(self):
        checker = PermissionChecker()
        policy = PathPolicy(workdir=Path("/tmp"))
        result = checker.check("bash", {"command": "rm -rf /"}, policy)
        assert result.decision == Decision.DENY

    def test_deny_rm_fr_variant(self):
        """rm -fr 变体也应该拦截。"""
        checker = PermissionChecker()
        policy = PathPolicy(workdir=Path("/tmp"))
        result = checker.check("bash", {"command": "rm -fr /etc"}, policy)
        assert result.decision == Decision.DENY

    def test_deny_shutdown(self):
        checker = PermissionChecker()
        policy = PathPolicy(workdir=Path("/tmp"))
        result = checker.check("bash", {"command": "shutdown -h now"}, policy)
        assert result.decision == Decision.DENY

    def test_deny_del_file(self):
        """Windows del 命令应该拦截。"""
        checker = PermissionChecker()
        policy = PathPolicy(workdir=Path("/tmp"))
        result = checker.check("bash", {"command": "del /f report.txt"}, policy)
        assert result.decision == Decision.DENY

    def test_deny_rd_dir(self):
        """Windows rd 命令应该拦截。"""
        checker = PermissionChecker()
        policy = PathPolicy(workdir=Path("/tmp"))
        result = checker.check("bash", {"command": "rd /s temp"}, policy)
        assert result.decision == Decision.DENY

    def test_deny_format(self):
        """format 命令应该拦截。"""
        checker = PermissionChecker()
        policy = PathPolicy(workdir=Path("/tmp"))
        result = checker.check("bash", {"command": "format D:"}, policy)
        assert result.decision == Decision.DENY

    def test_allow_safe_command(self):
        """安全命令通过 Gate 1。"""
        checker = PermissionChecker()
        policy = PathPolicy(workdir=Path("/tmp"))
        result = checker.check("bash", {"command": "echo hello"}, policy)
        assert result.decision != Decision.DENY

    def test_deny_only_applies_to_bash(self):
        """Gate 1 只检查 bash。"""
        checker = PermissionChecker()
        policy = PathPolicy(workdir=Path("/tmp"))
        result = checker.check("write_file", {"path": "/etc/passwd"}, policy)
        assert result.decision != Decision.DENY

    def test_allowlist_overrides_deny(self):
        """allowlist 可以放行被 deny 的命令（通过 Gate 1，且不触发 Gate 2）。"""
        checker = PermissionChecker(
            deny_patterns=[r"\bcurl\s+"],
            allow_patterns=[r"curl\s+http://internal"],
        )
        policy = PathPolicy(workdir=Path("/tmp"))
        result = checker.check("bash", {"command": "curl http://internal/api"}, policy)
        assert result.decision == Decision.ALLOW


# ── Gate 2: 规则测试 ──────────────────────────────────


class TestGate2Rules:
    def test_write_outside_asks(self, tmp_path):
        """写入外部路径应触发 ASK。"""
        checker = PermissionChecker()
        policy = PathPolicy(workdir=tmp_path)
        result = checker.check("write_file", {"path": "../outside.txt"}, policy)
        assert result.decision == Decision.ASK

    def test_write_inside_allowed(self, tmp_path):
        """写入内部路径应通过。"""
        checker = PermissionChecker()
        policy = PathPolicy(workdir=tmp_path)
        result = checker.check("write_file", {"path": "safe.txt"}, policy)
        assert result.decision == Decision.ALLOW

    def test_read_outside_asks(self, tmp_path):
        """读取外部路径应触发 ASK。"""
        checker = PermissionChecker()
        policy = PathPolicy(workdir=tmp_path)
        result = checker.check("read_file", {"path": "/etc/passwd"}, policy)
        assert result.decision == Decision.ASK

    def test_destructive_bash_asks(self, tmp_path):
        """破坏性 bash 应触发 ASK。"""
        checker = PermissionChecker()
        policy = PathPolicy(workdir=tmp_path)
        result = checker.check("bash", {"command": "rm important.txt"}, policy)
        assert result.decision == Decision.ASK

    def test_del_file_asks(self, tmp_path):
        """Windows del 也应该触发 ASK（非 /f 标志时）。"""
        checker = PermissionChecker()
        policy = PathPolicy(workdir=tmp_path)
        result = checker.check("bash", {"command": "del report.txt"}, policy)
        assert result.decision == Decision.ASK

    def test_erase_file_asks(self, tmp_path):
        """Windows erase 也应该触发 ASK。"""
        checker = PermissionChecker()
        policy = PathPolicy(workdir=tmp_path)
        result = checker.check("bash", {"command": "erase data.txt"}, policy)
        assert result.decision == Decision.ASK

    def test_safe_bash_passes_rules(self, tmp_path):
        """安全命令通过 Gate 2。"""
        checker = PermissionChecker()
        policy = PathPolicy(workdir=tmp_path)
        result = checker.check("bash", {"command": "echo hello"}, policy)
        assert result.decision == Decision.ALLOW

    def test_glob_always_allowed(self, tmp_path):
        """glob 不匹配任何规则。"""
        checker = PermissionChecker()
        policy = PathPolicy(workdir=tmp_path)
        result = checker.check("glob", {"pattern": "*.py"}, policy)
        assert result.decision == Decision.ALLOW


# ── Gate 3: 用户确认测试 ──────────────────────────────


class TestGate3AskUser:
    def test_user_allows(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        assert PermissionChecker.ask_user("bash", {"cmd": "rm file"}, "危险") is True

    def test_user_allows_yes(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "yes")
        assert PermissionChecker.ask_user("bash", {"cmd": "rm file"}, "危险") is True

    def test_user_denies(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "n")
        assert PermissionChecker.ask_user("bash", {"cmd": "rm file"}, "危险") is False

    def test_user_denies_default(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert PermissionChecker.ask_user("bash", {"cmd": "rm file"}, "危险") is False

    def test_user_denies_capital(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "N")
        assert PermissionChecker.ask_user("bash", {"cmd": "rm file"}, "危险") is False


# ── 自定义配置测试 ────────────────────────────────────


class TestCustomConfig:
    def test_custom_deny_list(self):
        checker = PermissionChecker(deny_patterns=[r"\bdocker\b"])
        policy = PathPolicy(workdir=Path("/tmp"))
        assert checker.check("bash", {"command": "docker run"}, policy).decision == Decision.DENY
        # 默认列表不再拦截
        result = checker.check("bash", {"command": "shutdown"}, policy)
        assert result.decision != Decision.DENY

    def test_custom_rules(self):
        checker = PermissionChecker(rules=[
            (["bash"], lambda a, p: "danger" in a.get("command", ""), "自定义"),
        ])
        policy = PathPolicy(workdir=Path("/tmp"))
        result = checker.check("bash", {"command": "danger"}, policy)
        assert result.decision == Decision.ASK
