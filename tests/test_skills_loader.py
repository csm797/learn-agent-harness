"""测试技能加载系统。"""

from pathlib import Path

import pytest

from learn_cc.skills_loader import (
    SkillLoader,
    _parse_frontmatter,
    run_load_skill,
    set_loader,
)


class TestParseFrontmatter:
    def test_no_frontmatter(self):
        """没有 frontmatter 时返回空 dict 和原文本。"""
        meta, body = _parse_frontmatter("# Hello\nworld")
        assert meta == {}
        assert body == "# Hello\nworld"

    def test_valid_frontmatter(self):
        """有效 frontmatter 应该被解析。"""
        text = "---\nname: test\ndescription: a test\n---\n# Body"
        meta, body = _parse_frontmatter(text)
        assert meta["name"] == "test"
        assert meta["description"] == "a test"
        assert "# Body" in body

    def test_empty_frontmatter(self):
        """空的 frontmatter 应该返回空 dict。"""
        text = "---\n---\n# Body"
        meta, body = _parse_frontmatter(text)
        assert meta == {}
        assert body == "# Body"


class TestSkillLoader:
    def test_load_skill_by_name(self, tmp_path):
        """按名称加载技能。"""
        skill_dir = tmp_path / "testing"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: testing\ndescription: 测试技能\n---\n# 测试\n内容"
        )
        loader = SkillLoader(tmp_path)
        content = loader.load_skill("testing")
        assert content is not None
        assert "测试" in content

    def test_load_skill_not_found(self, tmp_path):
        """不存在的技能返回 None。"""
        loader = SkillLoader(tmp_path)
        assert loader.load_skill("nonexistent") is None

    def test_list_skills(self, tmp_path):
        """list_skills 返回名称和简介。"""
        for name, desc in [("skill_a", "A技能"), ("skill_b", "B技能")]:
            d = tmp_path / name
            d.mkdir()
            (d / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: {desc}\n---\n# {name}"
            )
        loader = SkillLoader(tmp_path)
        skills = loader.list_skills()
        assert len(skills) == 2
        names = {s["name"] for s in skills}
        assert names == {"skill_a", "skill_b"}

    def test_build_catalog(self, tmp_path):
        """build_catalog 返回 Markdown 格式的目录。"""
        d = tmp_path / "myskill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: myskill\ndescription: 我的技能\n---\n# 详情"
        )
        loader = SkillLoader(tmp_path)
        catalog = loader.build_catalog()
        assert "myskill" in catalog
        assert "我的技能" in catalog
        assert "load_skill" in catalog

    def test_empty_catalog(self, tmp_path):
        """没有技能时目录为空。"""
        loader = SkillLoader(tmp_path / "nonexistent")
        assert loader.build_catalog() == ""

    def test_priority_order(self, tmp_path):
        """先列出的目录优先。"""
        d1 = tmp_path / "dir1"
        d2 = tmp_path / "dir2"
        d1.mkdir()
        d2.mkdir()
        (d1 / "common").mkdir()
        (d1 / "common" / "SKILL.md").write_text(
            "---\nname: common\ndescription: from dir1\n---\n# 1"
        )
        (d2 / "common").mkdir()
        (d2 / "common" / "SKILL.md").write_text(
            "---\nname: common\ndescription: from dir2\n---\n# 2"
        )
        loader = SkillLoader(d1, d2)
        content = loader.load_skill("common")
        assert "1" in content  # dir1 优先

    def test_reload(self, tmp_path):
        """reload 应该扫描新添加的技能。"""
        loader = SkillLoader(tmp_path)
        assert loader.list_skills() == []
        d = tmp_path / "newskill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: newskill\ndescription: new\n---\n# New"
        )
        loader.reload()
        assert len(loader.list_skills()) == 1


class TestRunLoadSkill:
    def test_load_existing(self, tmp_path):
        """加载存在的技能。"""
        d = tmp_path / "myskill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: myskill\ndescription: 我的\n---\n# 内容"
        )
        loader = SkillLoader(tmp_path)
        set_loader(loader)
        result = run_load_skill("myskill")
        assert "内容" in result

    def test_load_nonexistent(self, tmp_path):
        """加载不存在的技能返回错误。"""
        loader = SkillLoader(tmp_path)
        set_loader(loader)
        result = run_load_skill("nope")
        assert "错误" in result
        assert "未找到" in result


class TestRegistry:
    def test_load_skill_in_tool_schemas(self):
        """load_skill 应该在工具 schemas 中。"""
        from learn_cc.tools.registry import ToolRegistry
        reg = ToolRegistry()
        schemas = reg.get_schemas()
        names = [s["name"] for s in schemas]
        # 不在 create_default 中，但 schema 应该在 TOOL_SCHEMAS 里
        # 实际上 schema 是静态的，我们验证它存在
        from learn_cc.tools.registry import TOOL_SCHEMAS
        schema_names = {s["name"] for s in TOOL_SCHEMAS}
        assert "load_skill" in schema_names
