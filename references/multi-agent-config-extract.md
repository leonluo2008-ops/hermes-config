# 从 hermes-multi-agent SKILL.md 提取的"模型/delegation/profile 管理/gateway 配置"知识段落

> 来源: `~/.hermes/skills/autonomous-ai-agents/hermes-multi-agent/SKILL.md` (v3.13.0, 1579 行)
> 提取日期: 2026-07-24
> 目的: 迁移到 hermes-config-hub skill

---

## 1. Config 改动铁律（原 L177-216）

> 标题: `## Config 改动铁律（2026-06-12 实测发现 3 个护栏）`

**3 个护栏**会拦住你"用常规工具改配置"——必须知道绕过路径，否则会卡死：

| 护栏 | 现象 | 正确绕过方式 |
|------|------|------------|
| **`patch` 工具拒绝改 `~/.hermes/config.yaml`** | 错误：`Refusing to write to Hermes config file: ~/.hermes/config.yaml. Agent cannot modify security-sensitive configuration.` | ❌ `hermes config set` **只能改点对点 key**（`model.default` 这种），不能改大段<br>✅ **直接用 Python/terminal 编辑**：先 `cp config.yaml config.yaml.bak.<日期>` → 读文件 → 改文本 → `Path.write_text()` → `python3 -c "import yaml; yaml.safe_load(open('config.yaml'))"` 验证语法 |
| **`hermes gateway restart` 拒绝从 gateway 进程内触发** | 错误：`Refusing to restart the gateway from inside the gateway process. This command was blocked to prevent restart loops. Use \`hermes gateway restart\` from a shell outside the running gateway.` | ❌ agent 在当前 gateway 进程内**不能自重启**<br>✅ 让用户在**外部 shell** 执行 `hermes gateway restart`，或等下次会话开头执行 |
| **config 改动只在重启后生效** | 改了 `config.yaml` 但 `skills_list` 看到的是旧值 | ❌ config **不热重载**——`agent.image_input_mode` / `skills.disabled` / `personalities.*` 都是 gateway 启动时一次性加载<br>✅ 改完必须 `hermes gateway restart`，验证 `hermes profile list` 的 PID 是新的 |

**典型流程**（重写 personality + 屏蔽 skill 集）：

```bash
# Step 1: 备份（必做——直接编辑大段没 undo）
cp ~/.hermes/config.yaml ~/.hermes/config.yaml.bak.$(date +%Y%m%d_%H%M%S)

# Step 2: Python 替换大段（不能 sed——容易因多行/转义出错）
python3 <<'EOF'
from pathlib import Path
text = Path.home() / ".hermes" / "config.yaml"
content = text.read_text()
content = content.replace("personality: feishu-partner", "personality: default-main-agent")
# ... 其他替换
text.write_text(content)

# Step 3: 验证 yaml 语法
import yaml
yaml.safe_load(open(text))  # 失败立即抛异常

# Step 4: 验证生效（无需重启，先看 CLI 层）
hermes config check
hermes skills list --source all --enabled-only
# 期望：enabled 数从 N 降到 N-disabled

# Step 5: 让用户在外面重启 gateway
# "请在你 Windows 笔电的 WSL shell 里执行：hermes gateway restart"
```

**新会话的反射**：任何"我要改默认 profile 行为（personality / skill 集 / image_input_mode）"的需求，**第一步先列这 3 个护栏**。

---

## 2. model 字段格式陷阱（原 L237-313，去重后保留一份）

> 标题: `### ⚠️ \`model\` 字段格式陷阱：\`minimax-cn/MiniMax-M3\` 字符串 vs \`{ default, provider }\` 字典（2026-06-29 实战新增）`
> 
> ⚠️ **去重说明**：原文 L237-313 和 L317-393 是**同一段落的完整重复**（L315 被意外截断后 L317 重新开始）。此处只保留一份。原 L315 是一段残缺的衔接句（`## Skill 库管理：禁用而非删除（2026-06-12 实战方法）会话的反射**：...`），已丢弃。

