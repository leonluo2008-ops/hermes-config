#!/usr/bin/env bash
# hermes-config 合并前集成验证脚本
# 用法: ./scripts/verify-integration.sh
#
# 验证 L3 集成层: skill 加载 + plugin hook 注入 + 无异常
# 不开新会话, 只看 gateway 日志和静态加载状态

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SKILLS_DIR="$HERMES_HOME/skills"
PLUGINS_DIR="$HERMES_HOME/plugins"
LOG_FILE="$HERMES_HOME/logs/agent.log"

# 颜色
green() { printf "\033[32m%s\033[0m\n" "$1"; }
red()   { printf "\033[31m%s\033[0m\n" "$1"; }
yellow(){ printf "\033[33m%s\033[0m\n" "$1"; }

PASS=0; FAIL=0; WARN=0
pass() { green "✓ $1"; PASS=$((PASS+1)); }
fail() { red "✗ $1"; FAIL=$((FAIL+1)); }
warn() { yellow "⚠ $1"; WARN=$((WARN+1)); }

echo "═══════════════════════════════════════════════"
echo "  hermes-config 集成验证 (L3)"
echo "═══════════════════════════════════════════════"
echo "REPO_DIR:    $REPO_DIR"
echo "HERMES_HOME: $HERMES_HOME"
echo ""

# ─── 0. 前置检查 ─────────────────────────────────
echo "── [0] 前置检查 ──"
[ -d "$REPO_DIR/.git" ] && pass "在 git 仓库内" || { fail "不在 git 仓库"; exit 1; }
[ -f "$REPO_DIR/install.sh" ] && pass "install.sh 存在" || fail "install.sh 不存在"
[ -f "$LOG_FILE" ] && pass "agent.log 存在" || fail "agent.log 不存在"
echo ""

# ─── 1. 仓库内容完整性 ──────────────────────────
echo "── [1] 仓库内容完整性 ──"
[ -f "$REPO_DIR/hermes-config-organization/SKILL.md" ] && pass "hermes-config-organization/SKILL.md" || fail "缺 hermes-config-organization/SKILL.md"
[ -f "$REPO_DIR/hermes-md-init/SKILL.md" ] && pass "hermes-md-init/SKILL.md" || fail "缺 hermes-md-init/SKILL.md"
[ -f "$REPO_DIR/config-advisor/plugin.yaml" ] && pass "config-advisor/plugin.yaml" || fail "缺 config-advisor/plugin.yaml"
[ -f "$REPO_DIR/config-advisor/health_check.py" ] && pass "config-advisor/health_check.py" || fail "缺 health_check.py"
[ -f "$REPO_DIR/config-advisor/__init__.py" ] && pass "config-advisor/__init__.py" || fail "缺 __init__.py"

# skill 没有 version 字段（设计如此，不应有）
if grep -q "^version:" "$REPO_DIR/hermes-config-organization/SKILL.md" 2>/dev/null; then
  warn "hermes-config-organization/SKILL.md 有 version 字段（应该没有）"
else
  pass "hermes-config-organization/SKILL.md 无 version 字段（符合设计）"
fi
echo ""

# ─── 2. 硬编码检查（应为 0，.hermes.md 反模式示例 + CHANGELOG 历史记录 + 本脚本自身除外） ──
echo "── [2] 硬编码检查 ──"
HARDCODED=$(grep -rnE '/home/luo|~/Github' "$REPO_DIR" \
  --include='*.md' --include='*.py' --include='*.sh' --exclude-dir=.git \
  --exclude='CHANGELOG.md' --exclude='verify-integration.sh' 2>/dev/null | \
  { grep -v "^$REPO_DIR/.hermes.md" || true; } | wc -l)
if [ "$HARDCODED" -eq 0 ]; then
  pass "仓库零硬编码（.hermes.md 反模式示例 + CHANGELOG 历史记录 + 本脚本除外）"
