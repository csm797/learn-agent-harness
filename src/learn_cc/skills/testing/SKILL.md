---
name: testing
description: 项目测试框架使用指南 —— pytest 配置、运行、测试编写规范
---

# Testing Skill

## 测试框架

本项目使用 **pytest** 作为测试框架。

## 运行测试

```bash
# 运行全部测试
pytest tests/ -v

# 运行单个测试文件
pytest tests/test_hooks.py -v

# 运行单个测试
pytest tests/test_hooks.py::TestHookRegistry::test_register_and_dispatch -v

# 带覆盖率
pytest tests/ --cov=src/learn_cc --cov-report=term-missing
```

## 测试编写规范

1. 测试文件放在 `tests/` 目录，文件名 `test_*.py`
2. 测试函数名 `def test_*():`
3. 每个测试只测一个行为
4. 使用 `monkeypatch` 模拟环境变量
5. 使用 `tmp_path` 处理临时文件
6. 命名遵循 AAA 模式（Arrange-Act-Assert）