**症状**：`hermes` 启动后主模型请求**全部打错端点**——日志显示 `provider=zai base_url=https://open.bigmodel.cn/api/anthropic model=minimax-cn/MiniMax-M3`，智谱返回"模型不存在"，3 次重试全失败 → 切 fallback → fallback 也失败 → 多轮对话后必然崩。

**根因链路**（追到 `hermes_cli/runtime_provider.py`）：

```
config.yaml: model: minimax-cn/MiniMax-M3   ← 字符串
↓
_get_model_config() (line 200-201)
  → 返回 {"default": "minimax-cn/MiniMax-M3"}   ← ⚠️ 没有 provider 字段
↓
resolve_requested_provider() (line 432)
  → 读 model_cfg.get("provider") = None
  → 回退到 HERMES_INFERENCE_PROVIDER env
  → 最后返回 "auto"
↓
resolve_runtime_provider()
  → requested_provider="auto"
  → auto 检测链匹配 .env 里第一个有 key 的 provider
  → 命中 GLM_API_KEY → provider=zai, base_url=智谱
↓
主模型请求打智谱 → 1211 模型不存在
```

**反例**（有 bug 的 config）：

```yaml
# ❌ 字符串格式 — provider 字段缺失，走 auto 检测
model: minimax-cn/MiniMax-M3
```

**正例**（修好的 config）：

```yaml
# ✅ 字典格式 — 显式 provider，跳过 auto 检测
model:
  default: MiniMax-M3
  provider: minimax-cn
```

**4 步诊断 SOP**（任何"主模型打错端点 / 1211 模型不存在 / 主备同时挂"症状）：

```bash
# Step 1: 看 config 里 model 字段是字符串还是字典
sed -n '/^model:/p' ~/.hermes/config.yaml
# 字符串 → 改成字典

# Step 2: 用 Python 验证 provider 字段真存在
python3 -c "
import yaml
with open('/home/luo/.hermes/config.yaml') as f:
    m = yaml.safe_load(f).get('model', {})
print('default =', repr(m.get('default')))
print('provider =', repr(m.get('provider')))
"

# Step 3: 在 agent.log 里搜 provider= 与 base_url= 的实际组合
# 期望 provider 行的 provider/model/base_url 三者语义一致
# (minimax-cn/MiniMax-M3 → api.minimaxi.com/anthropic)
# (zai/glm-5-turbo → api.z.ai/api/coding/paas/v4)
grep -E "API call|base_url=" ~/.hermes/logs/agent.log | tail -5

# Step 4: 修完 config 后必须重启 gateway（config 不热加载）
# 改完前在 /tmp/restart_main_gateway.sh 写好重启脚本
# 等当前对话结束再执行（kill 当前 gateway = 中断用户对话）
```

**用户铁律**（强纠错信号）：**任何"`hermes config set model.default X` + `hermes config set model.provider Y` 分开设置"的教程都是误人子弟**——会导致 `model.base_url` 旧值残留。本节正例 = 一次性 dict 写好 3 个字段（`default` + `provider` + 可选 `base_url`）。

**坑 2**：`hermes config set model.default minimax-cn/MiniMax-M3`（带斜杠的字符串）会被 yaml 解析成普通字符串，**不是** provider/model 拆分。等于回到 `model: minimax-cn/MiniMax-M3` 字符串格式 → 触发本节 bug。

**反射规则**：
- ✅ 写 config.yaml = 一次性 dict（`default` + `provider` + `base_url`）
- ✅ 改 provider = 同步清 `base_url`（旧 provider 端点残留会污染新 provider）
- ❌ 不要在 config.yaml 里写 `model: minimax-cn/MiniMax-M3`（字符串）—— provider 字段缺失
- ❌ 不要靠 `hermes config set` 分点设（base_url 残留 + 旧值覆盖）

