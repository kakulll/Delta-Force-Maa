# Agent Guidelines

## Git Commit 规范

每次完成重要的代码修改并验证通过后：
1. **自主执行 `git commit`**：无需额外询问，完成修改验证后直接执行 `git commit`，并在回复中简要汇报提交哈希与信息。
2. **提交信息规范**：严格遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范，格式如下：
   - `feat: <新功能描述>`：新增功能或能力
   - `fix: <修复描述>`：修复缺陷或 bug
   - `docs: <文档描述>`：文档变动
   - `style: <样式描述>`：代码格式调整，不影响逻辑
   - `refactor: <重构描述>`：重构代码（既非修复 bug 也非添加功能）
   - `perf: <性能描述>`：性能优化
   - `test: <测试描述>`：添加或调整测试
   - `chore: <构建或辅助工具变动>`：依赖更新、配置调整等
3. 提交信息应简明扼要，说明修改的背景与主要内容。
