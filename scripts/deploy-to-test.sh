#!/bin/bash
# ============================================
# 开发机 → 测试服务器 部署脚本
# 使用方式: cd ~/data-platform-test && bash scripts/deploy-to-test.sh
# ============================================
set -e

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
    exit 1
fi

# 2. 拉取最新代码
echo "[1/5] 拉取 test 分支最新代码..."
git pull origin test

# 3. 同步代码到测试服务器
echo "[2/5] 同步代码到测试服务器 ($TEST_HOST)..."
rsync -avz --delete \
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

# 4. 在测试服务器清理旧部署并重新部署
echo "[3/5] 清理旧部署容器..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$TEST_USER@$TEST_HOST" "
    cd $TEST_DIR

    # 停止并删除所有 dmp 容器（保留镜像和卷）
    echo '停止并移除旧容器...'
    docker compose down --remove-orphans 2>/dev/null || true

    # 清理已退出/残留的 dmp 容器
    docker ps -aq --filter 'name=dmp-' | xargs -r docker rm -f 2>/dev/null || true

    echo '旧容器已清理，镜像保留'
"

echo "[4/5] 构建并启动服务..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$TEST_USER@$TEST_HOST" "
    cd $TEST_DIR

    # 强制重新构建前端和后端（避免 Docker 缓存导致代码未更新）
    docker compose build --no-cache portal-frontend portal-backend

    # 启动所有服务
    docker compose up -d

    echo '等待服务启动...'
    sleep 20

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
echo "注意: 系统 nginx 运行在 80/443，DMP 使用 8888 端口"
echo ""
echo "验证通过后，将 test 合并到 dev:"
echo "  cd ~/data-platform"
echo "  git checkout dev"
echo "  git merge test"
echo "  git push origin dev"
echo "=========================================="