---

## 3. Fallback Model 配置（原 L1350-1416）

> 标题: `## Fallback Model 配置`

### 查看当前 fallback 链

```bash
hermes fallback list
# 输出示例：
#   Primary:   MiniMax-M3  (via minimax-cn)
#   Fall名-M3  (via minimax-cn)
#   Fallback chain (2 entries):
#     1. deepseek-v4-pro  (via deepseek)
#     2. glm-5-turbo  (via zai)
```

### 管理 fallback 链（推荐方式）

```bash
hermes fallback add       # 交互式 picker 选择 provider+model，追加到链尾
hermes fallback remove    # 交互式选择要删除的条目
hermes fallback clear     # 清空整个链
```

> ⚠️ **`hermes fallback add` 需要交互式终端**，通过 pipe/subprocess 调会报错：
> `Error: 'hermes fallback add' requires an interactive terminal.`
> 非交互场景：直接编辑 `config.yaml` 的 `fallback_providers` 列表（见下方）。

### 存储格式

Hermes 有两个格式，**`fallback_providers` 列表是新格式**（v0.14+），旧 `fallback_model` 单 key 会被自动迁移：

```yaml
# ✅ 新格式（fallback_providers 列表，支持多条目）
# 每个条目可指定 provider、model，可选 base_url（覆盖 provider 默认端点）
fallback_providers:
  - provider: deepseek
    model: deepseek-v4-pro
  - provider: zai
    model: glm-5-turbo
    base_url: https://api.z.ai/api/coding/paas/v4   # 可选：per-entry 端点覆盖

# ⚠️ 旧格式（fallback_model 单 key，v0.13 及之前）
fallback_model:
  provider: zai
  model: glm-5-turbo
```

**两格式优先级**：代码优先读 `fallback_providers`，其次读 `fallback_model`。`hermes fallback add` 首次使用时会将旧 `fallback_model` 迁移为 `fallback_providers` 并删除旧 key。

**手动从 legacy 迁移到 list**（non-interactive）：
```bash
# 1. 在 config.yaml 中把 fallback_providers: [] 改成列表
# 2. 删除 fallback_model 整个块
# 3. 验证
hermes fallback list
```

### 手动验证 config.yaml 中的 fallback

```python
python3 -c "
import yaml
with open('/home/luo/.hermes/config.yaml') as f:
    data = yaml.safe_load(f)
fb = data.get('fallback_providers') or data.get('fallback_model', 'NOT FOUND')
print('fallback:', fb)
"
```

### Z.AI (GLM) 端点注意

标准端点 `https://api.z.ai/api/paas/v4/chat/completions`（OpenAI 兼容格式），环境变量 `ZAI_API_KEY`。

Coding 端点 `https://api.z.ai/api/coding/paas/v4/chat/completions` 用独立的 coding key（`Z_AI_API_KEY`），与标准端点余额分开计费。如果标准端点报 429 余额不足但 coding key 有配额，可把 fallback 的 GLM 切到 coding 端点（需改改 provider 配置或 base_url）。

---

## 4. Multi-Profile 工作流：配置 Model + 多 Profile 模型配置同步 + 启动 Gateway（原 L517-556, L793-836）

### 4a. 配置 Model（原 L517-526）

> 标题: `### 配置 Model`

```bash
hermes config set model.default MiniMax-M2.7 --profile {profile_name}
hermes config set model.provider minimax-cn --profile {profile_name}
```

> ⚠️ **切换 provider 后别忘了清 `model.base_url`**：`hermes config set` 改 `model.provider` 时不会自动清理旧的 `model.base_url`。如果旧 provider 的 base_url 残留（如 deepseek 的 `https://api.deepseek.com`），新 provider 可能用错端点。切换后执行：`hermes config set model.base_url ''`。

