#!/bin/bash
# ============================================
# 开发机 → 测试服务器 部署脚本
# 使用方式: cd ~/data-platform-test && bash scripts/deploy-to-test.sh
# 加 --force 参数强制全量重建（依赖有变化时用）
# ============================================
set -e

TEST_HOST="192.168.1.3"
TEST_USER="root"
TEST_DIR="/opt/data-platform-mvp"
SSH_KEY="$HOME/.ssh/test_server_key"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FORCE_REBUILD="${1:-}"

echo "=========================================="
echo "  开发机 → 测试服务器 部署"
echo "=========================================="

# 1. 确保在 test 分支
cd "$PROJECT_DIR"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "test" ]; then
    echo "错误: 当前分支是 $CURRENT_BRANCH，请切换到 test 分支"
    exit 1
fi

# 2. 拉取最新代码
echo "[1/4] 拉取 test 分支最新代码..."
git pull origin test

# 3. 同步代码到测试服务器（rsync 只传差异，通常几秒）
echo "[2/4] 同步代码到测试服务器 ($TEST_HOST)..."
rsync -az --delete \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='dist' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='*.pyc' \
    --exclude='portal/frontend/dist' \
    --exclude='portal/backend/.venv' \
    --exclude='drivers' \
    --exclude='datax' \
    --exclude='.env' \
    -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
    "$PROJECT_DIR/" \
    "$TEST_USER@$TEST_HOST:$TEST_DIR/"

# 4. 构建并重启（利用 Docker 层缓存，只有变化的层才重建）
echo "[3/4] 构建并启动服务..."
BUILD_ARGS=""
if [ "$FORCE_REBUILD" = "--force" ]; then
    echo "  强制全量重建（--force 模式）"
    BUILD_ARGS="--no-cache"
fi

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$TEST_USER@$TEST_HOST" "
    cd $TEST_DIR

    # 只重建前端和后端镜像（利用层缓存：依赖层不变则跳过）
    docker compose build $BUILD_ARGS portal-frontend portal-backend

    # 滚动重启：先停旧容器，再启新容器（保留 mysql/redis/ds 不重启）
    docker compose stop portal-frontend portal-backend nginx 2>/dev/null || true
    docker compose up -d

    echo '等待服务就绪...'
    for i in \$(seq 1 15); do
        if curl -sf http://localhost:8888/api/auth/me > /dev/null 2>&1 || \
           curl -sf http://localhost:8888/ > /dev/null 2>&1; then
            echo '服务已就绪'
            break
        fi
        echo \"  等待中... \${i}/15\"
        sleep 2
    done

    echo ''
    echo '服务状态:'
    docker compose ps --format 'table {{.Name}}\t{{.Status}}\t{{.Ports}}'
"

echo ""
echo "=========================================="
echo "  部署完成"
echo "=========================================="
echo "访问地址: http://$TEST_HOST:8888"
echo ""
echo "如需强制全量重建（依赖变化时）:"
echo "  bash scripts/deploy-to-test.sh --force"
echo ""
echo "验证通过后，将 test 合并到 dev:"
echo "  git checkout dev && git merge test && git push origin dev"
echo "=========================================="