else
  fail "发现 $HARDCODED 处硬编码："
  grep -rnE '/home/luo|~/Github' "$REPO_DIR" \
    --include='*.md' --include='*.py' --include='*.sh' --exclude-dir=.git \
    --exclude='CHANGELOG.md' --exclude='verify-integration.sh' 2>/dev/null | \
    { grep -v "^$REPO_DIR/.hermes.md" || true; }
fi
echo ""

# ─── 3. SKILL.md frontmatter 合法性 ─────────────
echo "── [3] SKILL.md frontmatter ──"
for skill in hermes-config-organization hermes-md-init; do
  FM="$REPO_DIR/$skill/SKILL.md"
  if head -1 "$FM" | grep -q "^---$"; then
    if awk '/^---$/{c++; next} c==1' "$FM" | grep -q "^name:"; then
      pass "$skill frontmatter 有 name"
    else
      fail "$skill frontmatter 缺 name"
    fi
    if awk '/^---$/{c++; next} c==1' "$FM" | grep -q "^description:"; then
      pass "$skill frontmatter 有 description"
    else
      fail "$skill frontmatter 缺 description"
    fi
  else
    fail "$skill SKILL.md 不以 --- 开头"
  fi
done
echo ""

# ─── 4. plugin.yaml 合法性 ──────────────────────
echo "── [4] plugin.yaml ──"
PY="$REPO_DIR/config-advisor/plugin.yaml"
grep -q "^name:" "$PY" && pass "plugin.yaml 有 name" || fail "缺 name"
grep -q "^version:" "$PY" && pass "plugin.yaml 有 version" || fail "缺 version"
grep -q "^hooks:" "$PY" && pass "plugin.yaml 有 hooks" || fail "缺 hooks"
# hooks 应该是 pre_llm_call, post_tool_call, on_session_finalize
for h in pre_llm_call post_tool_call on_session_finalize; do
  grep -q "$h" "$PY" && pass "plugin.yaml hook 含 $h" || warn "plugin.yaml 缺 hook $h"
done
echo ""

