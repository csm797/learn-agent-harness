# Step 2: Config 模块提取

> 关注点分离（Separation of Concerns）的第一刀

---

## 要解决的问题

原 `code.py` 第 31-39 行"散落"了所有配置相关代码：

```python
# 问题 1：import 时就有副作用
load_dotenv(override=True)           # 读文件
if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)  # 改全局

# 问题 2：模块级全局变量
WORKDIR = Path.cwd()                 # import 时固定
client = Anthropic(base_url=...)     # 创建网络客户端
MODEL = os.environ["MODEL_ID"]       # 缺环境变量直接 crash
SYSTEM = "..."                       
```

**4 个问题：**

| 问题 | 后果 |
|------|------|
| 模块级副作用 | `import code` 就会读 .env 文件、连 API |
| 全局可变变量 | 任何函数都能改，测试无法隔离 |
| 缺失时 crash | KeyError，没有友好提示 |
| 职责混在一起 | 配置、客户端创建、提示词混在文件顶部 |

## 设计思路

### 原则：配置是数据，不是代码

配置是从环境（文件、环境变量）读入的**数据**，应该与使用它的**逻辑**分离。

### 为什么用 dataclass 而不是 dict？

```python
# ❌ dict — 类型不安全
config = {"api_key": "sk-...", "model": "claude-3"}
config["api_ky"]  # 拼错了也不报错

# ✅ dataclass — IDE 补全 + 类型校验
@dataclass
class Config:
    api_key: str
    model: str

config.api_key  # IDE 自动补全
```

### 为什么用 frozen=True？

防止配置在运行时被意外修改：

```python
@dataclass(frozen=True)
class Config:
    api_key: str

config.api_key = "hacked"  # ❌ dataclass 报错
```

### 为什么用 classmethod load()？

```python
# ❌ 模块级自动加载
config = load_config()     # import 时就执行了

# ✅ 显式调用
config = Config.load()     # 只有调用时才执行
```

前者写起来少一行，但在测试环境里你无法控制它 —— import 就执行了。后者你可以在 setUp 里 mock。

### 错误处理

原代码 `MODEL = os.environ["MODEL_ID"]` 用 `[]` 访问，缺了就 `KeyError`。改成：

```python
if not (model := os.environ.get("MODEL_ID")):
    raise ConfigError("缺少环境变量: MODEL_ID")
```

> `:=` 是 walrus operator（海象运算符），赋值即判断。

## 与 nanobot 的对比

nanobot 用 Pydantic + pydantic-settings 做配置：

```python
class Config(BaseSettings):
    api_key: str = Field(validation_alias="ANTHROPIC_API_KEY")
```

Pydantic 能自动从环境变量读取、做类型转换、嵌套验证。但 learn-cc 目前只有 5 个配置项，引入 pydantic 太重了。**为小需求选合适的工具，而不是为工具选需求。"**

等配置复杂到十几个字段、嵌套结构时，再升级到 Pydantic 不迟。

## 本次变更

### 新增文件

| 文件 | 作用 |
|------|------|
| `src/learn_cc/config.py` | Config dataclass + 加载函数 + 异常类 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `src/learn_cc/__main__.py` | 调用 `Config.load()` 替代散落的全局变量 |

### 未变更

`code.py` 保留为参考，不做任何修改。

---

## 决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 配置容器 | frozen dataclass | 轻量、不可变、类型安全 |
| 加载方式 | classmethod `Config.load()` | 显式优于隐式，方便 mock |
| 环境变量前缀 | 无（保持原名） | 与原始项目兼容 |
| 配置验证 | 手动校验 + ConfigError | 体量小，不需要 Pydantic |
| 工具函数 | 暂不改参数 | Step 3 提取 Tools 时一起处理 |

---

## 下一步

Step 3 将提取 **Tools 包** —— 把 `run_bash`、`run_read`、`run_write`、`run_edit`、`run_glob` 拆成独立的模块，放到 `learn_cc/tools/` 下。
