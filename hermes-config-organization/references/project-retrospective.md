# 项目工作流复盘（Project Workflow Retrospective）

> **触发**：用户说"复盘""整理配置""看看有没有该改的""分析一下" / 会话结束自动（插件）
> **配套插件**：config-advisor 的 `on_session_finalize` hook（真实会话边界）

## 三种触发方式

### 方式 1：用户主动触发（skill 同步执行）

**触发词**（按用户沟通/语言习惯设计，持续扩充）：

- "复盘一下" / "复盘这个项目"
- "整理一下配置" / "整理项目配置"
- "看看有没有该改的" / "看看配置有没有问题"
- "分析一下最近的配置使用情况"
- "这个项目的工作流该整理了"
- "配置复盘"

**流程**：
1. 扫描当前项目 .hermes.md 内容
2. 对比本会话 / 近期会话的审计日志（哪些段被引用、哪些没碰到）
3. 产出建议清单（见下方"分析维度"）
4. 用户确认后执行变更

### 方式 2：会话结束自动触发（config-advisor 插件）

**Hook**：`on_session_finalize`（不是 `on_session_end`）

> ⚠️ **关键事实**（源码验证 `turn_finalizer.py:490`）：`on_session_end` 是 **per-turn**（每轮触发），不是 per-session。真实会话边界 hook 是 `on_session_finalize`（`gateway/slash_commands.py:206`），在 `/new`、`/reset`、session expiry 时触发，参数 `(session_id, platform, reason, old_session_id, new_session_id)`。

**异步执行**：
```python
def _on_session_finalize(session_id="", **kwargs):
    # 1. 快照数据（audit log 可能被 harness-guard 清理）
    snapshot = {
        'audit_trail': audit_trail.copy_session(session_id),
        'config_sizes': _measure_config_files(),
        'timestamp': time.time(),
    }
    # 2. 开后台线程调 LLM（不阻塞会话清理）
    thread = threading.Thread(
        target=_run_analysis_async,
        args=(session_id, snapshot),
        daemon=True
    )
    thread.start()
```

**竞态处理**（审查 F2-2）：
- harness-guard 的 `on_session_end`（per-turn）会做 `clear_session` 清理 audit log
- config-advisor 用 `on_session_finalize`（per-session），触发时机不同，但必须在回调中**先快照再开线程**
- 线程只读快照数据，不直接访问 harness-guard 的内存状态

**daemon 线程风险**（审查 F2-2）：
- `threading.Thread(daemon=True)` 在进程退出时被直接杀死
- 缓解：报告写到临时文件 + rename 原子操作，保证不出现半截文件
- 如果报告没写完，下次会话 pre_llm_call 读不到 = 无害（不注入）

### 方式 3：下次会话注入（config-advisor 插件）

**Hook**：`pre_llm_call`（只在 `is_first_turn=True` 时执行）

```python
def _on_pre_llm_call(session_id="", is_first_turn=False, **kwargs):
    if not is_first_turn:
        return None  # 非首轮不注入
    report = _read_unread_report(session_id)
    if report:
        return {"context": f"📋 上次会话配置复盘：\n{report}"}
    return None
```

**约束**：注入内容 <500 字符，避免触发 hook_output_spill。

## 分析维度

### 配置使用率

| 分析项 | 数据来源 | 建议动作 |
|---|---|---|
| .hermes.md 段落被引用次数 | 审计日志中的 read_file/patch 记录 | 0 次 → 删除候选 |
| MEMORY 条目被 recall 次数 | session_search 调用记录 | 3+ 次 → 晋升到 .hermes.md |
| 工作流重复执行 3+ 步 | 连续工具调用模式 | 建议创建 skill |
| 配置文件字数变化 | 文件系统时间戳 + wc | 增长 >20% → 膨胀预警 |

### 配置健康趋势

- SOUL.md 是否在本会话被修改（变更审查）
- MEMORY.md 是否接近上限
- 项目 .hermes.md 是否缺失或继承清单不完整
- 是否有 skill 从未被触发（僵尸 skill）

## 报告格式（写入文件 + 注入 user message）

文件路径：`~/.hermes/config-advisor/reports/{project}_{date}.md`

报告示例（≤500 字符版本，用于注入）：
```
📋 配置复盘（2026-07-17 Toonflow 项目）：
- "git push 挂代理 7897" 被引用 4 次，已在 MEMORY 但建议晋升到 .hermes.md
- .hermes.md "Phase 1 架构" 段未被触及，考虑删除
- 发现 3 次重复执行 "检查端口 10588"，建议创建 skill
- MEMORY.md 89%，建议整理
```

## 用户主动触发时的同步执行

当用户说"复盘一下"，skill 直接执行分析（同步等待结果），不走 hook 异步流程：

1. 读当前项目审计日志（如有 config-advisor 在运行）
2. 读 .hermes.md 内容 + 近期 session_search 结果
3. 按上述分析维度产出报告
4. 列出建议清单，用户确认后执行

如果 config-advisor 插件未安装，skill 仍然可以手动执行分析——只是数据来源从 hook 审计日志变为 agent 自己的会话记忆（session_search）。

## 来源标注

- [PLG] Hermes 官方文档《Plugins》— on_session_finalize / pre_llm_call / hook_output_spill
- 源码验证：`turn_finalizer.py:490`（on_session_end 注释）、`gateway/slash_commands.py:206`（on_session_finalize）