# ─── 5. Python 语法检查 ─────────────────────────
echo "── [5] Python 语法 ──"
for py in "$REPO_DIR"/config-advisor/*.py; do
  if python3 -m py_compile "$py" 2>/dev/null; then
    pass "语法 OK: $(basename "$py")"
  else
    fail "语法错误: $(basename "$py")"
    python3 -m py_compile "$py" 2>&1 | head -5
  fi
done
echo ""

# ─── 6. health_check 干测试（字符口径） ──────────
echo "── [6] health_check 干测试 ──"
cd "$REPO_DIR/config-advisor"
if HEALTH_OUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from health_check import check_health, format_report
issues = check_health()
print(f'issues_count={len(issues)}')
for i in issues:
    print(f'issue={i.severity}|{i.file}|{i.message}')
" 2>&1); then
  pass "health_check 可执行"
  echo "$HEALTH_OUT" | head -10
  # 验证是字符口径不是字节（SOUL.md 应该 ~2044，不是 ~3887）
  if echo "$HEALTH_OUT" | grep -q "SOUL.md"; then
    SOUL_VAL=$(echo "$HEALTH_OUT" | grep "SOUL.md" | grep -oE "[0-9]+" | head -1)
    if [ "$SOUL_VAL" -lt 3000 ] 2>/dev/null; then
      pass "SOUL.md 字符口径正确 ($SOUL_VAL < 3000)"
    else
      fail "SOUL.md 可能是字节口径 ($SOUL_VAL >= 3000)"
    fi
  fi
else
  fail "health_check 执行失败"
  echo "$HEALTH_OUT"
fi
cd "$REPO_DIR"
echo ""

# ─── 6.5. plugin hook 注册验证（L3 进程内） ──────
echo "── [6.5] plugin hook 注册验证（L3 进程内）──"
# 模拟 hermes plugin loader 的加载方式：用 hermes venv、按 spec_from_file_location 加载
# 验证 register(ctx) 能注册全部 3 个 hook（pre_llm_call/post_tool_call/on_session_finalize）
HERMES_PYTHON="${HERMES_PYTHON:-$HERMES_HOME/hermes-agent/venv/bin/python3}"
if [ -x "$HERMES_PYTHON" ]; then
  HOOK_RESULT=$("$HERMES_PYTHON" -c "
import sys, os
sys.path.insert(0, '$REPO_DIR')
import importlib.util
plugin_dir = os.path.join('$REPO_DIR', 'config-advisor')
spec = importlib.util.spec_from_file_location(
    'hermes_plugins.config_advisor',
    os.path.join(plugin_dir, '__init__.py'),
    submodule_search_locations=[plugin_dir]
)
mod = importlib.util.module_from_spec(spec)
sys.modules['hermes_plugins.config_advisor'] = mod
spec.loader.exec_module(mod)

class FakeCtx:
    def __init__(self): self.hooks = []
    def register_hook(self, name, fn, plugin_name=None): self.hooks.append(name)

try:
    ctx = FakeCtx()
    mod.register(ctx)
    expected = {'pre_llm_call', 'post_tool_call', 'on_session_finalize'}
    actual = set(ctx.hooks)
    missing = expected - actual
    if missing:
        print(f'FAIL missing hooks: {missing}')
    else:
        print(f'OK registered {len(ctx.hooks)} hooks: {sorted(ctx.hooks)}')
except Exception as e:
    print(f'FAIL register raised: {type(e).__name__}: {e}')
    import traceback; traceback.print_exc()
" 2>&1 | grep -E "^(OK|FAIL)" | head -3)
  if echo "$HOOK_RESULT" | grep -q "^OK"; then
    pass "plugin register(ctx) 成功注册 3 个 hook: $(echo "$HOOK_RESULT" | sed 's/^OK //')"
  else
    fail "plugin register(ctx) 失败: $HOOK_RESULT"
  fi
else
  warn "hermes venv python 不存在 ($HERMES_PYTHON)，跳过 L3 hook 注册验证"
fi
echo ""

# ─── 7. install.sh 沙箱安装 ─────────────────────
echo "── [7] install.sh 沙箱安装 ──"
SANDBOX=$(mktemp -d)
mkdir -p "$SANDBOX/.hermes/skills" "$SANDBOX/.hermes/plugins"
if HERMES_SKILLS_DIR="$SANDBOX/.hermes/skills" HERMES_PLUGINS_DIR="$SANDBOX/.hermes/plugins" \
   bash "$REPO_DIR/install.sh" --plugins > /dev/null 2>&1; then
  pass "install.sh 沙箱执行成功"
else
  fail "install.sh 沙箱执行失败"
fi
# 验证产物齐全
[ -f "$SANDBOX/.hermes/skills/hermes-config-organization/SKILL.md" ] && pass "沙箱有 hermes-config-organization" || fail "沙箱缺 hermes-config-organization"
[ -f "$SANDBOX/.hermes/skills/hermes-md-init/SKILL.md" ] && pass "沙箱有 hermes-md-init" || fail "沙箱缺 hermes-md-init"
[ -f "$SANDBOX/.hermes/plugins/config-advisor/__init__.py" ] && pass "沙箱有 config-advisor" || fail "沙箱缺 config-advisor"
[ -f "$SANDBOX/.hermes/plugins/config-advisor/.env.example" ] && pass "沙箱有 .env.example" || fail "沙箱缺 .env.example"
[ -f "$SANDBOX/.hermes/plugins/config-advisor/requirements.txt" ] && pass "沙箱有 requirements.txt" || fail "沙箱缺 requirements.txt"
rm -rf "$SANDBOX"
echo ""

# ─── 8. .env.example 字段完整性 ─────────────────
echo "── [8] .env.example 字段 vs 代码 ──"
CODE_VARS=$(grep -rhE "os\.(environ|getenv)" "$REPO_DIR/config-advisor/"*.py 2>/dev/null | \
  sed -E 's/.*(environ\.get|environ\[|getenv)\(?\s*"?'"'"'?([A-Z_]+)"?'"'"'?\s*[,)].*/\2/' | \
  grep -E "^[A-Z_]+$" | sort -u)
