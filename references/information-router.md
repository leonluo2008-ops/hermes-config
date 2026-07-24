# 信息路由决策树（Information Router）

> **触发**：遇到"该不该持久化"的信息 / 写 MEMORY/.hermes.md/skill 前 / 用户纠正 / 发现新规则或工作流
> **配套插件**：config-advisor 的 `post_tool_call` hook 监听写入操作，通过 `pre_llm_call` 注入建议

## 核心决策树（严格顺序，命中即停）

```
1. 用户身份/沟通偏好？
   → USER.md（声明性事实，≤1,375 字符）
   例："用户偏好中文回复""用户不喜欢 emoji 列表"

2. 会话级临时状态？（文件路径、任务进度、commit SHA、PR 编号）
   → 不写。用 session_search 回忆
   例："刚才读的 config.yaml 第 393 行""PR #42 已提交"

3. 跨所有项目、跨所有会话的铁律？
   → SOUL.md。但必须用户授权（黑名单约束）
   例："写任何具体值前必先 query 验证"

4. 当前项目的非显然约束/命令/工作流？
   → .hermes.md（项目级 context）
   例："构建用 pnpm 不用 npm""锁定 Node 18"

5. 3+ 步骤的可复用流程？
   → skill（用 skill_manage 创建/更新）
   例："飞书附件投递""项目初始化"

6. 高频引用的事实，且 MEMORY 快满了？
   → "晋升"：从 MEMORY 移到 .hermes.md 或 skill
   例：同一条事实在 3+ 会话被 recall

7. 以上都不匹配？
   → 不写。避免膨胀
   例："目录树""代码风格""能从 manifest 读出的技术栈"
```

## 协作规则（配置文件间的流动）

### MEMORY → .hermes.md 晋升

**信号**：同一条事实在 3+ 会话中被 recall 或引用。
**动作**：从 MEMORY 移到项目 .hermes.md（稳定可见 vs MEMORY 冻结快照）。

MEMORY 是会话启动时的冻结快照——本轮写入要下次会话才进入系统提示 [MEM]。如果一条事实每个会话都需要，它在 MEMORY 中的"下次生效"延迟就成了问题。晋升到 .hermes.md 后每次启动都可见。

### .hermes.md → skill 拆分

**信号**：一个工作流段落 >50 行。
**动作**：拆成独立 skill，.hermes.md 只留 pointer（如"具体流程见 XX skill"）。

Hermes skill 采用渐进式披露 [SKL]——L1 只读 SKILL.md 摘要，需要时才 `skill_view(path=...)` 加载 references。把大段工作流留在 .hermes.md 里 = 每轮都占 token。

### skill → SOUL.md 提取

**信号**：一条规则在每个项目、每个会话、每个任务中都适用。
**动作**：考虑提到 SOUL.md（需用户授权——黑名单约束）。

判断标准：如果 agent 不遵循这条规则，在任何项目都会出问题 → SOUL.md 候选。

### USER.md 反向更新

**信号**：agent 在会话中学到用户偏好（纠正、习惯、风格）。
**动作**：写 USER.md。下次会话该偏好自动生效 [MEM]。

## 插件自动建议模式（config-advisor post_tool_call）

插件在 `post_tool_call` 中监听以下操作，通过 `pre_llm_call` 注入建议（不阻断操作）：

| 监听操作 | 检测逻辑 | 建议注入 |
|---|---|---|
| `memory(action="add")` | 内容含项目名/路径 → 是项目级约束 | "这条信息是项目级约束，建议放到 .hermes.md" |
| `memory(action="add")` | 内容是 3+ 步骤流程 | "建议创建 skill 存储这个流程" |
| `memory(action="add")` | MEMORY 已 >80% | "MEMORY 接近上限，建议先整理" |
| `patch(.hermes.md)` | 段落 >50 行 | "建议拆成 skill，.hermes.md 留 pointer" |
| `skill_manage(action="create")` | 新 skill 内容与现有 skill 重叠 | "检测到与 XX skill 内容重叠" |

**约束**：
- **纯规则检测**——不调 LLM，零延迟
- **只建议不阻断**——通过 `pre_llm_call` 注入到 user message，agent 自行决定是否采纳
- **is_first_turn gate**——建议只在下一轮的首轮注入，不在当前轮重复

## 常见错误

1. **临时状态写进 MEMORY** —— "PR #42 已提交" 7 天后过期，不该持久化
2. **项目约束写进 SOUL.md** —— "用 pnpm" 只对当前项目生效，不是跨项目铁律
3. **workflow 塞进 MEMORY** —— "部署流程是 X → Y → Z" 是指令不是事实，应放 skill 或 .hermes.md
4. **能推断的也写** —— 目录树、代码风格、manifest 里的技术栈，写了只增加 token

## 来源标注

- [MEM] Hermes 官方文档《Memory》— 冻结快照机制 + "Skip These"
- [SKL] Hermes 官方文档《Skills》— 渐进式披露
- [CF] Hermes 官方文档《Context Files》— "stale context is worse than no context"
- [TIPS] Hermes 官方文档《Tips & Best Practices》— Skills = "what" vs Memory = "how"
