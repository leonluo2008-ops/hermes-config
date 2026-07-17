# config-advisor

Hermes 插件：配置健康监控 + 信息路由建议 + 会话复盘分析。

与 [harness-guard](https://github.com/leonluo2008-ops/hermes-plugin-harness-guard) 配套使用，互补不冲突：
- **harness-guard**：审查写入操作的正确性（阻断式，写错了拦住）
- **config-advisor**：监控配置健康度 + 建议信息路由（观察式，只建议不阻断）

## 三个 Hook

| Hook | 用途 | 延迟 |
|---|---|---|
| `pre_llm_call` | 首轮：配置健康检查 + 注入未读复盘报告；任意轮：注入排队建议 | 零延迟（纯文件 I/O）|
| `post_tool_call` | 审计记录 + 信息路由建议（排队等下轮注入） | 零延迟（纯规则）|
| `on_session_finalize` | 真实会话结束 → 异步 LLM 分析 → 写报告文件 | 异步线程，不阻塞 |

### 关键设计决策（源码验证）

- **用 `on_session_finalize` 不用 `on_session_end`**——后者是 per-turn（每轮触发 `turn_finalizer.py:490`），前者是 per-session（`/new`、`/reset`、session expiry 时触发）
- **`pre_llm_call` 加 `is_first_turn` gate**——健康检查和复盘报告只在首轮注入，避免每轮重复
- **不用 `transform_tool_result`**——harness-guard 已注册该 hook（first-wins），config-advisor 只用 `post_tool_call`（observer）
- **异步 LLM 分析**——`on_session_finalize` 先快照审计数据到局部变量，再开 daemon thread，不阻塞会话清理
- **注入 <500 字符**——避免 Hermes hook_output_spill 机制（单条 >10K 字符溢写磁盘）

## 前置条件

- Hermes Agent（需支持 plugin hooks）
- `httpx`：`pip install httpx`
- LLM API 密钥（GLM-5.2 / MiniMax / Juxin 任选其一）

## 安装

```bash
# 方式 1：通过 hermes-config 仓库一键安装
cd hermes-config && ./install.sh --plugins

# 方式 2：直接 git clone
cd ~/.hermes/plugins
git clone https://github.com/leonluo2008-ops/hermes-config.git tmp-clone
cp -r tmp-clone/config-advisor ./
rm -rf tmp-clone

# 配置 .env
cd config-advisor
cp .env.example .env
# 编辑 .env 填入 API key
```

启用插件（编辑 `~/.hermes/config.yaml`）：

```python
import yaml
p = '~/.hermes/config.yaml'
with open(p) as f: c = yaml.safe_load(f)
e = c.setdefault('plugins', {}).setdefault('enabled', [])
if 'config-advisor' not in e: e.append('config-advisor')
yaml.dump(c, open(p, 'w'), default_flow_style=False, allow_unicode=True, sort_keys=False)
```

重启 gateway：`hermes gateway restart`

## 验证

```bash
hermes plugins list
# 应看到 config-advisor | enabled | user

hermes hooks list
# 应看到 pre_llm_call / post_tool_call / on_session_finalize 注册了 config-advisor
```

## 配置

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `CONFIG_ADVISOR_PROVIDER` | `glm` | 提供商预设：glm / minimax / juxin |
| `CONFIG_ADVISOR_API_KEY` | — | API 密钥（fallback: ZAI_API_KEY 等）|
| `CONFIG_ADVISOR_BASE_URL` | 按 provider | 自定义 API 端点 |
| `CONFIG_ADVISOR_MODEL` | 按 provider | 自定义模型名 |
| `CONFIG_ADVISOR_TIMEOUT_S` | `60` | LLM 分析超时 |
| `CONFIG_ADVISOR_DISABLE` | — | 设为 `1` 禁用插件 |

## 与 harness-guard 共存

两个插件同时运行，互不干扰：

| 维度 | harness-guard | config-advisor |
|---|---|---|
| hook | post_tool_call + transform_tool_result | pre_llm_call + post_tool_call + on_session_finalize |
| 交互 | 阻断（返回 error JSON）| 建议（注入 advice）|
| LLM 调用 | 同步（写操作时 10-20s）| 异步（会话结束时后台线程）|
| 数据 | 审计日志（in-memory deque）| 审计日志（独立 deque）+ 复盘报告（文件）|

## 配套 Skill

[hermes-config-organization](https://github.com/leonluo2008-ops/hermes-config/tree/main/hermes-config-organization) v3+ 的"配置协作协议"段定义了插件的行为规范。

## License

MIT
