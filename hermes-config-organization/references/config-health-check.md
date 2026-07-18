# 配置自检协议（Config Health Check）

> **触发**：会话开头自动 / 用户说"检查配置""配置自检""配置健康""看看配置有没有问题"
> **配套插件**：config-advisor 的 `pre_llm_call` hook 自动执行（零延迟，不调 LLM）

## 检查清单

逐项执行，产出一段 ≤10 行的纯文本报告。

| # | 检查项 | 命令 | 不健康阈值 | 依据 |
|---|---|---|---|---|
| 1 | SOUL.md 存在 | `test -f ~/.hermes/SOUL.md` | 不存在 → Hermes 回退默认身份 | [PER] |
| 2 | SOUL.md 字数 | `wc -m ~/.hermes/SOUL.md` | >2000 → 通常塞了 workflow | [PER] |
| 3 | ~/.hermes.md 存在 | `test -f ~/.hermes.md` | 不存在 → 无全局兜底 | [CF] |
| 4 | ~/.hermes.md 字数 | `wc -m ~/.hermes.md` | >6000 → 接近 20K 截断上限 | [CF] |
| 5 | git 项目有 .hermes.md | `test -f $(git rev-parse --show-toplevel 2>/dev/null)/.hermes.md` | 缺失 → 全局规则不可见（git root 硬停）| [CF] |
| 6 | MEMORY.md 容量 | `wc -m ~/.hermes/memories/MEMORY.md` | >1760 (80%) → 接近报错上限 | [MEM] |
| 7 | USER.md 容量 | `wc -m ~/.hermes/memories/USER.md` | >1100 (80%) → 同上 | [MEM] |

### 阈值依据

- **SOUL.md 2000 字符**：作者经验值。官方未单独设限，SOUL.md 和其他 context 文件一样在 20,000 字符处截断 [CF]。但 SOUL.md 是身份锚定层，超过 2000 通常说明往里塞了 workflow。
- **MEMORY.md 2200 字符 / USER.md 1375 字符**：官方硬上限 [MEM]。不自动截断——超限时 `memory` 工具返回错误，要求 agent 先整理。80% 是安全预警线。
- **.hermes.md 6000 字符**：20K 截断上限（head 70% + tail 20%，中间 10% 丢弃）的 30%。建议控制在 6000 以内 [CF]。

## 执行脚本（skill 手动模式）

```bash
#!/bin/bash
# 配置健康检查——确定性，幂等，无副作用

HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
REPORT=""

# 1. SOUL.md
if [[ -f "$HOME_DIR/SOUL.md" ]]; then
  soul_size=$(wc -m < "$HOME_DIR/SOUL.md")
  if (( soul_size > 2000 )); then
    REPORT+="⚠️ SOUL.md (${soul_size} 字符) — 超过 2000，建议精简（workflow 移到 .hermes.md）\n"
  else
    REPORT+="✓ SOUL.md (${soul_size} 字符)\n"
  fi
else
  REPORT+="✗ SOUL.md 不存在 — Hermes 将回退默认身份\n"
fi

# 2. ~/.hermes.md
if [[ -f "$HOME/.hermes.md" ]]; then
  hermes_size=$(wc -m < "$HOME/.hermes.md")
  if (( hermes_size > 6000 )); then
    REPORT+="⚠️ ~/.hermes.md (${hermes_size} 字符) — 超过 6000，建议拆到 skill\n"
  else
    REPORT+="✓ ~/.hermes.md (${hermes_size} 字符)\n"
  fi
else
  REPORT+="✗ ~/.hermes.md 不存在 — 无全局兜底\n"
fi

# 3. git 项目 .hermes.md
git_root=$(git rev-parse --show-toplevel 2>/dev/null)
if [[ -n "$git_root" ]]; then
  if [[ ! -f "$git_root/.hermes.md" ]]; then
    REPORT+="✗ 当前 git 项目缺 .hermes.md — 全局规则不可见（git root 硬停）\n"
    REPORT+="  → 建议跑 hermes-md-init skill 建立项目配置\n"
  else
    REPORT+="✓ 项目 .hermes.md 存在\n"
  fi
fi

# 4. MEMORY.md
if [[ -f "$HOME_DIR/memories/MEMORY.md" ]]; then
  mem_size=$(wc -m < "$HOME_DIR/memories/MEMORY.md")
  if (( mem_size > 1760 )); then
    REPORT+="⚠️ MEMORY.md (${mem_size}/2200, $(( mem_size * 100 / 2200 ))%) — 接近上限\n"
    REPORT+="  → 建议整理旧条目或晋升到 .hermes.md\n"
  else
    REPORT+="✓ MEMORY.md (${mem_size}/2200)\n"
  fi
fi

# 5. USER.md
if [[ -f "$HOME_DIR/memories/USER.md" ]]; then
  user_size=$(wc -m < "$HOME_DIR/memories/USER.md")
  if (( user_size > 1100 )); then
    REPORT+="⚠️ USER.md (${user_size}/1375, $(( user_size * 100 / 1375 ))%) — 接近上限\n"
  else
    REPORT+="✓ USER.md (${user_size}/1375)\n"
  fi
else
  REPORT+="✗ USER.md 不存在 — 身份信息未初始化\n"
fi

echo -e "配置健康检查：\n$REPORT"
```

## 插件自动模式（config-advisor pre_llm_call）

插件在 `pre_llm_call` hook 中用 Python `path.read_text()` + `len()` 执行同样检查（字符数，非字节）。

**关键约束**：
- **is_first_turn gate**：只在 `kwargs.get("is_first_turn") == True` 时执行完整检查。非首轮只做增量检查（如果 agent 刚写了配置文件）。
- **注入长度 <500 字符**：避免触发 Hermes 的 hook_output_spill 机制（单条注入 >10,000 字符会溢写到磁盘，只留 preview）[PLG]。
- **全部健康时返回 None**：零开销，不注入任何内容。
- **不破坏 prompt cache**：注入到 user message，不是 system prompt [PLG]。

## 来源标注

- [PER] Hermes 官方文档《Personality & SOUL.md》
- [CF] Hermes 官方文档《Context Files》
- [MEM] Hermes 官方文档《Memory》
- [PLG] Hermes 官方文档《Plugins》— pre_llm_call context injection + hook_output_spill
