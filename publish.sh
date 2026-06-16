#!/usr/bin/env bash
# DeliverHQ npm 一键发布脚本
# 前置：你已 `npm login`（npm whoami 能出用户名）
# 用法：bash publish.sh
set -e

cd "$(dirname "$0")"
NAME=$(node -p "require('./package.json').name")
VER=$(node -p "require('./package.json').version")

echo "==================================================="
echo "  DeliverHQ 发布: ${NAME}@${VER}"
echo "==================================================="

# 1. 登录检查
echo "[1/5] 检查登录状态..."
if ! WHO=$(npm whoami 2>/dev/null); then
  echo "  ✗ 未登录 npm。请先执行：npm login"
  exit 1
fi
echo "  ✓ 已登录为: $WHO"

# 2. 包名占用检查
echo "[2/5] 检查包名是否可用..."
if npm view "$NAME" version >/dev/null 2>&1; then
  EXIST=$(npm view "$NAME" version 2>/dev/null)
  echo "  ⚠ 包名 ${NAME} 已存在（最新 ${EXIST}）。"
  echo "    若不是你的包，请改 package.json 的 name 为 @${WHO}/deliverhq 后重跑（scoped 需 --access public）。"
  read -r -p "    继续尝试发布？[y/N] " ans
  [ "$ans" = "y" ] || exit 1
fi

# 3. dry-run 预检
echo "[3/5] dry-run 预检..."
npm publish --dry-run >/dev/null 2>&1 && echo "  ✓ dry-run 通过" || { echo "  ✗ dry-run 失败"; npm publish --dry-run; exit 1; }

# 4. 正式发布
echo "[4/5] 正式发布..."
if [[ "$NAME" == @*/* ]]; then
  npm publish --access public
else
  npm publish
fi
echo "  ✓ 已发布 ${NAME}@${VER}"

# 5. 全新目录真实安装验证
echo "[5/5] 全新目录验证 npx 安装..."
TMP=$(mktemp -d)
( cd "$TMP" && npx -y "${NAME}@${VER}" init --yes >/dev/null 2>&1 && npx -y "${NAME}@${VER}" doctor 2>&1 | grep -E "通过:|selftest" )
rm -rf "$TMP"

echo ""
echo "==================================================="
echo "  ✅ 发布完成！用户现在可以："
echo "     npx ${NAME} init"
echo "     npx ${NAME} doctor"
echo "  查看: https://www.npmjs.com/package/${NAME}"
echo "==================================================="
