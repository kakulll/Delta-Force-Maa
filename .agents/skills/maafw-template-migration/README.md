# MaaFW Template Migration

MaaFramework 老项目迁移到 create-maa-project 脚手架的指南 skill。

## 用途

当需要把一个旧的 MaaFW 项目（`assets/` + `deps/` 结构、`install*.py` 打包脚本）迁移到 CMP 模板（`maa-project.json` + `build-release.mjs` + `sync-runtime.mjs`）时使用。

## 内容

- `SKILL.md`: 迁移指南正文，包含结构映射、迁移步骤、常见坑
- `maahub_meta.json`: MaaHub 网站元信息

## 适用场景

- 老项目从 assets/deps 结构迁移到 CMP 模板
- 需要了解新旧目录结构的对应关系
- 迁移过程中遇到 ocr.files 配置、logo.ico、macOS bash 兼容等问题时参考
