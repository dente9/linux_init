#!/bin/bash

# 获取脚本当前所在目录，确保无论在哪里运行脚本都能找到 tmux/tmux.conf
BASE_DIR=$(cd "$(dirname "$0")"; pwd)
SRC_CONF="${BASE_DIR}/tmux/tmux.conf"
DEST_CONF="$HOME/.tmux.conf"

echo ">>> [02_tmux.sh] 开始安装 Tmux..."

# 1. 安装 tmux
apt-get update && apt-get install -y tmux

# 2. 处理配置文件
if [ -f "$SRC_CONF" ]; then
    # 复制文件
    cp -f "$SRC_CONF" "$DEST_CONF"

    # 【关键步骤】格式修正
    # 使用 sed 去除文件末尾可能存在的 Windows 回车符 (\r)，防止 tmux 报错 "unknown command"
    sed -i 's/\r$//' "$DEST_CONF"

    echo ">>> [02_tmux.sh] 配置已加载并修正格式: $DEST_CONF"
else
    echo ">>> [Warn] 未找到 $SRC_CONF (在路径 $BASE_DIR 下)，跳过配置。"
fi