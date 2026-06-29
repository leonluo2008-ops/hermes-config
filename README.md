# hermes-config

Hermes Agent 配置管理套件 — 2 个配套 skill，规范 SOUL.md / .hermes.md / MEMORY.md 三层配置架构。

## 包含

| Skill | 用途 |
|---|---|
| `hermes-config-organization` | 三层配置架构规范——什么内容放哪个文件、搜索/优先级/遮蔽机制、变更检查清单 |
| `hermes-md-init` | 项目级 `.hermes.md` 人工策展式初始化——采集非显然信息 → 选骨架（`templates/`）→ 继承全局规则 → 写入验证 |

两个 skill 配合使用：`hermes-config-organization` 定义"应该怎样"，`hermes-md-init` 执行"具体怎么做"。

## 安装

```bash
git clone https://github.com/leonluo2008-ops/hermes-config.git /tmp/hermes-config

# 复制到 Hermes skills 目录（不用软链——用户偏好实体副本）
cp -r /tmp/hermes-config/hermes-config-organization ~/.hermes/skills/software-development/
cp -r /tmp/hermes-config/hermes-md-init ~/.hermes/skills/software-development/

# 验证
ls ~/.hermes/skills/software-development/hermes-config-organization/SKILL.md
ls ~/.hermes/skills/software-development/hermes-md-init/SKILL.md
```

## 升级

```bash
cd /tmp/hermes-config && git pull
cp -r /tmp/hermes-config/hermes-config-organization ~/.hermes/skills/software-development/
cp -r /tmp/hermes-config/hermes-md-init ~/.hermes/skills/software-development/
```

## 前置要求

- Hermes Agent（由 [Nous Research](https://github.com/nousresearch/hermes-agent) 开发）
- 全局 `~/.hermes.md` 已建立（见 `hermes-config-organization` skill 的全局配置段）

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
