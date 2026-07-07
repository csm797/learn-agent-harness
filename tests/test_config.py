"""
Config 模块的单元测试。

测试原则：
1. 不依赖 .env 文件 —— 用 monkeypatch 模拟环境变量
2. 每个测试只测一个行为
3. 测试要能独立运行
"""

from pathlib import Path

import pytest

from learn_cc.config import Config, ConfigError


class TestConfigLoad:
    """Config.load() 的测试。"""

    def test_load_basic(self, monkeypatch):
        """正常加载所有必要字段。"""
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.setenv("MODEL_ID", "claude-3-opus")

        config = Config.load(env_file=None)

        assert config.api_key == "sk-test-key"
        assert config.model == "claude-3-opus"
        assert config.base_url is None
        assert isinstance(config.workdir, Path)
        assert "coding agent" in config.system_prompt

    def test_load_with_base_url(self, monkeypatch):
        """设置 base_url 时，应该被正确读取。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.setenv("MODEL_ID", "claude-3-opus")
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://custom-api.example.com")

        config = Config.load(env_file=None)

        assert config.base_url == "https://custom-api.example.com"

    def test_load_missing_api_key(self, monkeypatch):
        """缺少 API_KEY 应该抛出 ConfigError。"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("MODEL_ID", "claude-3-opus")

        with pytest.raises(ConfigError) as exc:
            Config.load(env_file=None)
        assert "ANTHROPIC_API_KEY" in str(exc.value)

    def test_load_missing_model(self, monkeypatch):
        """缺少 MODEL_ID 应该抛出 ConfigError。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.delenv("MODEL_ID", raising=False)

        with pytest.raises(ConfigError) as exc:
            Config.load(env_file=None)
        assert "MODEL_ID" in str(exc.value)

    def test_load_missing_both(self, monkeypatch):
        """同时缺少多个变量时，应该列出所有缺失项。"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("MODEL_ID", raising=False)

        with pytest.raises(ConfigError) as exc:
            Config.load(env_file=None)
        assert "ANTHROPIC_API_KEY" in str(exc.value)
        assert "MODEL_ID" in str(exc.value)

    def test_config_is_frozen(self, monkeypatch):
        """Config 实例应该是不可变的。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.setenv("MODEL_ID", "claude-3-opus")

        config = Config.load(env_file=None)

        with pytest.raises(Exception):
            config.api_key = "new-key"  # type: ignore

    def test_workdir_defaults_to_cwd(self, monkeypatch):
        """workdir 默认应该是当前工作目录。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.setenv("MODEL_ID", "claude-3-opus")

        config = Config.load(env_file=None)

        assert config.workdir == Path.cwd()

    def test_system_prompt_includes_workdir(self, monkeypatch):
        """system_prompt 应该包含 workdir 路径。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.setenv("MODEL_ID", "claude-3-opus")

        config = Config.load(env_file=None)

        assert str(config.workdir) in config.system_prompt

    def test_custom_deny_patterns(self, monkeypatch):
        """PERMISSION_DENY_PATTERNS 应该被解析为 tuple。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("MODEL_ID", "claude-test")
        monkeypatch.setenv("PERMISSION_DENY_PATTERNS", r"\bshutdown\b;\breboot\b")

        config = Config.load(env_file=None)

        assert len(config.deny_patterns) == 2
        assert r"\bshutdown\b" in config.deny_patterns
        assert r"\breboot\b" in config.deny_patterns

    def test_custom_allow_patterns(self, monkeypatch):
        """PERMISSION_ALLOW_PATTERNS 应该被解析为 tuple。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("MODEL_ID", "claude-test")
        monkeypatch.setenv("PERMISSION_ALLOW_PATTERNS", "echo;ls;git status")

        config = Config.load(env_file=None)

        assert len(config.allow_patterns) == 3
        assert "echo" in config.allow_patterns
        assert "ls" in config.allow_patterns

    def test_permission_from_config(self, monkeypatch):
        """from_config 应该使用 Config 中的 patterns。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("MODEL_ID", "claude-test")
        monkeypatch.setenv("PERMISSION_DENY_PATTERNS", r"\bcurl\s+")
        monkeypatch.setenv("PERMISSION_ALLOW_PATTERNS", r"curl\s+http://internal")

        from learn_cc.permission import PermissionChecker

        config = Config.load(env_file=None)
        checker = PermissionChecker.from_config(config)

        # allowlist 模式：curl internal 放行
        from learn_cc.permission import Decision, PathPolicy
        policy = PathPolicy(workdir=config.workdir)
        result = checker.check("bash", {"command": "curl http://internal/api"}, policy)
        assert result.decision == Decision.ALLOW

        # 不匹配 allow 的 curl 应该拦截
        result2 = checker.check("bash", {"command": "curl http://evil.com"}, policy)
        assert result2.decision == Decision.DENY

    def test_permission_defaults_when_not_set(self, monkeypatch):
        """不设置 PERMISSION_* 时，from_config 应该使用代码默认值。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("MODEL_ID", "claude-test")
        monkeypatch.delenv("PERMISSION_DENY_PATTERNS", raising=False)
        monkeypatch.delenv("PERMISSION_ALLOW_PATTERNS", raising=False)

        from learn_cc.permission import DEFAULT_DENY_PATTERNS, PermissionChecker

        config = Config.load(env_file=None)
        checker = PermissionChecker.from_config(config)

        assert checker.deny_patterns == DEFAULT_DENY_PATTERNS
        assert checker.allow_patterns == []

    def test_load_from_env_file(self, tmp_path, monkeypatch):
        """应该能从 .env 文件读取配置。"""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "ANTHROPIC_API_KEY=sk-from-file\n"
            "MODEL_ID=claude-from-file\n"
        )
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("MODEL_ID", raising=False)

        config = Config.load(env_file=str(env_file))

        assert config.api_key == "sk-from-file"
        assert config.model == "claude-from-file"
