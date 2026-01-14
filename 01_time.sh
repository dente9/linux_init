#!/bin/bash

# ==========================================
# 脚本名称: time.sh
# 作用: 初始化系统时区及基础环境
# ==========================================

TARGET_TZ="CST-8"
BASHRC="$HOME/.bashrc"

echo "[-] 正在检查时区设置..."

# 1. 检查 .bashrc 是否已经包含配置，避免重复写入
if grep -q "export TZ='$TARGET_TZ'" "$BASHRC"; then
    echo "[!] .bashrc 中已存在时区配置，跳过写入。"
else
    echo "export TZ='$TARGET_TZ'" >> "$BASHRC"
    echo "[+] 已将时区配置写入 $BASHRC"
fi

# 2. 立即在当前 Shell 生效（不仅是写入文件，还要让当前脚本感知）
export TZ="$TARGET_TZ"

# 3. 验证
CURRENT_DATE=$(date)
echo "[+] 当前系统时间: $CURRENT_DATE"
