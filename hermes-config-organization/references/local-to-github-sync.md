# Skill 本地 → GitHub 同步工作流

> 适用于 `~/.hermes/skills/` 中的 skill 有对应 `~/Github/` 镜像仓库的场景（如 `hermes-config` suite）。

## 同步流程

### 1. 确认对应关系

```bash
# 检查本地 skill 是否有对应的 GitHub 仓库
ls ~/Github/<repo-name>/  # 对应 ~/.hermes/skills/<skill-name>/
```

已知对应关系：
- `~/.hermes/skills/hermes-config-organization/` + `~/.hermes/skills/hermes-md-init/` → `~/Github/hermes-config/`（仓库 `leonluo2008-ops/hermes-config`）

### 2. 从本地 skill 同步到 GitHub 仓库

```bash
# cp 本地最新版到镜像仓库（不软链——用户偏好实体副本）
cp -r ~/.hermes/skills/<skill-name>/SKILL.md ~/Github/<repo-name>/<skill-name>/SKILL.md
# 如有 templates/references 子目录也要同步
mkdir -p ~/Github/<repo-name>/<skill-name>/templates
cp ~/.hermes/skills/<skill-name>/templates/*.md ~/Github/<repo-name>/<skill-name>/templates/
```

### 3. 处理 rebase 冲突

远程可能有其他机器/PR 推送的改动（如通用化安装说明）。本地 skill 是权威版本（最新内容），但 README 可能需要保留远程的通用化改动。

```bash
cd ~/Github/<repo-name>
https_proxy=http://127.0.0.1:7897 git pull --rebase
# 冲突时：SKILL.md 直接用本地版本覆盖（cp），README 手工合并
cp ~/.hermes/skills/<skill-name>/SKILL.md <skill-name>/SKILL.md
git add <skill-name>/SKILL.md
# README 冲突：手工编辑保留两边合理内容
GIT_EDITOR=true git rebase --continue
```

### 4. 推送

```bash
https_proxy=http://127.0.0.1:7897 git push
```

### 5. 验证远程

```bash
git log --oneline -3
find . -not -path './.git/*' -type f | sort
```

## Pitfalls

1. **不要软链 skill 目录**——用户明确反对，用 `cp -r` 实体副本
2. **README 的通用性改动优先保留远程版本**——远程 PR 可能做了多平台适配（如 hermes-config PR #1 加了 Claude Code/OpenClaw/Cursor 安装说明），本地版只关心 Hermes
3. **git pull --rebase 遇到 dumb terminal**——`GIT_EDITOR=true git rebase --continue` 绕过 EDITOR 要求
4. **冲突标记检查**——push 前 `grep -c '<<<<<<\|>>>>>>\|======='` 确认无残留
