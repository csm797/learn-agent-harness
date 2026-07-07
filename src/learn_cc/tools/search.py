"""
search — 文件搜索工具（glob 模式匹配）。
"""

from __future__ import annotations

import glob as glob_module
from pathlib import Path


def run_glob(pattern: str, workdir: Path) -> str:
    """
    使用 glob 模式搜索文件。

    Args:
        pattern: glob 模式，如 "**/*.py"。
        workdir: 工作目录。

    Returns:
        匹配的文件路径列表，每行一个。
    """
    try:
        results: list[str] = []
        for match in glob_module.glob(pattern, root_dir=workdir, recursive=True):
            match_path = (workdir / match).resolve()
            if match_path.is_relative_to(workdir):
                results.append(match)
        return "\n".join(results) if results else "(无匹配)"
    except Exception as e:
        return f"错误: {e}"
