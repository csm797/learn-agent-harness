# Step 6: 权限系统（三关卡）

> Gate 1: 硬拒绝 → Gate 2: 规则匹配 → Gate 3: 用户确认

---

## 要解决的问题

当前项目的工具可以随意执行：

```python
AgentLoop._execute_tool_calls()
    → registry.dispatch()   # 直接执行，无拦截
```

这意味着 AI 可以：
- 执行 `rm -rf /`（虽然 `bash.py` 有简单拦截）
- 写入系统目录 `/etc/`
- 运行破坏性命令

问题在于：
1. **拦截范围不全** —— 只有 `bash.py` 有危险命令检测，其他工具（write_file）没有
2. **硬编码** —— 拦截规则不可配置
3. **无用户确认** —— 危险操作不征求用户意见

## 三关卡设计

```
Tool call
    │
    ▼
┌──────────┐
│ Gate 1   │ 硬拒绝列表 —— 无条件的禁止
│ Deny     │ 匹配即拦截，不过问
└────┬─────┘
     │ (通过)
     ▼
┌──────────┐
│ Gate 2   │ 规则匹配 —— 上下文相关
│ Rules    │ 写外部路径？危险命令？
└────┬─────┘
     │ (命中规则)
     ▼
┌──────────┐
│ Gate 3   │ 用户确认 —— 交互式审批
│ Ask User │ "允许执行吗？[y/N]"
└────┬─────┘
     │ (允许)
     ▼
  执行工具
```

## 为什么用独立模块而不是散在工具里？

权限是**横切关注点（Cross-Cutting Concern）** —— 它影响多个工具，但不属于任何一个。

```
❌ 分散：每个工具自己检查权限
tools/bash.py:     if dangerous: block
tools/file_ops.py: if outside: block
# 添加新工具时容易遗漏

✅ 集中：一个 PermissionChecker 统一处理
tools/permission.py: check(tool_name, args) → Result
# 加新工具时只要加规则
```

这就是 **AOP（Aspect-Oriented Programming，面向切面编程）** 的朴素版本。

## 与 AgentLoop 的集成

`check_permission()` 被 `_execute_tool_calls()` 调用：

```python
# agent.py
def _execute_tool_calls(self, content):
    for block in content:
        ...
        result = self.permission.check(block.name, block.input)
        if result.code == DENY:
            output = result.message       # 直接拒绝
        elif result.code == ASK:
            output = self._ask_user(...)   # 询问用户
        else:  # ALLOW
            output = self.registry.dispatch(...)
```

集成点只有 3 行，且不需要修改任何工具函数。

## 测试策略

| 场景 | 测试方法 | 预期 |
|------|---------|------|
| Gate 1 命中 | deny_list 中的命令 | 拒绝 |
| Gate 1 未命中 | 普通命令 | 通过 |
| Gate 2 命中规则 | 写外部路径 | ASK |
| Gate 2 未命中 | 写内部路径 | 通过 |
| Gate 3 用户允许 | mock input → "y" | 允许 |
| Gate 3 用户拒绝 | mock input → "n" | 拒绝 |

---

## 决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 权限模型 | 三关卡流水线 | 清晰、可扩展 |
| 用户交互 | `input()` 直接询问 | 保持简单，不引入第三方 |
| 规则格式 | (tools, check_fn, message) 元组 | 声明式，易读 |
| 集成方式 | AgentLoop 内调用 | 横切关注点，不侵入工具 |

---

## 下一步

Step 7 实现 Hooks 系统 —— 工具执行前后触发回调，实现日志、审计等扩展。
