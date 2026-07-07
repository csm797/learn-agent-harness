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
