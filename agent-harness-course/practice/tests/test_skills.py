"""Skill Loader / Context Builder —— 第 7 课（渐进披露）。"""
import json


class TestSkills:
    def test_load_and_catalog(self, tmp_path):
        from minimal_harness.skills import format_skills_catalog, load_skills

        skill_dir = tmp_path / "deploy"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: deploy\ndescription: 如何部署 demo 项目\n---\n\n正文步骤…",
            encoding="utf-8",
        )
        skills = load_skills(str(tmp_path))
        assert len(skills) == 1
        assert skills[0]["name"] == "deploy"
        assert skills[0]["location"].endswith("SKILL.md")

        catalog = format_skills_catalog(skills)
        assert "<available_skills>" in catalog
        assert "deploy" in catalog and "SKILL.md" in catalog
        # 渐进披露的关键断言：目录里绝不出现正文
        assert "正文步骤" not in catalog

    def test_empty_dir_empty_catalog(self, tmp_path):
        from minimal_harness.skills import format_skills_catalog, load_skills
        assert load_skills(str(tmp_path)) == []
        assert format_skills_catalog([]) == ""

    def test_build_context_includes_catalog_and_tools(self, tmp_path):
        from minimal_harness.skills import build_context
        from minimal_harness.types import Tool
        tool = Tool(name="read", description="r", parameters={}, execute=None)
        ctx = build_context("<available_skills>deploy</available_skills>", [], [tool])
        assert "deploy" in ctx.system_prompt
        assert ctx.tools and ctx.tools[0].name == "read"
