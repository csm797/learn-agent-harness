# Step 12: Skill Loading

> 两级按需知识注入——s07 + nanobot SkillsLoader

---

## 两级设计

```
Layer 1（廉价，始终存在）：
  SYSTEM prompt 包含技能名称 + 一行简介
  "可用技能: testing, python-sdk, ..."
  ≈ 100 tokens

Layer 2（昂贵，按需加载）：
  AI 调用 load_skill("testing") → 完整 SKILL.md 内容
  通过 tool_result 注入上下文
  ≈ 2000 tokens
```

## 与 nanobot 的对比

| 特性 | s07 | nanobot | 我们的实现 |
|------|-----|---------|-----------|
| 技能来源 | `skills/` 目录 | workspace + builtin 两级 | `skills/` + `learn_cc/内置技能` |
| 元数据 | YAML frontmatter | YAML frontmatter + metadata | YAML frontmatter |
| 需求检查 | 无 | bins + env vars 检查 | 无（保持简单） |
| 总是加载 | 无 | `always` 标记 | 无 |
| 加载方式 | `load_skill` 工具 | `load_skill()` + `load_skills_for_context()` | `load_skill` 工具 |

## 本次变更

| 文件 | 操作 |
|------|------|
| `src/learn_cc/skills_loader.py` | 新增：SkillLoader + load_skill 工具 |
| `src/learn_cc/skills/` | 新增：内置技能目录 |
| `src/learn_cc/config.py` | 修改：build_system() 注入技能目录 |
| `src/learn_cc/tools/registry.py` | 修改：注册 load_skill |
| `src/learn_cc/__main__.py` | 修改：创建 SkillLoader |
| `tests/test_skills_loader.py` | 新增：测试 |