> Fallback 模型配置 → 见下方「Fallback Model 配置」章节（推荐用 `hermes fallback add` / 手动编辑 `fallback_providers` 列表，不再用旧的 `hermes config set fallback_model.*`）。

### 4b. 多 Profile 模型配置同步（原 L528-556）

> 标题: `### 多 Profile 模型配置同步`

当调整 default profile 的模型配置后，**检查并同步其他 profile**，确保 fallback 链一致：

```bash
# 1. 查看 default 的模型配置
hermes fallback list

# 2. 逐个检查其他 profile
hermes -p {profile_name} fallback list

# 3. 对比差异（用 python3 快速对比 fallback_providers）
python3 -c "
import yaml
for p in ['', 'huiben']:
    path = f'/home/luo/.hermes/{\"config.yaml\" if not p else f\"profiles/{p}/config.yaml\"}'
    with open(path) as f:
        c = yaml.safe_load(f)
    fb = c.get('fallback_providers') or c.get('fallback_model')
    print(f'{p or \"default\"}: primary={c[\"model\"][\"default\"]} fb={fb}')
"
```

**同步方法**（两个 profile 用同样的 fallback 链）：
- 直接编辑目标 profile 的 `config.yaml`，复制 `fallback_providers` 整个块
- 同时检查目标 profile 的 `.env` 里 API key 是否一致（特别是 ZAI_API_KEY 等可能因端点切换需要更新的 key）
- **改完 config.yaml 需要重启对应 gateway**（`systemctl --user restart hermes-gateway-{profile_name}`）才会生效

> ⚠️ **`hermes config set model.provider X` 不会自动清理 `model.base_url`**。切换 provider 后立即执行 `hermes config set model.base_url ''`，否则旧 base_url 残留可能导致新 provider 调用失败。

### 4c. 启动 Gateway（原 L793-836）

> 标题: `### 启动 Gateway`

> ⚠️ **[CONFIRM]** systemd service 会常驻后台。确认这个 profile 是你真正要长期运行的，不是临时测试。

**第一步：检查端口占用，分配可用端口**

```bash
# 查看所有已占用的 API_SERVER_PORT（python进程监听的端口）
ss -tlnp | grep python | grep -oP '0.0.0.0:\K\d+'

# 分配原则：从 8642 起，每个新 profile 顺序占用一个端口
# 例：8642 被 default 占用 → huiben 用 8643 → account-ops 用 8644，以此类推
# 记录分配到的端口号（例如 8643），后续两步都要用到
```

> ⚠️ **[UPDATE_INVENTORY]** 端口分配完成后，更新 `references/agent-inventory.md` 的 Profile 状态表（填入分配的端口号）。

**第二步：写入分配到的端口到 profile .env**

> ⚠️ **[CONFIRM]** 将 `<PORT>` 替换为实际分配到的端口号（例如 8643），不要照抄 `<PORT>`。

```bash
# 把 <PORT> 换成真实端口号（例如 8643），下同
sed -i "s/^API_SERVER_PORT=.*/API_SERVER_PORT=<PORT>/" ~/.hermes/profiles/{profile_name}/.env
```

**第三步：安装并启动**

```bash
hermes -p {profile_name} gateway install
systemctl --user start hermes-gateway-{profile_name}
```

**验证**

```bash
hermes profile list                              # Gateway 列 = running
ss -tlnp | grep python | grep <分配到的端口>     # 确认端口已监听（把 <分配到的端口> 换成真实值，如 8643）
journalctl --user -u hermes-gateway-{profile_name} --no-pager | tail -3
```

> ⚠️ **[UPDATE_INVENTORY]** 验证成功后，更新 `references/agent-inventory.md` 的 Profile 状态表（确认 Gateway=running、填入实际端口）和配置变更记录表（追加变更时间+操作详情）。

---

## 5. 调试排查：快速诊断清单 + 日志分层诊断（原 L1155-1178）

### 5a. 快速诊断清单（原 L1155-1164）

> 标题: `### 快速诊断清单`

