# 第三方 Hermes 配置博客/笔记 — 术语核实对照表

> **来源**:2026-07-20 用户给一篇 Notion 笔记(匿名 zbook 作者)让核实,7 条核心声明里 5 条术语错或机制错。
> **铁律**:任何第三方 Hermes 教程/笔记/博客(包括知乎/公众号/Discord 频道/B站视频)声称的机制名/config key/CLI 子命令,**必须对照官方文档原文核实**——不能因为"对方是实战玩家"就当真。这跟 §4.6a 的"自己凭印象写"是同一类病,只是病源从"自己记忆"换成"别人笔记"。

## 官方文档真实 URL slugs(2026-07-20 实测)

文档站 Docusaurus,真实路径在 `/docs/user-guide/features/<slug>`(不是 `/docs/features/<slug>`,后者 404):

| 主题 | 真实 URL |
|---|---|
| 持久记忆 | https://hermes-agent.nousresearch.com/docs/user-guide/features/memory |
| 技能系统 | https://hermes-agent.nousresearch.com/docs/user-guide/features/skills |
| MoA | https://hermes-agent.nousresearch.com/docs/user-guide/features/mixture-of-agents |
| 记忆 provider | https://hermes-agent.nousresearch.com/docs/user-guide/features/memory-providers |
| Curator | https://hermes-agent.nousresearch.com/docs/user-guide/features/curator |
| 插件 | https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins |

**JS 路由坑**:sidebar link 点击不刷新地址栏,要拿真实 URL 得 `browser_console` 跑 `window.location.href`。

## 7 条声明 vs 官方文档(2026-07-20)

| # | 第三方笔记声称 | 官方文档真实情况 | 纠偏 |
|---|---|---|---|
| 1 | "把 Memory 删除,自动 Skill 删除" | `memory_enabled: false` 关 memory;`hermes profile create --no-skills` 或 install.sh `--no-skills` 拿空白 skill 目录 | 方向对,路径糙——是 config 开关 + flag,不是删目录文件 |
| 2 | "涉及 Hook 和一处代码调整" | **当前版本无 "Hook" 概念**。自动持久化靠 background self-improvement review,由 `auxiliary.background_review` 驱动 | 关掉靠 `memory_enabled: false` + `skills.write_approval`,**不改源码**。作者大概把"改 config"说成"改代码",或老版本说法 |
| 3 | "配置 DSv4Flash 为事实提取模型" | 真实机制是 `auxiliary.background_review.model` 指向便宜模型跑后台 review | 叫法错——官方叫 **background review model**,干的事是"回看对话→决定要不要存 memory/改 skill",不是"提取事实"。示例用 `google/gemini-3-flash-preview`,填 deepseek model ID 也行 |
| 4 | "三元组:技能 + 事实(图数据库 Graphify) + 永久记忆(Hindsight)" | 技能=原生 skills ✓;Hindsight 是官方 8 个 memory provider 之一 ✓;图数据库需自己搭 TEI embedding + 图库 + MCP wrapper | 图数据库是 infra 级自定义,不是 Hermes 内置功能。理论可行但非开箱即用 |
| 5 | "Skill 自动创建提醒 hook 改为每 N 轮提醒" | **不存在"每 N 轮提醒"的 config**。自动创建靠 `skill_manage` 工具,触发条件是"5+ tool calls 的复杂任务后 / 出错找到路 / 用户纠正" | **改不了频率**,只能开/关:`skills.write_approval: true` 把所有写操作 stage 起来让你审 |
| 6 | "Embedding/Rerank 用 HuggingFace TEI,CPU 够用" | session_search 走 FTS5(SQLite 全文),不强制 embedding。接 Hindsight/Mem0 这类 provider 时它们各自管 embedding | TEI 是自托管选项之一,属于 infra 级活,不是 Hermes config |
| 7 | "让 Hermes 检查所有 agent"(三体系接入所有 agent) | Hermes 多 agent 靠 profile 隔离 + delegate_task。每个 profile 独立 skills/memories/cron | 没有"一键同步所有 agent"机制,需手动给每个 profile 配同一个 MCP server |

## background_review 真实 config 段(官方文档原文)

```yaml
# ~/.hermes/config.yaml
auxiliary:
  background_review:
    model: google/gemini-3-flash-preview   # auto (default) = main chat model
```

- 指向不同模型时 review 跑那边,成本 ~3-5× 更低
- 设 `auto` 或主模型名 → review 跑主模型 + warm cache replay
- 这是笔记里"DSv4Flash 事实提取模型"的真身

## memory / skill 控制相关 config 全集(官方文档实证)

```yaml
memory:
  write_approval: false        # true = stage 写入待审
memory_enabled: true            # false = 完全关 memory
display:
  memory_notifications: on      # on / off / verbose — 只控通知,不控行为
skills:
  write_approval: false         # true = 所有 skill 写 stage
  guard_agent_created: ...      # 内容扫描器,独立于 approval gate
```

## 核实工作流(30 秒)

1. 从第三方素材提取"声称的 config key / 机制名 / CLI 子命令"
2. 浏览器开官方文档对应页(memory / skills / moa / curator)
3. `browser_console` 跑 `(() => { const a=document.querySelector('article'); const text=a?a.innerText:''; return text.includes('<声称的 key>'); })()` 验证字面存在
4. 不存在 → 标"术语错",找官方真名
5. 存在但语义不符 → 标"机制误解",写真身

## 反模式

- ❌ "对方是实战玩家,写的肯定对"——zbook 笔记作者用了 Hermes,但把 background_review 叫"事实提取模型"、把 config 开关叫"Hook 改代码",5/7 条术语错
- ❌ 只读第三方不动手验证就转述给用户——这等于把别人的凭印象病传染给自己的回答
- ❌ 用博客截图/外链/速查冒充核实结果(违反 MEMORY ⑥「跨机文档不能直接当本机规范」的同源病:二手来源不能直接当官方规范)
