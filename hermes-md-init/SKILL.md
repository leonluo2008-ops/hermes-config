---
name: hermes-md-init
description: |
  为项目初始化 .hermes.md 配置文件——Hermes 版的 /init。当用户说"新项目""初始化项目""建个 .hermes.md""这个项目还没有 .hermes.md""init 项目"时触发。也当 agent 检测到当前工作目录缺少 .hermes.md 时主动加载此 skill。
  触发词：新项目、初始化项目、建个hermes.md、init项目、项目配置、.hermes.md、AGENTS.md、项目规范文件
---

# .hermes.md 项目初始化

## 什么是 .hermes.md

`.hermes.md` 是 Hermes 的**项目级指令文件**，注入 system prompt 的 context 层。它告诉 agent 这个项目的架构、规范、约束。

**搜索规则**：从 CWD 向上搜索到 git root，就近命中。`~/.hermes.md` 是全局兜底。项目级 `.hermes.md` 遮蔽全局的。

**优先级**：`.hermes.md` > `AGENTS.md` > `CLAUDE.md` > `.cursorrules`（first match wins）

**截断上限**：20,000 字符（超了保留头部 70% + 尾部 20%，中间砍掉）。

## 什么时候需要建

### 必须建

- 新建项目目录（git init 后第一件事）
- 现有项目但没有 `.hermes.md`，且需要 agent 遵守项目特定规范

### 不需要建

- 项目跟其他项目用同样的规范（全局 `~/.hermes.md` 够用）
- 临时目录 / 一次性脚本

## 初始化流程

### Step 1：确认项目路径

```
问用户：这个项目在哪个目录？
（如果是飞书对话，用户可能只说项目名，用 search_files 或 find 在 ~/ 下搜索确认路径）
```

### Step 2：扫描项目结构

用 terminal 扫描项目目录，了解：
- 项目类型（web/CLI/library/MCP server/数据 pipeline）
- 语言和框架（package.json / pyproject.toml / go.mod / Cargo.toml）
- 目录结构
- 现有的 lint/format/test 配置
- 现有的 README

### Step 3：按模板生成

根据项目类型选择对应模板（见下方"模板"段），填充扫描到的信息。

### Step 3.5：继承全局关键规则（必做）

**这一步不可跳过。** 项目级 `.hermes.md` 一旦建立，`~/.hermes.md` 会被完全遮蔽——所有全局规则在项目目录下不再生效。

操作：
1. 读取 `~/.hermes.md`
2. 以下规则段**必须**在项目级 `.hermes.md` 中保留（摘要引用或完整搬运）：
   - **Hindsight 记忆协议** — 至少保留 retain infra_state 的触发条件和格式
   - **工作流程路由** — 如果项目可能触发跨 agent 协作（如内容创作→huiben）
3. 以下规则段**可选**保留（看项目是否相关）：
   - 基础设施维护职责
   - 情报采集职责
4. 如果项目有独立 AGENTS.md，也要把 AGENTS.md 的关键约束搬进 `.hermes.md`（因为 `.hermes.md` 一旦建立，AGENTS.md 不会被加载）
5. **写入后读回文件，验证以下段落存在**：☐ Hindsight retain infra_state 触发条件和格式 ☐ 工作流程路由（如适用）。缺失则补写。

写入 `{project_root}/.hermes.md`，告诉用户文件已创建，列出关键内容。

## 模板

### 通用结构

每个 `.hermes.md` 都应该有这几个段，按需填充：

```markdown
# {项目名}

> 一句话描述这个项目是什么。

## 技术栈

- 语言：{Python 3.11 / TypeScript / ...}
- 框架：{FastAPI / Next.js / ...}
- 包管理：{uv / npm / pnpm / ...}
- 测试：{pytest / vitest / ...}

## 目录结构

{关键目录的简短说明，不展开到每个文件}

## 开发规范

- {代码风格 / lint 规则}
- {commit 规范}
- {分支规范}

## 关键约束

- {不能改的东西}
- {必须注意的坑}
- {安全相关约束}

## 常用命令

- 构建：`{command}`
- 测试：`{command}`
- 部署：`{command}`
```

### Web 应用项目

额外加：
```markdown
## 端口
- 前端：{port}
- 后端：{port}
- 数据库：{port}

## 环境变量
- {关键变量名和用途，不放实际值}
```

### MCP Server 项目

额外加：
```markdown
## 角色
{列出所有 agent 角色及其职责}

## 模型
- {哪个角色用哪个模型/provider}

## 运行
- 开发路径：{dev path}
- 运行路径：{deploy path}
- 启动命令：`{command}`
```

### 数据/内容创作项目

额外加：
```markdown
## 内容规范
- 目标受众：{受众}
- 风格要求：{风格}
- 输出格式：{格式}

## 工作流
{创作步骤的简短描述}
```

## 写什么 vs 不写什么

### 写

- 项目架构（目录结构、技术栈）
- 编码规范（风格、lint、commit）
- 关键约束（不能改的、已知的坑）
- 常用命令（构建、测试、部署）
- 项目特有的工作流

### 不写

- 身份/语气/风格（→ SOUL.md）
- 通用工作规范（→ `~/.hermes.md`）
- 临时 TODO
- 敏感信息（密钥、密码、token）

## 坑

1. **不要写太长** — 20,000 字符上限，但实际超过 5,000 字符就该考虑精简。中间内容会被截断丢弃。
2. **不要复制全局规范** — `~/.hermes.md` 已有的规则不要重复写。（但注意：项目级会遮蔽全局，关键规则必须继承，见 Step 3.5）
3. **不要写"be helpful"之类的废话** — agent 默认就会做。
4. **YAML frontmatter 会被剥离** — 如果用 `---` 分隔的 frontmatter，内容会被丢弃。直接写 markdown body。
5. **项目级遮蔽全局** — 一旦建了项目级 `.hermes.md`，全局的就不会被加载。必须走 Step 3.5 继承检查。
6. **AGENTS.md 也会被遮蔽** — `.hermes.md` 优先级高于 AGENTS.md，first match wins。如果项目已有 AGENTS.md，建 `.hermes.md` 时要把 AGENTS.md 的关键约束搬过来。
7. **git submodule 独立搜索** — submodule 有自己的 `.git`，搜索会在 submodule 根停止，不会走到父仓库。每个 submodule 需要独立的 `.hermes.md`。
8. **git root 截断不回退** — 如果 CWD 在 git 仓库内且项目没有 `.hermes.md`，搜索在 git root 停止，**不会回退到 `~/.hermes.md`**。这是 Step 3.5 存在的原因。