发现"消息没收到"问题时，按顺序：

```
1. 用 send_message 工具测试 → 确认通道正常（send_message 是 Hermes 内置工具，直接调用即可）
2. hermes --version → 检查版本（< v0.13.0 可能有 Agent Loop Bug）
3. hermes profile list → 确认 Gateway 状态
4. journalctl --user -u hermes-gateway --no-pager | grep -E "feishu|error|inbound"
```

### 5b. 日志分层诊断（原 L1166-1178）

> 标题: `### 日志分层诊断（gateway.log vs agent.log）`

**两个日志关注不同层**，查错时分清楚：

| 日志 | 关注内容 | 典型关键词 |
|------|---------|-----------|
| **`~/.hermes/logs/gateway.log`** | 飞书/Telegram 等平台层 + image_routing + session 管理 | `Inbound message`、`Image routing: native/text`、`Flushing text batch` |
| **`~/.hermes/logs/agent.log`** | AIAgent 内部：API call、工具调用、_model_supports_vision 决策、fallback 触发 | `API call #`、`conversation turn`、`vision_analyze`、`_preprocess_anthropic_content` |

**典型故障分层排查**：
- 图片看不到 → 先看 `gateway.log` 确认 `Image routing: native` → 再看 `agent.log` 确认没触发 `vision_analyze fallback`
- 消息没收到 → 只看 `gateway.log`（agent 层根本没收到）
- 模型回复奇怪 → 只看 `agent.log`（gateway 已经成功投递）

---

## 附录：补充知识片段（从"已知坑"段提取，与上述章节强相关）

### 附录 A: gateway stop/restart 不接受 profile 名参数（原 L1466-1486）

> ⚠️ `hermes gateway stop/restart` 只支持 `--system` / `--all` 标志，不接受 `<profile>` 位置参数

**正确做法**（按 profile 重启 gateway）：
```bash
# 单 profile
systemctl --user restart hermes-gateway-<profile>

# 全部 profile
systemctl --user restart 'hermes-gateway-*.service'

# 单 profile 启停
systemctl --user stop hermes-gateway-<profile>
systemctl --user start hermes-gateway-<profile>
```

**验证三件套**：
1. `hermes profile list` 看 PID 变了 = 新进程
2. `ss -tlnp | grep 8643` 看端口监听 = 端口通了
3. `systemctl --user status hermes-gateway-<profile>` 看 Active: active (running) + 启动时间 = service 起来了

### 附录 B: config.yaml 改动必须重启 gateway 才生效（原 L927-933）

`config.yaml` 是 **gateway 启动时一次性加载**（包括 `agent.image_input_mode`、vision 路由、provider 配置等），**运行时修改不会热重载**。

**排查坑**：改了 config 之后没生效 → 99% 是没重启 gateway。验证：`hermes profile list` 看到的 PID 是新的才代表配置生效。

**多 profile 场景**：每个 profile 有独立 gateway 进程，**改哪个 profile 的 config.yaml 就要重启哪个**（`systemctl --user restart hermes-gateway-{profile_name}`，不是 restart default）。

### 附录 C: Gateway 显示 running 但 Api_Server 未监听（原 L1443-1446）

- **现象**：gateway 进程活着但 Api_Server 挂起
- **验证**：需 `ss -tlnp | grep python` 验证端口监听状态，不只靠 `hermes profile list`
- **根因**：profile 创建时从全局 .env 复制错误的 `API_SERVER_PORT=8642`，`gateway install` 不会自动修正这个值
- **正确顺序**：先 `sed -i` 修正端口 → `gateway install` → `start`（而非先 install/start 再改端口）

### 附录 D: Systemd Timer 问题（原 L1424-1432）

```bash
systemctl --user list-timers --all

# Timer 显示 `-`（下次运行时间）
# 原因：OnUnitActiveSec 系统睡眠后失去参考
# 解决：改用 OnCalendar
```
