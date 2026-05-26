#!/bin/bash

echo ">>> [00init.sh] 开始安装 uv (Python包管理器)..."

# 使用清华源安装，速度更快，防止超时
pip install uv -i https://pypi.tuna.tsinghua.edu.cn/simple

# 验证安装
if command -v uv &> /dev/null; then
    echo ">>> uv 安装成功: $(uv --version)"

    # [新增] 获取 uv 真实路径，并软链接给 root (全局可用)
    UV_PATH=$(which uv)
    echo ">>> 正在为 sudo 环境配置软链接: $UV_PATH -> /usr/local/bin/uv"
    sudo ln -sf "$UV_PATH" /usr/local/bin/uv
else
    echo ">>> [Error] uv 安装失败"
    exit 1
fi

if ! command -v fuser &> /dev/null; then
    echo "⚠️  缺少 fuser 工具，正在补充安装 psmisc..."
    sudo apt-get update && sudo apt-get install -y psmisc
fi

sudo apt install xterm -y && resize