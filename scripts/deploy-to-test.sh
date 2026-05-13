#!/bin/bash
# ============================================
# 开发机 → 测试服务器 部署脚本
# 使用方式: cd ~/data-platform-test && bash scripts/deploy-to-test.sh
# ============================================
set -e

# 配置
TEST_HOST="192.168.1.3"
TEST_USER="root"
TEST_DIR="/opt/data-platform-mvp"
SSH_KEY="$HOME/.ssh/test_server_key"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=========================================="
echo "  开发机 → 测试服务器 部署"
echo "=========================================="

# 1. 确保在 test 分支
cd "$PROJECT_DIR"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "test" ]; then
    echo "错误: 当前分支是 $CURRENT_BRANCH，请切换到 test 分支"
    echo "  git checkout test"
    exit 1
fi

# 2. 拉取最新代码
echo "[1/4] 拉取 test 分支最新代码..."
git pull origin test

# 3. 同步代码到测试服务器 (排除不需要的文件)
echo "[2/4] 同步代码到测试服务器 ($TEST_HOST)..."
rsync -avz --delete \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='dist' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='*.pyc' \
    --exclude='portal/frontend/dist' \
    --exclude='portal/backend/.venv' \
    -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
    "$PROJECT_DIR/" \
    "$TEST_USER@$TEST_HOST:$TEST_DIR/"

# 4. 在测试服务器构建并部署
echo "[3/4] 测试服务器构建并部署..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$TEST_USER@$TEST_HOST" "
    cd $TEST_DIR
    echo '停止旧容器...'
    docker compose down portal-frontend portal-backend nginx 2>/dev/null || true

    echo '构建并启动服务...'
    docker compose up -d --build portal-frontend portal-backend nginx

    echo '等待服务就绪...'
    sleep 10

    echo '服务状态:'
    docker compose ps --format 'table {{.Name}}\t{{.Status}}'
"

echo ""
echo "=========================================="
echo "  部署完成"
echo "=========================================="
echo "测试地址: http://$TEST_HOST"
echo ""
echo "验证通过后，将 test 合并到 dev:"
echo "  cd ~/data-platform"
echo "  git checkout dev"
echo "  git merge test"
echo "  git push origin dev"
echo "=========================================="
