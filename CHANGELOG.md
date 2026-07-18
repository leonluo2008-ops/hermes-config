# Changelog

本项目的所有重要变更记录。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

本项目有两套独立版本号：
- **skill 版本**（v1/v2/v3/v4...）：对应 `hermes-config-organization` + `hermes-md-init` 两个 skill 的内容演进，tag 形式 `v4.0`
- **config-advisor plugin 版本**（0.1.x）：对应 `config-advisor/plugin.yaml` 的 version 字段

---

## [Unreleased]

（下次发布的内容将在此累积）

---

## [skill v4.0] - 2026-07-18

本次发布是项目初始化整改：通用化、版本维护基建、配置完整性核查、本地→GitHub 同步模式修正。

### Added
- `.hermes.md` 项目级指令文件（人工策展式初始化，含开发铁律/版本维护规则/登记清单/新机器初始化 6 步）
- `CHANGELOG.md` 版本维护基建（Keep a Changelog 格式，skill + plugin 双 section）
- `config-advisor/requirements.txt`（httpx 依赖声明，运行时由 hermes venv 提供）
- `config-advisor/docs/GUIDE.md` 保姆级开发与使用文档（13 章节，616 行）
- `scripts/verify-integration.sh` 集成验证脚本（46 项检查：L1 静态 + L2 单元 + L3 集成）

### Changed
- `install.sh`：删除 config-advisor 未发布的 dead code 判断；echo 出的 Python 启用脚本改用 `os.path.expanduser` 通用化路径；删除误导性注释；L58 `$HOME` 在双引号 echo 里会展开成绝对路径，改为不展开的字面提示
- `config-advisor/plugin.yaml`：version 0.1.0 → 0.1.1（追平 GUIDE.md L3，patch：仅文档/版本号对齐无 hook 逻辑变化）
- `README.md`：清除 3 处 `~/Github/` 硬编码；合并前置要求段（httpx + Python 3.11+ + agentskills.io 标准）
- `GUIDE.md`：清除 5 处硬编码路径；L4 配套 skill 版本号 `v3+` → `v4+`；§5 前置条件改 `pip install httpx` → "Hermes venv 已提供"
- `SKILL.md`：L217-219 harness-guard workaround 可执行片段 `/home/luo/` → `os.path.expanduser('~/.hermes.md')`（terminal python3 -c 不展开 ~）

### Fixed
- 通用性整改：清除仓库内 17 处本机硬编码路径（README 3 + GUIDE 5 + local-to-github-sync 7 + SKILL 2）
- `.env.example` 完整性核查：代码实际读取 11 个 env 变量（grep `os.environ.get` + `os.getenv` 实测），补 5 个缺失字段（HERMES_HOME + 4 个 fallback API key）

### Removed
- `references/local-to-github-sync.md`：描述的"运行目录→镜像仓库"三段式同步模式与项目实际不符（项目是 promotion 模式：仓库→运行目录），同步清除 SKILL.md L290-292 的悬空引用段

### Known Issues（本次不修，单独 issue 跟踪）
- `SOUL.md` 2044 字符超 2000 上限（workflow 段应移到 .hermes.md）
- `MEMORY.md` 2173/2200（98%）接近上限
- `USER.md` 1242/1375（90%）接近上限
- 这三项是配置内容问题不是代码问题，合并到 main 不会让它们变差，但 config-advisor 的 `pre_llm_call` hook 会在每次新会话注入这个警告

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
