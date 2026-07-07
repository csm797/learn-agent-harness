"""
learn_cc — 从零学习 Claude Code 核心机制。

本项目是开源教学项目 learn-claude-code 的模块化重构版本。
原始项目通过 s01~s20 逐步从单文件构建一个简易 Agent Harness。
本重构版将其拆分为标准 Python 包结构，目的是学习：

  1. 模块化编程 —— 关注点分离、包组织
  2. 测试驱动 —— pytest、mock、覆盖率
  3. 工程规范 —— pyproject.toml、lint、CI
  4. 文档思维 —— 每个决策都有记录

原始教学项目位于: ../learn-claude-code-main/
"""

__version__ = "0.1.0"
