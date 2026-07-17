---
name: hermes-md-init
description: |
  人工策展式初始化项目级 .hermes.md（Hermes 版 /init，但由人确认每段内容）。流程：确认路径 → 采集非显然信息 → 选骨架并逐段填充 → 强制继承全局规则（Step 3.5）→ 写入读回验证。
  当用户说"新项目""初始化项目""建个 .hermes.md""这个项目还没有 .hermes.md"，或 agent 检测到 CWD 缺少 .hermes.md 时加载。
---

# .hermes.md 项目初始化

> **理念（重要）**：本 skill 是**人工策展助手**，不是"扫一扫自动生成"。实证研究显示让 agent 自动生成 context 文件反而降低任务成功率、推高成本（依据见 `hermes-config-organization` 文末"参考来源"）。所以流程是：agent 提问 + 给精简骨架 + 强制继承检查，**每段内容由用户确认**；只写 agent 推断不出来的关键信息，能交给 linter / 从 manifest 读出的就别写。

## 什么是 .hermes.md

`.hermes.md` 是 Hermes 的**项目级指令文件**，注入 system prompt 的 context 层。它告诉 agent 这个项目的关键约束、非显然命令、特有工作流。

**搜索规则**：从 CWD 向上搜索到 git root，就近命中。`~/.hermes.md` 是全局兜底（注：非官方命名特性，仅在 CWD 不在任何 git 仓库内时才会命中，详见 `hermes-config-organization`）。项目级 `.hermes.md` 遮蔽全局。

**优先级**：`.hermes.md` > `AGENTS.md` > `CLAUDE.md` > `.cursorrules`（first match wins）。注意只有 `.hermes.md` 走到 git root；`AGENTS.md` 启动时仅读 CWD。

**截断上限**：20,000 字符（超了保留头部 70% + 尾部 20%，中间砍掉）。

## 什么时候需要建

### 自动触发（v2 新增）

`~/.hermes.md` 顶部前提条件注释中已加入"项目自检"行：**会话开头如果 CWD 在 git 仓库内，先检查 git root 是否有 `.hermes.md`，没有则走本 skill 先建再干活。** 这是确定性文件存在性检查（`test -f`），幂等无状态——有 → 跳过，无 → 建。不依赖"首次"概念（跨会话无法可靠记忆"已建过了"）。

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

**完成判据**：拿到项目根目录的确切绝对路径，并确认它是否为 git 仓库根（决定 `.hermes.md` 的作用域与是否会遮蔽全局）。

### Step 2：采集非显然信息（不要全量复制）

只采集 **agent 自己推断不出来** 的东西，**不要**把目录树、代码风格、manifest 里的技术栈复制进来——那些 agent 会自己探、或交给 linter。重点问/查：
- 有没有"不能改/改了会出事"的地方？
- 有没有已知的坑、非默认端口、非显然的构建/部署命令？
- 有没有这个项目独有的工作流或安全约束？

**完成判据**：能回答"这个项目有哪些非显然约束/坑/特殊命令"，而不是"复述了一遍目录结构"。

### Step 3：选骨架 + 逐段人工填充

从 `templates/` 选一个骨架（用 `skill_view` 加载，见下方"模板"段），与用户**逐段确认**：不适用的段直接删掉，不要留占位符。

**完成判据**：每一段要么填了项目特定内容、要么被删除；没有 `{占位符}` 残留，没有"be helpful"之类 agent 默认就会做的废话。

### Step 3.5：继承全局关键规则（必做）

**这一步不可跳过。** 项目级 `.hermes.md` 一旦建立，`~/.hermes.md` 会被完全遮蔽——所有全局规则在项目目录下不再生效。

操作：
1. 读取 `~/.hermes.md`
2. 以下规则段**必须**在项目级 `.hermes.md` 中保留（摘要引用或完整搬运）：
   - **关键原则**（主动推送/系统问题优先/效率优先）— 完整搬运（3 行，短，跨项目铁律级原则）
   - **Hindsight 记忆协议** — 至少保留 retain infra_state 的触发条件和格式
   - **凭印象病黑名单** — 摘要引用（指向 `~/.hermes.md` 的铁律 6+7 段即可，不必完整搬运）
   - **工作流程路由** — 如果项目可能触发跨 agent 协作（如内容创作→huiben）
