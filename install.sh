#!/bin/bash
# hermes-config 套件安装脚本
# 用法: ./install.sh [--plugins]
#
# 不加参数：只安装 skills
# --plugins：同时安装 config-advisor 插件（需要先安装 skills）

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="${HERMES_SKILLS_DIR:-$HOME/.hermes/skills}"
PLUGINS_DIR="${HERMES_PLUGINS_DIR:-$HOME/.hermes/plugins}"

echo "hermes-config 套件安装"
echo "  Skills  → $SKILLS_DIR"
[ "$1" = "--plugins" ] && echo "  Plugins → $PLUGINS_DIR"
echo ""

# ── 1. 安装 skills ──────────────────────────────────────────

mkdir -p "$SKILLS_DIR"

for skill in hermes-config-organization hermes-md-init; do
    if [ -d "$REPO_DIR/$skill" ]; then
        cp -r "$REPO_DIR/$skill" "$SKILLS_DIR/"
        echo "✓ $skill"
    fi
done

# ── 2. 安装插件（显式 opt-in） ─────────────────────────────

if [ "$1" = "--plugins" ]; then
    # 检查 skill 是否已安装
    if [ ! -f "$SKILLS_DIR/hermes-config-organization/SKILL.md" ]; then
        echo "❌ 需要先安装 hermes-config-organization skill"
        exit 1
    fi

    mkdir -p "$PLUGINS_DIR"
    cp -r "$REPO_DIR/config-advisor" "$PLUGINS_DIR/"
    echo "✓ config-advisor (plugin)"

    echo ""
    echo "⚠️  插件已安装，需手动启用："
    echo "    在 config.yaml 的 plugins.enabled 列表添加 'config-advisor'"
    echo "    然后重启 gateway: hermes gateway restart"
    echo ""
    echo "    或用 Python 安全编辑："
    echo '    python3 -c "'
    echo "    import os, yaml"
    echo "    p = os.path.expanduser('~/.hermes/config.yaml')"
    echo "    with open(p) as f: c = yaml.safe_load(f)"
    echo "    e = c.setdefault('plugins', {}).setdefault('enabled', [])"
    echo "    if 'config-advisor' not in e: e.append('config-advisor')"
    echo '    yaml.dump(c, open(p,"w"), default_flow_style=False, allow_unicode=True, sort_keys=False)'
    echo '    "'
fi

echo ""
echo "安装完成。"
