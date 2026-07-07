"""
base — 工具共享函数。

目前只有 safe_path，但后续可以加路径缓存、日志装饰器等。
"""

from pathlib import Path


class PathEscapeError(ValueError):
    """路径逃逸工作目录。"""


def safe_path(path: str, workdir: Path) -> Path:
    """
    校验并解析路径，防止逃逸工作目录。

    Args:
        path: 用户提供的路径（相对或绝对）。
        workdir: 工作目录安全边界。

    Returns:
        解析后的绝对 Path。

    Raises:
        PathEscapeError: 路径解析后不在 workdir 内。
    """
    full_path = (workdir / path).resolve()
    if not full_path.is_relative_to(workdir):
        raise PathEscapeError(f"路径逃逸工作目录: {path}")
    return full_path
