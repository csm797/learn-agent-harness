"""
skills_loader — 技能加载系统。

两级设计：
  Level 1（廉价）：SYSTEM prompt 中列出技能名称和简介
  Level 2（昂贵）：load_skill 工具按需加载完整 SKILL.md

参考 s07 + nanobot SkillsLoader。
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import yaml


class SkillLoader:
    """
    技能加载器。

    扫描 skills 目录下的 SKILL.md（含 YAML frontmatter），
    提供目录浏览和按需加载功能。
    """

    def __init__(self, *skill_dirs: str | Path):
        """
        Args:
            skill_dirs: 一个或多个技能目录。先列出的优先。
        """
        self._dirs = [Path(d) for d in skill_dirs]
        self._registry: dict[str, dict] = {}
        self._scan()

    def _scan(self) -> None:
        """扫描所有技能目录，构建注册表。"""
        self._registry = {}
        for base in self._dirs:
            if not base.exists():
                continue
            for entry in sorted(base.iterdir()):
                if not entry.is_dir():
                    continue
                skill_file = entry / "SKILL.md"
                if not skill_file.exists():
                    continue
                name = entry.name
                if name in self._registry:
                    continue  # 前面的目录优先
                raw = skill_file.read_text(encoding="utf-8")
                meta, body = _parse_frontmatter(raw)
                self._registry[name] = {
                    "name": name,
                    "title": meta.get("name", name),
                    "description": meta.get("description", _first_heading(body) or name),
                    "content": raw,
                }

    def list_skills(self) -> Sequence[dict]:
        """返回所有技能的名称和简介（Level 1 用）。"""
        return [
            {"name": s["name"], "description": s["description"]}
            for s in sorted(self._registry.values(), key=lambda x: x["name"])
        ]

    def build_catalog(self) -> str:
        """构建技能目录文本（注入 SYSTEM prompt 用）。"""
        skills = self.list_skills()
        if not skills:
            return ""
        lines = ["可用技能:"]
        for s in skills:
            lines.append(f"- **{s['name']}**: {s['description']}")
        lines.append("使用 load_skill(\"名称\") 加载完整内容。")
        return "\n".join(lines)

    def load_skill(self, name: str) -> str | None:
        """按名称加载完整技能内容（Level 2 用）。"""
        skill = self._registry.get(name)
        if skill is None:
            return None
        return skill["content"]

    def reload(self) -> None:
        """重新扫描技能目录（添加新技能后调用）。"""
        self._scan()


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    解析 SKILL.md 的 YAML frontmatter。

    Returns:
        (metadata dict, body text without frontmatter)
    """
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, parts[2].strip()


def _first_heading(body: str) -> str:
    """提取正文的第一个 # 标题作为简介。"""
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return ""


# ── 工具函数（由 registry 注册） ──


_current_loader: SkillLoader | None = None


def set_loader(loader: SkillLoader) -> None:
    """设置全局 SkillLoader（用于工具函数访问）。"""
    global _current_loader
    _current_loader = loader


def _get_loader() -> SkillLoader:
    global _current_loader
    assert _current_loader is not None, "SkillLoader 未初始化，请先调用 set_loader()"
    return _current_loader


def run_load_skill(name: str, workdir: object = None) -> str:
    """
    加载技能完整内容（load_skill 工具处理函数）。

    Args:
        name: 技能名称。
        workdir: 兼容接口。

    Returns:
        技能完整内容，或错误消息。
    """
    loader = _get_loader()
    content = loader.load_skill(name)
    if content is None:
        available = ", ".join(s["name"] for s in loader.list_skills())
        return f"错误: 未找到技能 '{name}'。可用技能: {available}"
    return content
