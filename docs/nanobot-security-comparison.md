# nanobot 权限安全体系分析与对比

> 学习 nanobot 的安全架构，对比我们自己的实现，找出差距和改进方向。

---

## nanobot 安全架构全景

nanobot 的安全不是分散在各工具中的，而是**体系化**的——有独立的 `security/` 包、有清晰的层级、有文档约束。

```
nanobot/security/
├── __init__.py                  # 空
├── workspace_policy.py          # 路径边界策略
├── workspace_access.py          # 工作区作用域 (ContextVar)
└── network.py                   # SSRF 防护

nanobot/.agent/
└── security.md                  # 安全规则文档（给 AI agent 读的）
```

### 第 1 层：工作区作用域（WorkspaceScope）

这是 nanobot 区别于我们实现的最核心概念。

```python
@dataclass(frozen=True)
class WorkspaceScope:
    project_path: Path        # 当前项目的根路径
    access_mode: str          # "restricted" | "full"
    restrict_to_workspace: bool
```

关键在于：**作用域是按请求/按 session 动态决定的**。什么叫「按请求动态决定」？

- 来自 WebUI 的消息可以带 `workspace_scope` 元数据，指定本次对话的工作区
- 来自 Telegram 的消息使用默认工作区
- 不同渠道可以有不同的访问级别

实现方式：`ContextVar`（上下文变量）—— 每个 agent turn 开始时绑定作用域，工具调用时从 `ContextVar` 读取。这比「全局变量」和「参数传递」都更灵活。

```python
# 绑定（每个 turn 开始）
token = bind_workspace_scope(scope)

# 读取（任何工具内部）
scope = current_workspace_scope()
```

> **ContextVar** 是 Python 3.7+ 的线程/协程隔离的全局变量。它像全局变量一样易用，但不同协程之间互不干扰。

### 第 2 层：路径边界策略（WorkspacePolicy）

nanobot 的路径校验比我们精细得多：

| 特性 | nanobot | learn-cc |
|------|---------|----------|
| 基本路径包含检查 | `is_path_within(path, root)` | `safe_path(path, workdir)` |
| 额外只读目录 | `extra_read_allowed_dirs` | ❌ 无 |
| 额外可写目录 | `extra_write_allowed_dirs` | ❌ 无 |
| 精确文件白名单 | `extra_allowed_files` | ❌ 无 |
| 媒体目录自动放行 | `get_media_dir()` | ❌ 无 |
| symlink 处理 | `resolve(strict=False)` 安全解析 | `.resolve()` 简单解析 |
| 区分读写能力 | `extra_allowed_dirs` 默认只读，写需单独声明 | ❌ 无 |

关键设计：**读写分离**。`extra_allowed_dirs` 默认是只读的，写操作必须通过 `extra_write_allowed_dirs` 明确声明。这让代码不可能无意地修改了只读区域的路径。

```python
class _FsTool(Tool):
    def __init__(self, ...):
        self._extra_read_allowed_dirs = [*(extra_allowed_dirs or []), ...]
        self._extra_write_allowed_dirs = extra_write_allowed_dirs or []
        # ^^ 读和写是分开的
```

### 第 3 层：Shell 安全

nanobot 的 shell 执行 (ExecTool) 有 4 道防线：

```
命令 → 路径逃逸检查 → deny 正则 → allow 覆盖 → SSRF 检查 → 执行
```

| 防线 | 实现 | 说明 |
|------|------|------|
| Path traversal | `_guard_command` 检查 `../` | 阻止路径穿越 |
| Deny list | 17 条正则（rm -rf, mkfs, dd, fork bomb...） | 正则匹配，更强 |
| Allow 覆盖 | `allow_patterns` 配置 | 用户可放行特定命令 |
| SSRF | `contains_internal_url()` | 阻止访问内网 |

我们之前只做了简单的字符串匹配 `if "rm -rf /" in command`，而 nanobot 用的是**正则**：`r"\brm\s+-[rf]{1,2}\b"` —— 匹配 `rm -rf`、`rm -fr`、`rm -r -f` 等变体，但不误伤 `grmrf` 这样的函数名。

### 第 4 层：SSRF 防护

nanobot 有独立的 `security/network.py`，对所有出站 HTTP 请求做校验：

- 阻止 loopback（127.0.0.1）
- 阻止 RFC1918 私有地址（10.x, 172.16-31.x, 192.168.x）
- 阻止 CGNAT 地址（100.64.x）
- 阻止 cloud metadata（169.254.169.254）
- 可通过 `ssrf_whitelist` 配置放行

### 第 5 层：安全文档约束

nanobot 的 `.agent/security.md` 是一份**给 AI agent 读的规则文件**（通过 CLAUDE.md 引用）：

```markdown
# Security Boundaries
...
**Rule**: Any new path-handling logic must go through the workspace path resolver
**Rule**: Do not add direct httpx.get / requests.get calls in tools.
```

这种「文档即约束」的实践非常值得学习：不是靠人记住规则，而是让规则出现在 AI 的上下文中。

---

## 与 learn-cc 的对比

### 我们的设计

```python
# permission.py — 三关卡流水线
Gate 1: deny_list        # 字符串匹配
Gate 2: rules            # lambda 判断
Gate 3: ask_user()       # input() 交互
```

| 维度 | nanobot | learn-cc |
|------|---------|----------|
| 安全架构 | 独立 `security/` 包，4 个模块 | 单文件 `permission.py` |
| 作用域 | `ContextVar` 动态切换 | 固定 `workdir` |
| 路径校验 | 读写分离，额外根目录，文件白名单 | `safe_path` 简单包含检查 |
| 命令过滤 | 正则 + allow 覆盖 | 字符串匹配 |
| SSRF | `validate_url_target()` | ❌ 无网络工具 |
| 用户交互 | Hooks 系统触发审批 | 阻塞式 `input()` |
| 安全文档 | `.agent/security.md` | ❌ 无 |
| 测试覆盖 | 各工具独立测试 | 21 个测试 |

### 核心差距

1. **没有作用域机制** —— 我们的 `workdir` 是固定的，不能动态切换
2. **没有 SSRF 防护** —— 因为我们还没有网络工具，但早晚需要
3. **用户审批是阻塞的** —— nanobot 通过 Hooks 异步处理
4. **没有安全文档** —— 没有给未来的自己/AI 代理看的规则

---

## 我们可以改进的方向

1. **引入 WorkspaceScope** —— 用 `ContextVar` 支持动态工作区切换，至少为后续 Hooks 做准备
2. **路径策略升级** —— 区分读/写权限，支持额外安全目录
3. **正则化 deny 模式** —— 把字符串匹配改为正则，避免变体绕过
4. **增加安全文档** —— `.agent/security.md`，记录安全边界

但这些改进需要匹配实际需求。如果你的用例只是本地 REPL，当前的实现已经够用。**安全不是越多越好，是刚好够用。** 对本地开发工具来说，阻塞式 `input()` 比异步回调更直接、更安全（你不可能错过审批弹窗）。

---

## 参考来源

所有分析基于 nanobot `v0.2.2` 源码：

- `nanobot/security/workspace_policy.py` — 路径边界策略
- `nanobot/security/workspace_access.py` — 工作区作用域
- `nanobot/security/network.py` — SSRF 防护
- `nanobot/agent/tools/shell.py` — Shell 执行工具
- `nanobot/agent/tools/filesystem.py` — 文件系统工具
- `nanobot/agent/tools/path_utils.py` — 路径工具函数
- `.agent/security.md` — 安全规则文档
