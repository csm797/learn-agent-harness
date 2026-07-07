"""测试 safe_path 路径安全校验。"""

from pathlib import Path

import pytest

from learn_cc.tools.base import PathEscapeError, safe_path


class TestSafePath:
    def test_normal_relative_path(self, tmp_path):
        """合法的相对路径应该解析到 workdir 内。"""
        result = safe_path("sub/file.txt", tmp_path)
        assert result == (tmp_path / "sub/file.txt").resolve()
        assert result.is_relative_to(tmp_path)

    def test_absolute_path_within_workdir(self, tmp_path):
        """传入绝对路径但仍在 workdir 内，应该接受。"""
        target = tmp_path / "inner/file.txt"
        result = safe_path(str(target), tmp_path)
        assert result == target.resolve()

    def test_escape_with_dotdot(self, tmp_path):
        """使用 ../ 逃逸应该被拒绝。"""
        with pytest.raises(PathEscapeError):
            safe_path("../etc/passwd", tmp_path)

    def test_escape_with_absolute_path(self, tmp_path):
        """指向 workdir 外的绝对路径应该被拒绝。"""
        with pytest.raises(PathEscapeError):
            safe_path("/etc/passwd", tmp_path)

    def test_current_directory(self, tmp_path):
        """. 应该指向 workdir 自身。"""
        result = safe_path(".", tmp_path)
        assert result == tmp_path.resolve()