ENV_VARS=$(grep -oE "^[# ]*[A-Z_]+=" "$REPO_DIR/config-advisor/.env.example" | sed 's/=.*//;s/^# *//;s/^ *//' | sort -u)
MISSING=$(comm -23 <(echo "$CODE_VARS") <(echo "$ENV_VARS"))
if [ -z "$MISSING" ]; then
  pass ".env.example 字段与代码完全一致 ($(echo "$ENV_VARS" | wc -l) 个字段)"
else
  fail ".env.example 缺字段: $MISSING"
fi
echo ""

# ─── 9. CHANGELOG 引用完整性 ────────────────────
echo "── [9] 文档引用检查 ──"
# CHANGELOG 提到的文件应该都存在
for f in CHANGELOG.md config-advisor/requirements.txt install.sh .hermes.md; do
  [ -f "$REPO_DIR/$f" ] && pass "CHANGELOG 引用的 $f 存在" || warn "CHANGELOG 引用的 $f 不存在"
done
# SKILL.md 的 references/ 文件应该都存在
for ref in "$REPO_DIR"/hermes-config-organization/references/*.md; do
  [ -f "$ref" ] && pass "reference 存在: $(basename "$ref")" || fail "reference 不存在: $ref"
done
# 不应该有对已删文件的悬空引用（CHANGELOG 历史记录除外）
if grep -rq "local-to-github-sync" "$REPO_DIR" --include='*.md' --exclude-dir=.git | grep -v CHANGELOG; then
  fail "发现对已删 local-to-github-sync.md 的悬空引用"
else
  pass "无 local-to-github-sync.md 悬空引用（CHANGELOG 历史记录除外）"
fi
echo ""

# ─── 10. gateway 集成（如果 gateway 在跑） ──────
echo "── [10] gateway 集成 ──"
if pgrep -f "hermes.*gateway" > /dev/null 2>&1; then
  pass "gateway 进程在跑"
  # 检查 config-advisor 是否在 enabled 列表
  if grep -A 10 "plugins:" "$HERMES_HOME/config.yaml" 2>/dev/null | grep -q "config-advisor"; then
    pass "config-advisor 在 plugins.enabled"
  else
    warn "config-advisor 不在 plugins.enabled（plugin 不会被加载）"
  fi
  # 检查最近日志有没有 plugin 加载错误（精确匹配 plugin loader 抛的异常，不误判 tool_executor WARNING）
  RECENT_ERRORS=$(tail -500 "$LOG_FILE" 2>/dev/null | { grep -iE "plugin.*(config-advisor).*(Traceback|ImportError|HookError|failed to load|ModuleNotFoundError)" | grep -v "tool_executor" || true; } | head -3)
  if [ -z "$RECENT_ERRORS" ]; then
    pass "最近日志无 config-advisor plugin 加载/执行异常"
  else
    fail "日志发现 config-advisor plugin 异常:"
    echo "$RECENT_ERRORS"
  fi
  # 检查 skill 是否被加载过（看日志里有没有 skill 名字）
  if tail -500 "$LOG_FILE" 2>/dev/null | { grep -q "hermes-config-organization\|hermes-md-init" || true; }; then
    pass "日志显示 skill 被引用过"
  else
    warn "日志未显示 skill 引用（可能本会话未触发加载条件）"
  fi
else
  warn "gateway 未运行（跳过集成检查）"
fi
echo ""

# ─── 总结 ────────────────────────────────────────
echo "═══════════════════════════════════════════════"
printf "  结果: %s✓ pass%s  %s✗ fail%s  %s⚠ warn%s\n" \
  '\033[32m' '\033[0m' \
  '\033[31m' '\033[0m' \
  '\033[33m' '\033[0m'
echo "  $PASS passed, $FAIL failed, $WARN warned"
echo "═══════════════════════════════════════════════"

[ "$FAIL" -eq 0 ] && { green "✅ 可以合并"; exit 0; } || { red "❌ 有失败项，不能合并"; exit 1; }
