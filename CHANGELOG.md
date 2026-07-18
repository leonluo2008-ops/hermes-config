# Changelog

本项目的所有重要变更记录。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

本项目有两套独立版本号：
- **skill 版本**（v1/v2/v3/v4...）：对应 `hermes-config-organization` + `hermes-md-init` 两个 skill 的内容演进，tag 形式 `v4.0`
- **config-advisor plugin 版本**（0.1.x）：对应 `config-advisor/plugin.yaml` 的 version 字段

---

## [Unreleased]

### Removed
- `references/local-to-github-sync.md`：描述的"运行目录→镜像仓库"三段式同步模式与项目实际不符（项目是 promotion 模式：仓库→运行目录），同步清除 SKILL.md L290-292 的悬空引用段

### Added
- `.hermes.md` 项目级指令文件（人工策展式初始化，含开发铁律/版本维护/登记清单）
- `CHANGELOG.md` 本文件
- `config-advisor/requirements.txt`（httpx 依赖声明，运行时由 hermes venv 提供）

### Changed
- `install.sh`：删除 config-advisor 未发布的 dead code 判断；echo 出的 Python 启用脚本改用 `os.path.expanduser` 通用化路径；删除误导性注释
- `config-advisor/plugin.yaml`：version 0.1.0 → 0.1.1（追平 GUIDE.md L3）

### Fixed
- 通用性整改：清除仓库内 17 处本机硬编码路径
  - README.md 3 处 `~/Github/` → `<your-repo-dir>/`
  - GUIDE.md 5 处 `/home/luo/` + `~/Github/` → `~/.hermes/` / `os.path.expanduser` / `<your-repo-dir>`
  - local-to-github-sync.md 7 处 `~/Github/` → `<your-repo-dir>/`
  - SKILL.md 2 处 `/home/luo/` → `os.path.expanduser('~/.hermes.md')`（保语义不删段）

---

## [skill v4.0] - 2026-07-18

### Added
- `.hermes.md` 项目级指令（通用性铁律 / 版本维护规则 / 登记清单 / 新机器初始化 6 步）
- `CHANGELOG.md` 版本维护基建
- `config-advisor/requirements.txt` 依赖声明
- `config-advisor/docs/GUIDE.md` 保姆级开发与使用文档（13 章节，616 行）

### Changed
- `install.sh` 通用化（删 dead code、修 $HOME 展开问题、echo 脚本改 expanduser）
- `README.md` 加"开发调试流程"段（双段式开发约定）

### Fixed
- `health_check.py` 字节口径 → 字符口径（`stat().st_size` → `len(read_text())`，中文 UTF-8 虚高 1.9 倍）
- 17 处本机硬编码路径清理（见 Unreleased.Fixed 详列）

---

## [config-advisor plugin 0.1.1] - 2026-07-18

### Fixed
- `health_check.py` 的 `_file_size` 函数从字节计数改为字符计数，修复中文内容虚高误报
- 版本号追平 GUIDE.md 文档（GUIDE.md L3 已写 v0.1.1）

---

## [skill v3] - 2026-07-17

### Added
- `hermes-config-organization` 新增"配置协作协议"——信息路由决策树、配置自检协议（7 项确定性检查）、项目工作流复盘（3 种触发方式）
- 3 个新 references 文件
- `install.sh` 一键安装脚本

*(注：v1/v2/v3 为事后回溯，依据 git log + README L129 变更日志段，可能不完整)*

---

## [config-advisor plugin 0.1.0] - 2026-07-17

### Added
- config-advisor plugin 初始发布
- 三层 hook 架构：pre_llm_call（首轮健康检查）+ post_tool_call（信息路由建议）+ on_session_finalize（异步复盘报告）
- observer-only 设计，与 harness-guard 互补共存

---

## [skill v2] - 2026-07-17

### Changed
- `hermes-md-init` 重写为人工策展式（不再自动生成）
- Step 3.5 继承清单补充"关键原则"
- 加确定性自动触发机制（`~/.hermes.md` 项目自检行）
- 模板拆分到 `templates/` 目录

---

## [skill v1] - 2026-07-12

### Added
- 初始发布
- `hermes-config-organization` + `hermes-md-init` 两个 skill
