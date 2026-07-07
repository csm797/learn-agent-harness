# Step 7: 学习 nanobot 加强安全体系

> 从 3 道关卡 ⟶ 5 层防御体系

---

## 改进动机

当前的安全实现（Step 6 的三关卡）有 3 个弱点：

1. **字符串匹配太弱** —— `"rm -rf /" in command` 会被 `"rm -rf /tmp"` 误杀，但 `"rm -fr /"` 绕过
2. **没有 Allowlist** —— 用户无法放行特定操作
3. **无安全文档** —— 缺少给 AI 代理读的安全规则

## 改进 1：正则化 Deny Patterns

参考 nanobot 的做法，用**正则表达式**替代字符串匹配：

```python
# ❌ 字符串匹配
"rm -rf /" in command       # 漏掉 rm -fr /，误杀 rm -rf /tmp

# ✅ 正则
r"\brm\s+-[rf]{1,2}\b"      # 匹配 rm -r, rm -rf, rm -fr, rm -r -f
```

正则优势：
- `\b` 单词边界 —— 防止 `grmrf` 误匹配
- `\s+` 空白符 —— 处理多个空格、tab
- `[rf]{1,2}` —— `-r`、`-f`、`-rf`、`-fr` 全部覆盖
- `?<=` 原子组 —— 不会误伤注释中的内容但实战中极少见

## 改进 2：Allowlist 覆盖

```python
# 只有当 allow_patterns 为空 或 没有匹配 allow 时才走 deny
explicitly_allowed = bool(self.allow_patterns) and any(
    re.search(p, lower) for p in self.allow_patterns
)
if not explicitly_allowed:
    for pattern in self.deny_patterns:
        if re.search(pattern, lower):
            return "Blocked"
```

这意味着：配置了 `allow_patterns` 后，只有匹配 allow 列表的命令能执行，其余全部拦截——从黑名单模式切换为白名单模式。

## 改进 3：读写分离路径策略

参考 nanobot 的 `_FsTool`，区分只读和可写路径：

```python
class PathPolicy:
    workdir: Path                  # 主工作区（可读写）
    extra_read_only: list[Path]    # 额外只读目录（媒体目录等）
    extra_writable: list[Path]     # 额外可写目录（输出目录等）
```

当前 `safe_path(path, workdir)` 对所有工具同等对待。改进后：
- `read_file`：可以读 workdir + extra_read_only
- `write_file`：只能写 workdir + extra_writable
- bash：路径检查只在 workdir 内

## 改进 4：安全文档

创建 `.agent/security.md`，记录安全边界规则。参考 nanobot 的 `.agent/security.md`，给 AI 代理（包括你自己和后续维护者）读的：

```markdown
# Security Boundaries

## Workspace Restriction
所有文件操作必须通过 safe_path 校验，禁止逃逸工作目录。

## Shell Security
bash 工具使用正则 deny 列表，allow 配置可覆盖。
...
```

---

## 本次变更

| 文件 | 操作 |
|------|------|
| `src/learn_cc/tools/bash.py` | 修改：正则 deny patterns + allowlist |
| `src/learn_cc/permission.py` | 修改：正则 + allowlist + PathPolicy |
| `.agent/security.md` | 新增：安全边界文档 |
| `tests/test_tools/test_bash.py` | 新增：正则 deny 测试 |
| `tests/test_permission.py` | 新增：PathPolicy 测试 |
