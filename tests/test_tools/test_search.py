"""测试文件搜索工具 run_glob。"""

from learn_cc.tools.search import run_glob


class TestRunGlob:
    def test_glob_find_py_files(self, tmp_path):
        """搜索 .py 文件应该能找到。"""
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "c.txt").write_text("")

        result = run_glob("*.py", tmp_path)
        assert "a.py" in result
        assert "b.py" in result
        assert "c.txt" not in result

    def test_glob_recursive(self, tmp_path):
        """** 模式应该递归搜索。"""
        sub = tmp_path / "sub" / "deep"
        sub.mkdir(parents=True)
        (sub / "file.py").write_text("")

        result = run_glob("**/*.py", tmp_path)
        # Windows 用反斜杠，需要统一匹配
        assert "file.py" in result
        assert "deep" in result

    def test_glob_no_match(self, tmp_path):
        """没有匹配应该返回提示。"""
        result = run_glob("*.zzz", tmp_path)
        assert "无匹配" in result

    def test_glob_empty_dir(self, tmp_path):
        """空目录搜索应该无匹配。"""
        result = run_glob("*", tmp_path)
        assert "无匹配" in result
