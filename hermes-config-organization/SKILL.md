---
name: hermes-config-organization
description: |
  Hermes Agent 配置三层架构规范——什么内容放 SOUL.md、什么放 .hermes.md、什么放 MEMORY.md，以及搜索规则、遮蔽机制、变更检查清单。
  当用户问"这个规则放哪里""SOUL.md 该写什么"".hermes.md 和 AGENTS.md 区别""配置怎么组织""SOUL.md 太长了""workflow 该放哪"时触发。
  也当 agent 需要修改 SOUL.md 或 .hermes.md 时主动加载，确认改动符合分层规范。
  触发词：SOUL.md 写什么、配置组织、配置分层、hermes-config-organization、workflow 放哪、SOUL.md 滥用、配置最佳实践、.hermes.md 搜索规则、遮蔽机制
---

# Hermes 配置三层架构

## 三层定义

| 层 | 文件 | 位置 | 注入时机 | 写什么 |
|---|---|---|---|---|
| **stable** | `SOUL.md` | `HERMES_HOME/SOUL.md` | 每次会话 slot #1 | 身份、语气、风格、铁律 |
| **context** | `.hermes.md` | CWD 向上搜索到 git root | 会话启动时 | 项目指令、工作流、架构、规范 |
| **volatile** | `MEMORY.md` / `USER.md` | HERMES_HOME 内部管理 | 每轮动态注入 | 会话级事实、用户偏好 |

### SOUL.md（stable 层）

**官方定位**（来自 hermes-agent.nousresearch.com/docs）：

> SOUL.md is about who Hermes is and how Hermes speaks.

**写什么：**
- 身份声明（你是谁、做什么）
- 语气和沟通风格（短答/长答、直接/委婉）
- 硬性铁律（跨所有项目、跨所有会话必须遵守的规则）
- 行为默认值（不确定时怎么做）

**不写：**
- 项目架构、目录结构、端口、路径
- 具体工作流程（步骤 1 → 步骤 2 → ...）
- 基础设施操作规范（Docker/systemd/cron 细节）
- Hindsight/API 调用代码示例

**判断标准：** 如果一条规则只在你"工作中枢"角色下生效，不管哪个项目，不管什么任务 → SOUL.md。如果只对某个项目或某类操作生效 → `.hermes.md`。

**字数建议：** < 2,000 字符。SOUL.md 越短，身份锚定越强。超过 2,000 字符说明你在往里塞 workflow。

### .hermes.md（context 层）

**官方定位：**

> Use for: project architecture, coding conventions, tool preferences, repo-specific workflows, commands, ports, paths, deployment notes.

**写什么：**
- 核心使命和职责描述
- 工作流程路由（什么任务自己处理、什么转发）
- 操作规范（Hindsight retain/recall 协议、对抗审查流程）
- 基础设施维护职责
- 项目级编码规范、架构说明

**不写：**
- 身份和语气（→ SOUL.md）
- 会话级动态数据（→ MEMORY.md）

**搜索规则（关键）：**

1. Hermes 从 CWD 开始向上搜索 `.hermes.md` 或 `HERMES.md`
2. 遇到 git root（含 `.git` 的目录）停止搜索
3. 如果 CWD 不在 git 仓库内，一直走到文件系统根 `/`
4. **first match wins**——找到第一个就返回，不继续向上找
5. 优先级：`.hermes.md` > `AGENTS.md` > `CLAUDE.md` > `.cursorrules`（只加载一种）

**遮蔽机制（关键）：**

- 项目级 `.hermes.md` 一旦存在，**完全遮蔽** `~/.hermes.md`——全局规则在项目目录下不可见
- `.hermes.md` 一旦存在，也**完全遮蔽** `AGENTS.md`——两者不会同时加载
- git root 是硬停止点：CWD 在 git 项目内且项目没有 `.hermes.md` 时，搜索在 git root 停止，**不会回退到** `~/.hermes.md`

**截断上限：** 20,000 字符。超了保留头部 70% + 尾部 20%，中间 10% 被丢弃。建议控制在 6,000 字符以内。

### MEMORY.md / USER.md（volatile 层）

**写什么：**
- 用户偏好和习惯（会话级注入，每轮都能看到）
- 环境事实（OS、工具路径、版本）
- 纠错记录（用户纠正过的行为）

**不写：**
- 可从文件推断的环境信息
- 7 天后会过期的临时状态（任务进度、PR 编号、commit SHA）

**字数限制：** ~2,200 字符。超过会被截断。

## 全局 vs 项目级 .hermes.md

### 推荐架构

```
~/.hermes.md                    ← 全局兜底（跨项目生效的工作流）
~/Github/some-project/
  └── .hermes.md                ← 项目级（遮蔽全局）
```

### 什么时候用全局

- 你有一个"工作中枢"角色，其工作流跨所有项目（调度、运维、Hindsight 协议）
- 大部分会话的 CWD 是 `~/`（飞书对话、消息平台场景）

### 什么时候建项目级

- 项目有独立的编码规范、架构、技术栈
- 项目有独立 AGENTS.md 需要迁移（`.hermes.md` 优先级更高）
- 项目工作目录在 git 仓库内（全局 `.hermes.md` 搜不到）

**建项目级时必须走 `hermes-md-init` skill 的继承检查（Step 3.5）**，否则全局规则会静默丢失。

## 变更检查清单

### 改 SOUL.md 前问自己

1. **这是身份/风格，还是 workflow？** → workflow 移到 `.hermes.md`
2. **这条规则跨所有项目生效吗？** → 不跨项目的移到项目级 `.hermes.md`
3. **SOUL.md 总字数是否超过 2,000？** → 超了就精简，把 workflow 搬走
4. **有没有写具体路径/端口/命令？** → 移到 `.hermes.md` 或 skill

### 改 .hermes.md 前问自己

1. **这是项目级规则，还是全局的？** → 全局规则放 `~/.hermes.md`
2. **总字数是否接近 6,000？** → 超了考虑拆到 skill 或 reference 文件
3. **如果这是项目级改动，全局规则有没有被遮蔽？** → 走 `hermes-md-init` Step 3.5 继承检查

### 改 MEMORY.md 前问自己

1. **这条事实 7 天后还有用吗？** → 没用就别放（用 session_search 回忆临时状态）
2. **这是声明性事实，还是指令？** → 指令放 SOUL.md 或 skill，MEMORY 只放事实

## 常见错误

1. **SOUL.md 塞满 workflow** — 最常见的错误。SOUL.md 不是"agent 的所有规则"，只是身份层。
2. **项目级 `.hermes.md` 不继承全局** — 建了项目级就忘了搬全局的关键规则。
3. **以为 `.hermes.md` 会回退到 `~/`** — 不会。git root 是硬墙。
4. **MEMORY.md 写指令** — "运行测试用 pytest -n 4"是指令不是事实，应该写进 `.hermes.md` 或 skill。
5. **SOUL.md 写具体路径** — `/home/luo/.hermes/scripts/` 这种路径放 skill 或 `.hermes.md`，不放心层。
