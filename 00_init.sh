#!/bin/bash

echo ">>> [00init.sh] 开始安装 uv (Python包管理器)..."

# 使用清华源安装，速度更快，防止超时
pip install uv -i https://pypi.tuna.tsinghua.edu.cn/simple

# 验证安装
if command -v uv &> /dev/null; then
    echo ">>> uv 安装成功: $(uv --version)"
else
    echo ">>> [Error] uv 安装失败"
    exit 1
fi

if ! command -v fuser &> /dev/null; then
    echo "⚠️  缺少 fuser 工具，正在补充安装 psmisc..."
    apt-get update && apt-get install -y psmisc
fi

sudo apt install xterm -y && resize