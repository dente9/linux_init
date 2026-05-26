#!/bin/bash

# ================= 配置区 =================
PORT=8080
INSTALL_MODE="uv"  # 可选安装模式: "uv" 或 "python"
PYPI_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"

# 统一管理安装包 (增加/删除包只需在此处修改)
PACKAGES=(
    "jupyterlab"
    "jupyter-server-proxy"
    "jupyterlab-language-pack-zh-CN"
    "jupyterlab-favorites"
    "jupyterlab-unfold"
)
# ==========================================

PYTHON_BIN=$(which python)

echo ">>> [1/4] 正在使用 $INSTALL_MODE 安装 JupyterLab 及其依赖..."

if [ "$INSTALL_MODE" = "uv" ]; then
    # 检查是否安装了uv
    if ! command -v uv &> /dev/null; then
        echo ">>> [Error] 未找到 uv 命令，请先安装 uv 或将 INSTALL_MODE 改为 python"
        exit 1
    fi
    # 使用 uv 极速安装，添加 --system 允许在全局环境安装
    uv pip install --system "${PACKAGES[@]}" -i $PYPI_MIRROR
elif [ "$INSTALL_MODE" = "python" ]; then
    $PYTHON_BIN -m pip install "${PACKAGES[@]}" -i $PYPI_MIRROR
else
    echo ">>> [Error] 未知的安装模式: $INSTALL_MODE"
    exit 1
fi

echo ">>> [2/4] 正在清理残留进程 (端口 $PORT)..."

# 1. 获取占用端口的 PID
PID=$(netstat -tulpn 2>/dev/null | grep ":$PORT " | awk '{print $7}' | cut -d'/' -f1)

# 2. 如果找到了 PID，直接强杀 (Kill -9)
if [ -n "$PID" ]; then
    echo ">>> 发现占用进程 PID: $PID，正在强杀..."
    kill -9 $PID
fi

# 3. 补充清理 (fuser)
if command -v fuser &> /dev/null; then
    fuser -k -9 $PORT/tcp > /dev/null 2>&1
fi
sleep 1

echo ">>> [3/4] 正在启动 Jupyter Lab..."
nohup $PYTHON_BIN -m jupyterlab \
    --ip=0.0.0.0 \
    --port=$PORT \
    --allow-root \
    --no-browser \
    --ServerApp.token='' \
    --ServerApp.password='' \
    --ServerApp.allow_remote_access=True > ~/jupyter_debug.log 2>&1 &

echo "------------------------------------------------"
echo "[完成] 环境修复与配置成功"
echo "[地址] 访问链接: 服务器:端口号/lab"
echo "[设置] 中文语言: 刷新页面 -> Settings -> Language -> Chinese"
echo "[代理] 代理示例: 启动端口为 N 的服务后，访问 服务器:端口号/proxy/N/"
echo "------------------------------------------------"