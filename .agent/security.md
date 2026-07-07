# Security Boundaries

> 本文档记录 learn-cc 的安全边界和约束规则。AI 代理在修改相关代码时必须遵守。

---

## Workspace Restriction

所有文件操作必须通过 `PathPolicy` 校验，禁止逃逸工作目录。

规则：
- `PathPolicy.resolve_read()` 允许 workdir + extra_read_only
- `PathPolicy.resolve_write()` 只允许 workdir + extra_writable
- 新增文件工具必须使用 PathPolicy 做路径解析

例外：
- 媒体目录自动加入 extra_read_only
- 精确文件白名单优先于目录策略

## Shell Security

Shell 执行有四道防线：

1. **正则 deny 列表** — `tools/bash.py` 中的 `DENY_PATTERNS`，匹配即拦截
2. **Allowlist 覆盖** — `allow_patterns` 非空时启用白名单模式
3. **权限系统** — `permission.py` 的 Gate 1/2/3
4. **超时 + 截断** — 120s 超时，50000 字符截断

**Rule**: 新增 bash 工具的安全规则必须同时更新 `DENY_PATTERNS` 和权限规则。

## Permission System

三关卡流水线（`permission.py`）：

```
Tool call → Gate 1 (deny patterns) → Gate 2 (rules) → Gate 3 (user approval) → execute
```

规则：
- Gate 1 只检查 bash 工具
- Gate 2 检查所有工具
- Gate 3 只在 Gate 2 命中时触发
- 新增工具必须考虑添加 Gate 2 规则

## SSRF Protection

当前无网络工具，所以无 SSRF 防护。
**添加网络工具时必须先实现 `validate_url_target()` 或同等防护。**

## Testing

安全相关的测试必须覆盖：

| 场景 | 测试文件 |
|------|---------|
| deny pattern 匹配 | `tests/test_tools/test_bash.py` |
| 路径逃逸 | `tests/test_tools/test_base.py` |
| Gate 1/2/3 | `tests/test_permission.py` |
| PathPolicy 读写 | `tests/test_permission.py` |

## Reference

安全架构参考 nanobot v0.2.2 的设计：

- `nanobot/security/workspace_policy.py` — 路径边界策略
- `nanobot/security/workspace_access.py` — 工作区作用域
- `nanobot/security/network.py` — SSRF 防护
- `.agent/security.md` — 本文档的原型

[对比分析](../docs/nanobot-security-comparison.md)
