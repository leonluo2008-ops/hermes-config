# hermes-config

Hermes Agent 配置管理套件 — 2 个配套 skill，规范 SOUL.md / .hermes.md / MEMORY.md 三层配置架构。

## 包含

| Skill | 用途 |
|---|---|
| `hermes-config-organization` | 三层配置架构规范 + **配置协作协议**（自检/路由/复盘）——什么内容放哪个文件、搜索/优先级/遮蔽机制、变更检查清单、信息路由决策树 |
| `hermes-md-init` | 项目级 `.hermes.md` 人工策展式初始化——采集非显然信息 → 选骨架逐段填充 → 强制继承全局规则（Step 3.5）→ 写入读回验证。含确定性自动触发机制 |

两个 skill 配合使用：`hermes-config-organization` 定义"应该怎样"，`hermes-md-init` 执行"具体怎么做"。

**配套插件**：`config-advisor` 自动执行配置自检、信息路由建议和会话复盘。通过 `./install.sh --plugins` 安装。

## 开发调试流程（重要）

> 本仓库**不是运行目录**，是开发仓库。`install.sh` 用 `cp -r` 把文件**复制**到运行目录（`install.sh:25,46`），不是软链。两边是独立副本。

| 角色 | 路径 | 说明 |
|------|------|------|
| **开发仓库**（改代码的地方） | `<your-repo-dir>/hermes-config/` | git repo，remote = `leonluo2008-ops/hermes-config`（`git remote -v` 验证）|
| **运行目录**（Hermes 实际加载） | `~/.hermes/skills/*` + `~/.hermes/plugins/config-advisor` | `install.sh` 复制过去的 |
| **安装方式** | `install.sh` 用 `cp -r`（L25, L46） | 复制，非软链 |

**正确流程**（三步，缺一不可）：
1. 在 `<your-repo-dir>/hermes-config/` 改代码 → `git commit && git push`
2. `./install.sh` 或 `cp -r config-advisor/ ~/.hermes/plugins/`（skill 同理）同步到运行目录
3. 外部终端 `hermes gateway restart` 才生效（`hermes gateway --help` 确认 restart 子命令存在）

**⚠️ 坑**：直接改 `~/.hermes/plugins/config-advisor/` 的文件，仓库不会变——下次 `install.sh` 或 `git pull` 会覆盖你的改动。**改代码永远在仓库**。

**验证两边一致**：
```bash
diff <your-repo-dir>/hermes-config/config-advisor/health_check.py ~/.hermes/plugins/config-advisor/health_check.py
# 无输出 = 一致
```

> 对比：`harness-guard` 插件是"运行目录=开发目录=git repo"的单段式模式（`~/.hermes/plugins/harness-guard/` 自己就是 git repo，remote 指向 `hermes-plugin-harness-guard`）。本仓库不同，是双段式。

## 通用性说明（先读这个）

这两个 skill 遵循 [agentskills.io](https://agentskills.io) 开放标准（`SKILL.md` = YAML frontmatter + Markdown），**可以安装并加载进任何支持该标准的系统**：Claude Code、OpenClaw、Cursor、Trae、Hermes 等。安装方式见下，唯一差别是各家 skills 目录不同。

但请区分两层"通用"：

- **打包 / 安装通用** ✅ — 标准 SKILL.md，装哪儿都能被识别加载。
- **内容适用范围** — 这两个 skill 的*知识本身*是讲 **Hermes 的配置文件**（SOUL.md / .hermes.md / MEMORY.md 是 Hermes 专有概念）。装进 Claude Code 等系统也能加载，但只有当你用该系统**管理一个 Hermes 实例**时才真正有用；它不会自动变成"通用配置规范"。

## 安装

### 一键安装（推荐）

```bash
git clone https://github.com/leonluo2008-ops/hermes-config.git
cd hermes-config

# 只安装 skills
./install.sh

# 同时安装 config-advisor 插件（仅 Hermes，需 --plugins 显式 opt-in）
./install.sh --plugins
```

### 手动安装

把 `hermes-config-organization/` 和 `hermes-md-init/` 两个目录整体复制到你的 skills 目录：

| 系统 | 全局 skills 目录 | 项目级 skills 目录 |
|---|---|---|
| Hermes | `~/.hermes/skills/` | — |
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| OpenClaw | `~/.openclaw/skills/`（`--global`）| `.openclaw/skills/` |
| Cursor | `~/.cursor/skills/` | — |
| Trae | 通过 Trae 的 Skills 界面导入 | 以 Trae 文档为准 |

通用命令（把 `SKILLS_DIR` 换成上表你系统对应的目录）：

```bash
SKILLS_DIR="$HOME/.claude/skills"   # ← 改成你的系统对应目录
mkdir -p "$SKILLS_DIR"
cp -r hermes-config-organization hermes-md-init "$SKILLS_DIR"/
```

> Windows：`$HOME` 即 `%USERPROFILE%`；用 PowerShell 的 `Copy-Item -Recurse` 代替 `cp -r`。
> 也可用软链接代替复制（`ln -s`），按个人习惯；OpenClaw 对 config 软链有限制，skills 目录一般不受影响。

### 3. 验证

```bash
ls "$SKILLS_DIR"/hermes-config-organization/SKILL.md
ls "$SKILLS_DIR"/hermes-md-init/SKILL.md
```

新开一个会话，agent 即会按需加载。

## 升级

```bash
cd hermes-config && git pull
cp -r hermes-config-organization hermes-md-init "$SKILLS_DIR"/
```

## 前置要求

- 一个支持 agentskills.io 标准 SKILL.md 的 agent 系统（Claude Code / OpenClaw / Cursor / Trae / Hermes…）。
- 若用于管理 Hermes：建议全局 `~/.hermes.md` 已建立（见 `hermes-config-organization` 的全局配置段）。

## 背景

Hermes 的 system prompt 分三层注入：

```
stable 层   SOUL.md          身份/语气/风格（HERMES_HOME，每次会话）
context 层  .hermes.md       项目指令/工作流（CWD 搜索，first match wins）
volatile 层 MEMORY.md/USER.md 会话级动态数据
```

官方文档明确 SOUL.md 不应放 workflow 指令，但很多用户（包括本项目作者）把 workflow 塞进了 SOUL.md。这套 skill 就是解决这个问题的。

## 最佳实践对齐

本套 skill 已对齐以下权威来源（详见 `hermes-config-organization` 文末"参考来源"）：

- **Hermes 官方 skill 写作规范** — 精简 description、信息分层、每步给完成判据、一行不改行为就删。
- **AGENTS.md 实证研究**（ETH Zurich / Philschmid / agents.md） — 自动生成 context 文件反而降低成功率，故 `hermes-md-init` 采用"人工策展"而非"自动 /init"；不写 agent 能自己推断的目录树、代码风格、manifest 技术栈。
- **官方 Context Files 行为校准** — `.hermes.md` 走 git root、`AGENTS.md` 启动仅读 CWD（issue #21686）、MEMORY 超限报错而非静默截断等事实均已核实。

## 变更日志

- **v3** (2026-07-17): hermes-config-organization 新增"配置协作协议"——信息路由决策树（正文精简版 + 完整 reference）、配置自检协议（7 项确定性检查）、项目工作流复盘（3 种触发方式）；3 个新 references 文件；install.sh 一键安装脚本
- **v2** (2026-07-17): hermes-md-init 重写为人工策展式；Step 3.5 继承清单补充"关键原则"；加确定性自动触发机制（`~/.hermes.md` 项目自检行）；模板拆分到 `templates/` 目录
- **v1** (2026-07-12): 初始发布 — hermes-config-organization + hermes-md-init
