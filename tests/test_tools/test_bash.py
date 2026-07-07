"""测试 run_bash 命令执行。"""

from pathlib import Path

from learn_cc.tools.bash import _check_deny, run_bash


class TestCheckDeny:
    """正则 deny 检查的单元测试。"""

    def test_deny_rm_rf(self):
        """rm -rf / 应该被拦截。"""
        result = _check_deny("rm -rf /", deny_patterns=[r"\brm\s+-[rf]{1,2}\b"], allow_patterns=[])
        assert result is not None

    def test_deny_rm_fr(self):
        """rm -fr / 变体也应该被拦截。"""
        result = _check_deny("rm -fr /etc", deny_patterns=[r"\brm\s+-[rf]{1,2}\b"], allow_patterns=[])
        assert result is not None

    def test_allow_safe_rm(self):
        """单纯 'rm file' 没有 -rf 标志，应该通过。"""
        result = _check_deny("rm file.txt", deny_patterns=[r"\brm\s+-[rf]{1,2}\b"], allow_patterns=[])
        assert result is None

    def test_allowlist_overrides_deny(self):
        """allow_patterns 非空时，匹配 allow 的通过。"""
        result = _check_deny(
            "rm -rf /build/cache",
            deny_patterns=[r"\brm\s+-[rf]{1,2}\b"],
            allow_patterns=[r"rm\s+-rf\s+/build"],
        )
        assert result is None

    def test_allowlist_rejects_unlisted(self):
        """allow_patterns 非空时，不匹配 allow 的拦截。"""
        result = _check_deny(
            "rm -rf /etc",
            deny_patterns=[r"\brm\s+-[rf]{1,2}\b"],
            allow_patterns=[r"rm\s+-rf\s+/build"],
        )
        assert result is not None
        assert "白名单" in result


class TestRunBash:
    def test_echo_command(self, tmp_path):
        """简单 echo 应该返回输出。"""
        result = run_bash("echo hello world", tmp_path)
        assert "hello world" in result

    def test_dangerous_command_blocked(self, tmp_path):
        """危险命令应该被拦截。"""
        result = run_bash("rm -rf /", tmp_path)
        assert "拦截" in result

    def test_shutdown_blocked(self, tmp_path):
        """shutdown 命令应该被拦截。"""
        result = run_bash("shutdown now", tmp_path)
        assert "拦截" in result

    def test_del_file_blocked(self, tmp_path):
        """Windows del /f 应该被拦截。"""
        result = run_bash("del /f important.txt", tmp_path)
        assert "拦截" in result

    def test_rd_dir_blocked(self, tmp_path):
        """Windows rd /s 应该被拦截。"""
        result = run_bash("rd /s /q temp_dir", tmp_path)
        assert "拦截" in result

    def test_format_disk_blocked(self, tmp_path):
        """format 命令应该被拦截。"""
        result = run_bash("format D: /fs:NTFS", tmp_path)
        assert "拦截" in result

    def test_allowlist_custom(self, tmp_path):
        """自定义 allowlist 放行特定命令。"""
        result = run_bash(
            "rm -rf /build/cache",
            tmp_path,
            deny_patterns=[r"\brm\s+-[rf]{1,2}\b"],
            allow_patterns=[r"rm\s+-rf\s+/build"],
        )
        assert "拦截" not in result

    def test_nonexistent_command(self, tmp_path):
        """不存在的命令应该返回错误。"""
        result = run_bash("nonexistent_command_xyz123", tmp_path)
        assert any(kw in result.lower() for kw in ["错误", "not recognized", "not found"])

    def test_output_truncated(self, tmp_path):
        """大量输出应该被截断。"""
        result = run_bash("python -c 'print(\"x\" * 60000)'", tmp_path)
        assert len(result) <= 50000
