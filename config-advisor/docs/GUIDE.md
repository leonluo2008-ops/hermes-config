# config-advisor 保姆级开发与使用文档

> **版本**：v0.1.1（2026-07-18，修复字节/字符 bug 后）
> **配套 Skill**：`hermes-config-organization` v3+
> **仓库**：https://github.com/leonluo2008-ops/hermes-config

---

## 目录

1. [它是什么](#1-它是什么)
2. [核心设计理念](#2-核心设计理念)
3. [三层 Hook 架构（工作流程图）](#3-三层-hook-架构工作流程图)
4. [使用指南（用户视角）](#4-使用指南用户视角)
5. [安装与配置](#5-安装与配置)
6. [如何验证它在运行](#6-如何验证它在运行)
7. [如何触发健康检查](#7-如何触发健康检查)
8. [复盘报告机制](#8-复盘报告机制)
9. [配置项详解](#9-配置项详解)
10. [开发指南（源码结构）](#10-开发指南源码结构)
11. [与 harness-guard 的关系](#11-与-harness-guard-的关系)
12. [常见问题](#12-常见问题)
13. [设计决策溯源（为什么这么写）](#13-设计决策溯源为什么这么写)

---

## 1. 它是什么

**config-advisor** 是一个 Hermes Agent 用户插件（user plugin），做三件事：

| 功能 | 触发时机 | 延迟 | 阻断？ |
|------|---------|------|--------|
| **配置健康检查** | 每个会话首轮 | 零（纯文件 I/O） | 否 |
| **信息路由建议** | 每次 `memory`/`patch` 工具调用后 | 零（纯规则） | 否 |
| **会话复盘报告** | 真实会话结束时 | 异步（后台线程 LLM） | 否 |

**核心特征**：**永远只观察、只建议，从不阻断 agent 的操作**。

---

## 2. 核心设计理念

### 永不阻断（observer-only）

config-advisor 的所有 hook 回调返回值都不会阻止 agent 继续工作：
- `pre_llm_call`：返回 `{"context": "..."}` 或 `None`（注入建议文本，不拦截）
- `post_tool_call`：返回 `None`（返回值被忽略，只记录）
- `on_session_finalize`：返回 `None`（异步开线程，不阻塞）

这与 `harness-guard`（阻断式审查）形成互补。

### 零延迟优先

健康检查和信息路由建议都是**纯确定性规则**（文件 I/O、字符串匹配、正则），不调 LLM。只有会话复盘报告调 LLM，且在**异步 daemon thread** 里跑，不阻塞会话清理。

### 注入不破坏 prompt cache

所有注入走 `pre_llm_call` 的 `{"context": "..."}`，追加到**当前轮的 user message**，不是 system prompt。这样不会破坏 Hermes 的 prompt cache（system prompt 不变，cache 命中）。

---

## 3. 三层 Hook 架构（工作流程图）

```
用户发消息（每轮）
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  pre_llm_call hook                                   │
│  ───────────────────                                 │
│  if is_first_turn:                                   │
│    1. check_health() → 配置健康检查（零延迟）        │
│    2. read_unread_report() → 读上次会话的复盘报告    │
│  （任意轮）                                          │
│    3. 弹出 _advice_queue 里的排队建议（≤3 条）       │
│  → 返回 {"context": "合并文本 <480 字符"}            │
└─────────────────────────────────────────────────────┘
     │
     ▼
  LLM 生成回复 + 调用工具
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  post_tool_call hook（每次工具调用后）               │
│  ───────────────────                                 │
│  1. 记录到审计日志（in-memory deque）                │
│  2. analyze_tool_call() → 若匹配模式，生成路由建议   │
│     → 存入 _advice_queue（等下一轮 pre_llm_call 注入）│
│  → 返回 None（返回值被忽略）                         │
└─────────────────────────────────────────────────────┘
     │
   ... (多轮循环) ...
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  on_session_finalize hook（真实会话结束：/new, /reset, expiry）│
│  ───────────────────                                 │
│  1. 快照审计日志到局部变量                           │
│  2. 开 daemon thread（不阻塞）：                     │
│     - 调 LLM 分析配置活动                            │
│     - 原子写入报告文件（retro_*.md）                 │
│  → 返回 None                                         │
└─────────────────────────────────────────────────────┘
     │
     ▼
  下个会话首轮 → pre_llm_call 读这份报告 → 注入给 agent
```

---

## 4. 使用指南（用户视角）

### 你能感知到的三件事

**① 会话开头，agent 可能突然知道你的配置有问题**

开新会话发第一条消息时，插件自动检查配置文件大小。如果 SOUL.md / .hermes.md / MEMORY.md / USER.md 任意一个超阈值，agent 的上下文里会被注入一段提示。**你不需要做任何事**，agent 自己会看到并可能主动提醒你。

**② 你用 `memory` 工具写东西时，agent 下轮可能收到路由建议**

比如 agent 把"项目级约束"写进 MEMORY，插件会在下一轮注入建议："这条信息更适合放 .hermes.md"。**你不需要做任何事**，agent 自己会看到建议。

**③ 会话结束后，会生成一份复盘报告**

`/new` 开新会话、或会话超时（expiry）时，插件在后台调 LLM 分析本次会话的配置活动，把报告写到 `~/.hermes/config-advisor/reports/retro_*.md`。**下次会话首轮**，如果报告有可操作内容，会自动注入给 agent。如果分析结果是"无需调整"，报告静默标记为已读，不打扰你。

### 你**不能**直接做的事

- ❌ **手动触发健康检查**——它只在首轮自动跑
- ❌ **手动查看注入内容**——注入在 agent 的上下文里，用户侧看不到
- ❌ **指定什么时候生成复盘报告**——只在真实会话边界触发

### 你**能**做的替代方案

如果想**立刻看健康检查结果**（不等首轮注入），直接让 agent 跑：

```bash
PYTHONPATH=/home/luo/.hermes/plugins/config-advisor python3 -c \
  "from health_check import check_health, format_report; print(format_report(check_health()) or '全部健康')"
```

或者对 agent 说"检查配置健康"，agent 会按 `hermes-config-organization` skill 的脚本跑一遍。

---

## 5. 安装与配置

### 前置条件

- Hermes Agent（需支持 plugin hooks）
- `httpx`：`pip install httpx`（复盘报告 LLM 调用用）
- 一个 LLM API 密钥（GLM / MiniMax / Juxin 任选，用于复盘报告）

### 一键安装

```bash
git clone https://github.com/leonluo2008-ops/hermes-config.git
cd hermes-config
./install.sh --plugins
```

`install.sh` 会：
1. 把两个 skill 复制到 `~/.hermes/skills/`
2. 把 config-advisor 插件复制到 `~/.hermes/plugins/`
3. 提示你手动在 `config.yaml` 启用 + 重启 gateway

### 手动启用插件

编辑 `~/.hermes/config.yaml`（用 Python 局部修改，不要用 `hermes config set` 写列表）：

```python
import yaml
path = '/home/luo/.hermes/config.yaml'
with open(path) as f:
    cfg = yaml.safe_load(f)
e = cfg.setdefault('plugins', {}).setdefault('enabled', [])
if 'config-advisor' not in e:
    e.append('config-advisor')
with open(path, 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
```

重启 gateway（**必须从外部终端**，不能从 agent 内部）：
```bash
hermes gateway restart
```

### 配置 LLM 密钥

```bash
cd ~/.hermes/plugins/config-advisor
cp .env.example .env
# 编辑 .env，填入：
# CONFIG_ADVISOR_PROVIDER=minimax  (或 glm / juxin)
# CONFIG_ADVISOR_BASE_URL=https://api.minimaxi.com/v1
# CONFIG_ADVISOR_MODEL=MiniMax-M3
# CONFIG_ADVISOR_API_KEY=你的key（或用 ZAI_API_KEY 等 fallback）
```

**API key 解析顺序**（任填一个即可）：
1. `CONFIG_ADVISOR_API_KEY`（推荐，插件专用）
2. `ZAI_API_KEY`（Z.AI / GLM fallback）
3. `GLM_API_KEY`（GLM fallback）
4. `MINIMAX_CN_API_KEY`（Minimax fallback）
5. `JUXIN_GEMINI_API_KEY`（Juxin fallback）

---

## 6. 如何验证它在运行

### 三步验证

```bash
# 1. 插件是否被发现 + 启用
hermes plugins list
# 应看到：config-advisor | enabled | user

# 2. Hook 是否注册
hermes hooks list
# 应看到 pre_llm_call / post_tool_call / on_session_finalize 注册了 config-advisor

# 3. 加载日志是否正常
grep "config-advisor" ~/.hermes/logs/agent.log | tail -5
# 应看到类似：
# config-advisor: loaded N env var(s) from .../.env
# config-advisor: registering pre_llm_call + post_tool_call + on_session_finalize hooks
```

### 验证健康检查函数本身

不依赖 gateway，直接调函数看结果：

```bash
PYTHONPATH=/home/luo/.hermes/plugins/config-advisor python3 -c "
from health_check import check_health, format_report
issues = check_health()
for i in issues:
    print(f'  [{i.severity}] {i.file}: {i.message}')
print()
report = format_report(issues)
print(report if report else '(全部健康，无注入)')
"
```

### 验证复盘报告生成

```bash
# 看历史报告
ls -lt ~/.hermes/config-advisor/reports/
# .read 后缀 = 已被下个会话首轮读过，不会再注入
# 无 .read = 未读，下次首轮会注入
```

---

## 7. 如何触发健康检查

### 自动触发（设计如此）

**每个会话的第一轮对话**，`pre_llm_call` hook 在 `is_first_turn == True` 时自动调用 `check_health()`。

- "会话" = 一个 session_id 周期
- "首轮" = 该 session 的第一条用户消息
- 新会话的产生：`/new`、`/reset`、session expiry、首次打开对话

**只有检测到 warn/error 才会注入**——全健康时返回空字符串，零注入，不浪费 token。

### 手动触发（绕过 hook）

三种方式，按推荐度排序：

**方式 A（推荐）：让 agent 跑 skill 脚本**
对 agent 说"检查配置健康"或"配置自检"。agent 会加载 `hermes-config-organization` skill，按 `references/config-health-check.md` 的 bash 脚本跑一遍。

**方式 B：直接调 Python 函数**
```bash
PYTHONPATH=/home/luo/.hermes/plugins/config-advisor python3 -c \
  "from health_check import check_health, format_report; print(format_report(check_health()) or '全部健康')"
```

**方式 C：开新会话**
`/new` 开新会话，发任意消息，插件自动跑。注入在 agent 上下文里，你侧看不到，但 agent 会看到。

### 会话中途能不能触发？

**不能**。`check_health()` 只在首轮调用，代码在 `__init__.py:98` 的 `if is_first_turn:` gate 里。这是设计决策——避免每轮重复检查同一组文件浪费 I/O。

会话中唯一自动运行的是**信息路由建议**（`post_tool_call`），但它检查的是工具调用的内容，不是配置文件大小。

---

## 8. 复盘报告机制

### 触发时机

只在**真实会话边界**触发（`on_session_finalize` hook）：
- `/new` 开新会话
- `/reset`
- session expiry（超时）

**不是**每轮触发（`on_session_end` 才是 per-turn，config-advisor 故意不用它）。

### 生成流程

1. `on_session_finalize` 被调用
2. **先快照**审计日志到局部变量（`snapshot_and_clear()`，原子操作避免竞态）
3. 开 daemon thread（`threading.Thread(daemon=True)`），hook 回调立即返回（不阻塞）
4. 后台线程：
   - 调 LLM（GLM/MiniMax/Juxin）分析配置活动摘要
   - 原子写报告文件（tmp 文件 + rename，避免半成品文件）
5. 报告写到 `~/.hermes/config-advisor/reports/retro_YYYY-MM-DD_HHMM_<sid>.md`

### 注入流程（下次会话首轮）

1. 下次会话首轮，`pre_llm_call` 调 `read_unread_report()`
2. 扫描 `reports/` 目录，找最新未读报告（无 `.read` 后缀）
3. 提取 `## LLM 分析` 段
4. 如果内容含"无需调整" → 静默标记已读（rename 加 `.read`），不注入
5. 如果有可操作内容 → 截断到 400 字符，注入给 agent，然后标记已读

### 手动查看报告

```bash
# 看所有报告（最新的在前）
ls -lt ~/.hermes/config-advisor/reports/

# 读最新报告
cat $(ls -t ~/.hermes/config-advisor/reports/retro_*.md | head -1)
```

---

## 9. 配置项详解

所有配置通过环境变量，优先从插件目录的 `.env` 文件读，系统 env 优先级更高（不 clobber）。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CONFIG_ADVISOR_PROVIDER` | `glm` | Provider 预设：`glm` / `minimax` / `juxin` |
| `CONFIG_ADVISOR_BASE_URL` | 按 provider | 覆盖 API 端点 |
| `CONFIG_ADVISOR_MODEL` | 按 provider | 覆盖模型名 |
| `CONFIG_ADVISOR_API_KEY` | — | API 密钥（推荐） |
| `CONFIG_ADVISOR_TIMEOUT_S` | `60` | LLM 分析超时秒数 |
| `CONFIG_ADVISOR_DISABLE` | — | 设为 `1` / `true` / `yes` / `on` 彻底禁用 |

### Provider 预设（`analyzer.py:24-37`）

| Provider | base_url | model |
|----------|----------|-------|
| `glm` | `https://open.bigmodel.cn/api/coding/paas/v4` | `glm-5.2` |
| `minimax` | `https://api.minimaxi.com/v1` | `MiniMax-M3` |
| `juxin` | `https://api.jxincm.cn/v1` | `gemini-3.5-flash` |

### 健康检查阈值（`health_check.py:15-20`）

| 文件 | 预警阈值 | 硬上限 | 说明 |
|------|---------|--------|------|
| `SOUL.md` | >2000 字符 | — | 超过说明塞了 workflow |
| `~/.hermes.md` | >6000 字符 | — | 20K 截断上限的 30% |
| `MEMORY.md` | >1760 (80%) | 2200 | 官方硬限 |
| `USER.md` | >1100 (80%) | 1375 | 官方硬限 |

> **⚠️ 2026-07-18 修复**：之前用 `stat().st_size`（字节），对中文虚高 1.9 倍。现在用 `len(read_text())`（字符）。阈值单位是**字符**，不是字节。

---

## 10. 开发指南（源码结构）

### 目录结构

```
~/.hermes/plugins/config-advisor/
├── plugin.yaml          # 插件清单（name, version, hooks）
├── __init__.py          # 入口：register(ctx) + 三个 hook 回调
├── health_check.py      # 配置健康检查（纯 Python，零延迟）
├── advisor_rules.py     # 信息路由建议规则（纯 Python，零延迟）
├── analyzer.py          # 异步 LLM 复盘分析（daemon thread）
├── audit_trail.py       # 审计日志（线程安全 deque + lock）
├── .env                 # 本地配置（gitignored）
├── .env.example         # 配置模板
├── .gitignore
└── README.md
```

### 运行时产物

```
~/.hermes/config-advisor/
└── reports/
    ├── retro_2026-07-18_0909_abc12345.md       # 未读
    └── retro_2026-07-17_2325_def67890.md.read  # 已读（.read 后缀）
```

### 模块职责

#### `health_check.py` — 配置健康检查

**职责**：检查 5 个配置文件的大小是否超阈值。

**关键函数**：
- `check_health() -> List[HealthIssue]`：跑全部检查，返回 issue 列表
- `format_report(issues) -> str`：格式化为注入文本（<500 字符），全健康返回空字符串

**阈值常量**（`health_check.py:15-20`）：见上方配置项表。

**注意**：`_file_size()` 返回**字符数**（`len(read_text())`），不是字节数。

#### `advisor_rules.py` — 信息路由建议

**职责**：分析 `memory` / `patch` 工具调用的内容，如果匹配可疑模式，生成路由建议。

**三类检测**（`advisor_rules.py:60-75`）：
1. **项目级约束误放 MEMORY** — 内容含 `/home/`、`~/.hermes/`、`项目`、`project`、`deploy`、`build`
2. **3+ 步骤流程误放 MEMORY** — 内容含 `→`、`步骤`、`step`、`1.` `2.` `3.`、`流程`
3. **临时状态误放 MEMORY** — 内容含 `commit`、`pr #`、`phase`、`已提交`、`已完成`、`进度`

**patch 特殊检测**（`advisor_rules.py:86-104`）：patch `.hermes.md` 且 `new_string > 1500 字符` → 建议拆成 skill。

**输出**：建议文本（<300 字符），或 `None`。

#### `analyzer.py` — 异步 LLM 复盘

**职责**：会话结束时，后台调 LLM 分析配置活动，写报告文件。

**关键函数**：
- `trigger_async_analysis(session_id, audit_entries)`：开 daemon thread（不阻塞）
- `read_unread_report() -> Optional[str]`：读最新未读报告（供 pre_llm_call 调用）
- `_call_llm(snapshot, api_key) -> str`：调 LLM，strip `<think>` 标签

**原子写入**（`analyzer.py:215-239`）：写 tmp 文件 → rename，保证不出现半成品文件。

**报告格式**：
```markdown
# 配置复盘报告
- 日期: ...
- Session: ...
- 工具调用: N

## LLM 分析
（LLM 生成的 1-3 条建议）

## 原始数据
### 配置活动
（工具调用统计）
### 健康检查
（注入的健康检查文本）
```

#### `audit_trail.py` — 审计日志

**职责**：线程安全地记录每次工具调用。

**数据结构**：
- `ConfigAuditLog`：模块级单例
- 每 session 一个 `deque(maxlen=100)`
- 最多 50 个 session（超过驱逐最老的）

**config_related 标记**（`audit_trail.py:41-54`）：工具名是 `memory` / `skill_manage`，或 args 字符串含配置文件模式（`SOUL.md`、`.hermes.md`、`MEMORY.md`、`config.yaml`、`plugin.yaml`、`SKILL.md`）。

**线程安全**：所有操作加 `threading.Lock()`。

### Hook 注册（`__init__.py:200-207`）

```python
def register(ctx) -> None:
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    ctx.register_hook("on_session_finalize", _on_session_finalize)
```

### 三个 Hook 回调签名

```python
def _on_pre_llm_call(
    session_id: str = "",
    is_first_turn: bool = False,
    **_kwargs: Any,
) -> Optional[dict]:
    # 返回 {"context": "..."} 注入 user message，或 None

def _on_post_tool_call(
    tool_name: str = "",
    args: Any = None,
    result: Any = None,
    task_id: str = "",
    session_id: str = "",
    duration_ms: int = 0,
    **_kwargs: Any,
) -> None:
    # 返回值被忽略（observer）

def _on_session_finalize(
    session_id: str = "",
    **_kwargs: Any,
) -> None:
    # 返回值被忽略；内部开 daemon thread
```

### 开发工作流

运行目录 = 开发目录 = git 仓库（三者合一）：

```bash
cd ~/Github/hermes-config   # git 仓库（config-advisor/ 是子目录）
# 改 config-advisor/health_check.py
git add -A && git commit -m "fix: ..."
git push

# 同步到运行目录
cp -r config-advisor/ ~/.hermes/plugins/

# 重启 gateway 生效（必须从外部终端）
hermes gateway restart
```

---

## 11. 与 harness-guard 的关系

两个插件互补，可共存：

| 维度 | harness-guard | config-advisor |
|------|---------------|----------------|
| **定位** | 写操作正确性审查 | 配置健康度监控 |
| **交互** | 阻断（返回 error JSON） | 建议（注入 advice） |
| **LLM 调用** | 同步（写操作时 10-20s） | 异步（会话结束时后台线程） |
| **Hook** | `post_tool_call` + `transform_tool_result` | `pre_llm_call` + `post_tool_call` + `on_session_finalize` |
| **数据** | 审计日志（in-memory deque） | 审计日志（独立 deque）+ 复盘报告（文件）|

**关键共存设计**：
- config-advisor **不用** `transform_tool_result`（harness-guard 已注册，first-wins 会冲突）
- config-advisor 只用 `post_tool_call`（observer，返回值忽略）
- 两个插件各有独立的审计日志 deque，互不干扰

---

## 12. 常见问题

### Q: 开了新会话但没看到健康检查注入？

**原因**：全健康时返回空字符串，不注入（设计如此，省 token）。
**验证**：手动跑 `check_health()`（见 §6）看是否有 issue。

### Q: 复盘报告没生成？

**检查**：
1. `.env` 里有没有 API key（`CONFIG_ADVISOR_API_KEY` 或 fallback）
2. 日志里有没有 `analysis thread failed`：`grep "config-advisor.*fail" ~/.hermes/logs/agent.log`
3. 会话有没有真正结束（`/new` 或 expiry，不是每轮）

### Q: 注入内容被截断了？

**原因**：注入文本硬上限 480 字符（`__init__.py:122-123`），超过会截断 + 加 `…(详见 config-advisor)`。
**设计**：避免触发 Hermes 的 hook_output_spill 机制（单条 >10K 字符溢写磁盘）。

### Q: 字节数和字符数为什么不一样？

**中文 UTF-8**：1 个汉字 = 3 字节 = 1 字符。
**Hermes 限制单位**：字符数（`len(text)`）。
**本插件**：用 `len(read_text())` 返回字符数，与 Hermes 口径一致。

> 2026-07-18 修复了一个 bug：之前用 `stat().st_size`（字节），对中文内容虚高约 1.9 倍，导致全盘误报。

### Q: 怎么彻底禁用插件？

```bash
# 方式 1：环境变量（临时）
export CONFIG_ADVISOR_DISABLE=1

# 方式 2：.env 文件（持久）
echo "CONFIG_ADVISOR_DISABLE=1" >> ~/.hermes/plugins/config-advisor/.env

# 方式 3：config.yaml（移出 enabled 列表）
# 编辑 ~/.hermes/config.yaml，从 plugins.enabled 删掉 'config-advisor'

# 改完重启 gateway
```

---

## 13. 设计决策溯源（为什么这么写）

### 为什么用 `on_session_finalize` 不用 `on_session_end`？

**源码证据**：`turn_finalizer.py:489-503` 注释明写 `on_session_end` 是 **"Fired at the very end of every run_conversation call"**——即**每轮**触发。如果用它生成复盘报告，一次会话会生成 N 份重复报告。

`on_session_finalize` 才是**真实会话边界**（`slash_commands.py:206-216`），在 `/new`、`/reset`、session expiry 时触发。

### 为什么 `pre_llm_call` 要加 `is_first_turn` gate？

`pre_llm_call` **每轮**触发。如果不 gate，健康检查和复盘报告会被每轮重复注入，污染每轮的 user message，浪费 token + 干扰 agent。

### 为什么不用 `transform_tool_result`？

`transform_tool_result` 是 **first-wins**（`model_tools.py:1334-1337`）：第一个返回 `str` 的 callback 直接 break，后续全跳过。harness-guard 已经注册了这个 hook。config-advisor 只需要"观察"，用 `post_tool_call`（observer，返回值忽略）更安全。

### 为什么 LLM 分析要开 daemon thread？

`invoke_hook` 是**同步调用**（`plugins.py L1915`）。如果在 hook 回调里同步调 LLM（10-20s），会阻塞 gateway 线程，期间 agent 卡死不响应。daemon thread 让 hook 立即返回，分析在后台跑。

### 为什么注入要 <500 字符？

Hermes 有 **hook_output_spill** 机制：单条注入 >10,000 字符会溢写到磁盘，只留 preview。config-advisor 保守控制在 480 字符以内，留足余量。

### 为什么快照数据后再开线程？

`on_session_finalize` 触发时，harness-guard 的 `on_session_end`（per-turn）可能正在清理审计日志。如果不快照，后台线程读到的是空数据或竞态数据。`snapshot_and_clear()` 是原子操作（加锁 + pop），保证数据一致性。

---

## 参考来源

- Hermes 插件系统源码：`~/.hermes/hermes-agent/hermes_cli/plugins.py`
- Hermes hooks 文档：`~/.hermes/hermes-agent/website/docs/user-guide/features/hooks.md`
- 配套 skill：`hermes-config-organization`（`references/config-health-check.md`）
- hook 机制详解：`hermes-plugin-dev` skill（`autonomous-ai-agents/hermes-plugin-dev/SKILL.md`）