3. 以下规则段**可选**保留（看项目是否相关）：
   - 基础设施维护职责
   - 情报采集职责
4. 如果项目有独立 AGENTS.md，也要把 AGENTS.md 的关键约束搬进 `.hermes.md`（因为 `.hermes.md` 一旦建立，启动阶段同一层级的 AGENTS.md 不会被加载）

**完成判据（写入后读回验证）**：☐ 关键原则存在（主动推送/系统问题优先/效率优先） ☐ Hindsight retain infra_state 触发条件和格式存在 ☐ 工作流程路由存在（如适用）。缺失则补写。

### Step 4：写入 + 读回验证

写入 `{project_root}/.hermes.md`，读回文件确认 Step 3.5 的关键段都在，然后告诉用户文件已创建并列出关键内容。

**完成判据**：文件已落盘、读回内容与预期一致、用户已看到最终关键内容清单。

## 模板（按需用 skill_view 加载）

骨架已移到 `templates/`，保持本文精简、按需加载（渐进式披露）：

- `templates/general.md` — 通用骨架，任何项目的起点
- `templates/web-app.md` — Web 应用补充段（非默认端口、环境变量名）
- `templates/mcp-server.md` — MCP server 补充段（角色、模型路由、运行路径）
- `templates/data-content.md` — 数据/内容创作补充段

用类似 `skill_view("hermes-md-init/templates/general.md")` 加载对应文件。先用 general 打底，再按项目类型叠加补充段。

## 写什么 vs 不写什么

### 写（只写 agent 推断不出来的）

- 关键约束：不能改的东西、已知的坑、安全约束
- 非显然命令：构建/测试/部署里那些"不看就不知道"的
- 项目特有的工作流 / 跨 agent 路由
- 非显然的架构决策（为什么这么拆，而不是目录在哪）

### 不写（agent 自己能拿到 / 工具能管）

- 目录树、文件列表（agent 会自己探）
- 代码风格 / 格式规则（交给 linter / formatter）
- 能从 `package.json`/`pyproject.toml`/`go.mod` 读出的技术栈版本
- 身份/语气/风格（→ SOUL.md）
- 通用工作规范（→ `~/.hermes.md`）
- 临时 TODO、敏感信息（密钥、密码、token）

## 坑

1. **不要写太长** — 20,000 字符上限，但实际超过 5,000 字符就该考虑精简。中间内容会被截断丢弃。
2. **不要复制全局规范** — `~/.hermes.md` 已有的规则不要重复写。（但注意：项目级会遮蔽全局，关键规则必须继承，见 Step 3.5）
3. **不要写"be helpful"之类的废话** — agent 默认就会做。
4. **YAML frontmatter 是否会被剥离（待实测，官方文档未说明）** — 有观点认为 `.hermes.md` 顶部用 `---` 包裹的 frontmatter 会被丢弃。官方 Context Files 文档对此**无明确说明**，请以实测为准；保险起见，直接写 markdown body，不要把关键指令放进 frontmatter。
5. **项目级遮蔽全局** — 一旦建了项目级 `.hermes.md`，全局的就不会被加载。必须走 Step 3.5 继承检查。
6. **AGENTS.md 也会被遮蔽（启动阶段、同层级）** — `.hermes.md` 优先级高于 AGENTS.md，first match wins。如果项目已有 AGENTS.md，建 `.hermes.md` 时要把 AGENTS.md 的关键约束搬过来。注意：会话中进入子目录时，子目录的 AGENTS.md 仍可能被渐进式加载。
7. **git submodule 独立搜索（作者推断，非官方明文）** — submodule 有自己的 `.git`，由"搜索到 git root 停止"规则外推，搜索应会在 submodule 根停止、不走到父仓库，因此每个 submodule 可能需要独立的 `.hermes.md`。官方未单独文档化 submodule 行为，请以实测为准。
8. **git root 截断不回退** — 如果 CWD 在 git 仓库内且项目没有 `.hermes.md`，搜索在 git root 停止，**不会回退到 `~/.hermes.md`**。这是 Step 3.5 存在的原因。

参考来源见 `hermes-config-organization` 文末"参考来源"。
