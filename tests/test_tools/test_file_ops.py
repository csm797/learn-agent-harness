"""测试文件操作工具（read / write / edit）。"""

from pathlib import Path

from learn_cc.tools.file_ops import run_read, run_write, run_edit


class TestRunWrite:
    def test_write_new_file(self, tmp_path):
        """写新文件应该成功。"""
        result = run_write("new.txt", "hello", tmp_path)
        assert (tmp_path / "new.txt").read_text() == "hello"
        assert "已写入" in result

    def test_write_deep_path(self, tmp_path):
        """父目录不存在的路径应该自动创建。"""
        result = run_write("a/b/c/deep.txt", "deep", tmp_path)
        assert (tmp_path / "a/b/c/deep.txt").read_text() == "deep"
        assert "已写入" in result

    def test_write_overwrite(self, tmp_path):
        """覆盖已有文件。"""
        (tmp_path / "existing.txt").write_text("old")
        run_write("existing.txt", "new", tmp_path)
        assert (tmp_path / "existing.txt").read_text() == "new"

    def test_write_escape_detected(self, tmp_path):
        """尝试写到工作目录外应该返回错误。"""
        result = run_write("../escaped.txt", "content", tmp_path)
        assert "错误" in result


class TestRunRead:
    def test_read_existing_file(self, tmp_path):
        """读取存在的文件。"""
        (tmp_path / "test.txt").write_text("line1\nline2\nline3")
        result = run_read("test.txt", tmp_path)
        assert result == "line1\nline2\nline3"

    def test_read_with_limit(self, tmp_path):
        """limit 参数只返回前 N 行。"""
        (tmp_path / "test.txt").write_text("line1\nline2\nline3\nline4")
        result = run_read("test.txt", tmp_path, limit=2)
        assert "line1" in result
        assert "line2" in result
        assert "line3" not in result  # 被截断

    def test_read_nonexistent(self, tmp_path):
        """读取不存在的文件返回错误。"""
        result = run_read("no_such_file.txt", tmp_path)
        assert "错误" in result

    def test_read_escape_detected(self, tmp_path):
        """读取路径逃逸返回错误。"""
        result = run_read("/etc/passwd", tmp_path)
        assert "错误" in result


class TestRunEdit:
    def test_edit_existing_text(self, tmp_path):
        """替换存在的文本。"""
        (tmp_path / "test.txt").write_text("Hello World")
        result = run_edit("test.txt", "World", "Python", tmp_path)
        assert (tmp_path / "test.txt").read_text() == "Hello Python"
        assert "已编辑" in result

    def test_edit_only_first_occurrence(self, tmp_path):
        """应该只替换第一次出现的文本。"""
        (tmp_path / "test.txt").write_text("a a a")
        run_edit("test.txt", "a", "b", tmp_path)
        assert (tmp_path / "test.txt").read_text() == "b a a"

    def test_edit_text_not_found(self, tmp_path):
        """文本不存在时返回错误。"""
        (tmp_path / "test.txt").write_text("Hello")
        result = run_edit("test.txt", "Nonexistent", "X", tmp_path)
        assert "未找到" in result
        assert (tmp_path / "test.txt").read_text() == "Hello"  # 文件不变

    def test_edit_nonexistent_file(self, tmp_path):
        """编辑不存在的文件返回错误。"""
        result = run_edit("no_such.txt", "old", "new", tmp_path)
        assert "错误" in result
