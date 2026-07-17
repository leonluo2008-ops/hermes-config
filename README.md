# hermes-config

Hermes Agent 配置管理套件 — 2 个配套 skill，规范 SOUL.md / .hermes.md / MEMORY.md 三层配置架构。

## 包含

| Skill | 用途 |
|---|---|
| `hermes-config-organization` | 三层配置架构规范——什么内容放哪个文件、搜索/优先级/遮蔽机制、变更检查清单 |
| `hermes-md-init` | 项目级 `.hermes.md` 人工策展式初始化——采集非显然信息 → 选骨架逐段填充 → 强制继承全局规则（Step 3.5）→ 写入读回验证。含确定性自动触发机制 |

两个 skill 配合使用：`hermes-config-organization` 定义"应该怎样"，`hermes-md-init` 执行"具体怎么做"。

## 通用性说明（先读这个）

这两个 skill 遵循 [agentskills.io](https://agentskills.io) 开放标准（`SKILL.md` = YAML frontmatter + Markdown），**可以安装并加载进任何支持该标准的系统**：Claude Code、OpenClaw、Cursor、Trae、Hermes 等。安装方式见下，唯一差别是各家 skills 目录不同。

但请区分两层"通用"：

- **打包 / 安装通用** ✅ — 标准 SKILL.md，装哪儿都能被识别加载。
- **内容适用范围** — 这两个 skill 的*知识本身*是讲 **Hermes 的配置文件**（SOUL.md / .hermes.md / MEMORY.md 是 Hermes 专有概念）。装进 Claude Code 等系统也能加载，但只有当你用该系统**管理一个 Hermes 实例**时才真正有用；它不会自动变成"通用配置规范"。

## 安装

### 1. 获取仓库

```bash
git clone https://github.com/leonluo2008-ops/hermes-config.git
cd hermes-config
```

（或下载 zip 解压后进入该目录。）

### 2. 复制到你所用 agent 的 skills 目录

把 `hermes-config-organization/` 和 `hermes-md-init/` 两个目录整体复制过去。各系统位置：

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

- **v2** (2026-07-17): hermes-md-init 重写为人工策展式；Step 3.5 继承清单补充"关键原则"；加确定性自动触发机制（`~/.hermes.md` 项目自检行）；模板拆分到 `templates/` 目录
- **v1** (2026-07-12): 初始发布 — hermes-config-organization + hermes-md-init
