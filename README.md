# hermes-config

Hermes Agent 配置管理 —— 本机唯一负责"Hermes 怎么配置"的 skill 仓库。

## 当前结构

### `hermes-config-hub` 分支（活跃开发）

**Hermes 配置专员** —— 合并自 5 个旧 skill 的统一配置入口：

| 来源 skill | 迁移到 hub 的章节 |
|---|---|
| hermes-config-troubleshooting | §7 Toolset / §8 Token / §9 平台诊断 / §10 MoA |
| hermes-config-organization | §1 配置分层规范（SOUL / .hermes.md / MEMORY）|
| provider-config-standard | §11 项目级 Provider 管理 |
| hermes-slash-commands | §12 斜杠命令 |
| hermes-md-init | §13 .hermes.md 初始化 |
| hermes-multi-agent（抽取）| §2 Model / §3 Delegation / §4 Fallback / §5 Profile / §6 Gateway |

14 个章节 + 5 个 references，覆盖：
- 配置分层规范（SOUL.md / .hermes.md / MEMORY.md 三层）
- Model 与 Provider 配置（主力模型切换、base_url 陷阱）
- **Delegation 与子 Agent 模型**（3 种指定子 agent 模型的方式 + 实战案例）
- Fallback 模型链 / Profile 管理 / Gateway 管理
- Toolset 配置 / Token 与密钥 / 平台诊断 5 步流程
- MoA / 项目级 Provider 管理 / 斜杠命令 / .hermes.md 初始化 / Config 改动铁律

触发词采用角色化命名：`Hermes 配置专员`、`让配置专员检查`、`配置健康检查`。

### `main` 分支（历史保留）

| 组件 | 说明 |
|---|---|
| `hermes-config-organization/` | 三层配置架构规范（已合并到 hub §1，此为历史版本）|
| `hermes-md-init/` | .hermes.md 初始化（已合并到 hub §13，此为历史版本）|
| `config-advisor/` | 配置自检插件（自动执行配置健康检查、信息路由建议）|
| `install.sh` | 同步到运行目录的安装脚本 |

## 开发说明

> 本仓库是**开发仓库**，不是运行目录。运行时 Hermes 从 `~/.hermes/skills/hermes-config-hub/` 加载。

**修改 hub 的正确流程**：
1. 在本仓库改 `SKILL.md` 或 `references/` → `git commit && git push`
2. 同步到运行目录：`cp -r hermes-config-hub/ ~/.hermes/skills/`
3. 外部终端 `hermes gateway restart` 生效

## CHANGELOG

- **2026-07-24**：创建 hermes-config-hub，合并 5 个配置 skill 为统一入口。新分支 `hermes-config-hub`。
- **2026-07-18**：初始版本（hermes-config-organization + hermes-md-init + config-advisor）。
