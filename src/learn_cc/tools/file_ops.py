"""
file_ops — 文件读写编辑工具。

包含 read、write、edit 三个操作，共享 safe_path 做路径校验。
"""

from __future__ import annotations

from pathlib import Path

from learn_cc.tools.base import safe_path


def run_read(path: str, workdir: Path, limit: int | None = None) -> str:
    """
    读取文件内容。

    Args:
        path: 文件路径（相对工作目录）。
        workdir: 工作目录。
        limit: 可选，只返回前 N 行。

    Returns:
        文件文本内容。
    """
    try:
        file_path = safe_path(path, workdir)
        lines = file_path.read_text(encoding="utf-8").splitlines()
        if limit is not None and limit < len(lines):
            lines = lines[:limit] + [f"... (还有 {len(lines) - limit} 行)"]
        return "\n".join(lines)
    except Exception as e:
        return f"错误: {e}"


def run_write(path: str, content: str, workdir: Path) -> str:
    """
    写入文件。父目录不存在时自动创建。

    Args:
        path: 文件路径。
        content: 文件内容。
        workdir: 工作目录。

    Returns:
        操作结果描述。
    """
    try:
        file_path = safe_path(path, workdir)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"已写入 {len(content)} 字节到 {path}"
    except Exception as e:
        return f"错误: {e}"


def run_edit(path: str, old_text: str, new_text: str, workdir: Path) -> str:
    """
    编辑文件：替换文本（只替换第一次出现）。

    Args:
        path: 文件路径。
        old_text: 要替换的旧文本。
        new_text: 新文本。
        workdir: 工作目录。

    Returns:
        操作结果描述。
    """
    try:
        file_path = safe_path(path, workdir)
        text = file_path.read_text(encoding="utf-8")
        if old_text not in text:
            return f"错误: 在 {path} 中未找到要替换的文本"
        file_path.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
        return f"已编辑 {path}"
    except Exception as e:
        return f"错误: {e}"
