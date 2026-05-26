#!/bin/bash

# ==========================================
#               超参数配置区
# ==========================================
# 1. 目标端口 (留空如 TARGET_PORT="" 则不修改任何端口配置)
TARGET_PORT="8080"

# 2. 本地公钥 (留空如 MY_PUBLIC_KEY="" 则跳过免密登录配置)
# 支持填入多个密钥，如果有多行，请用 \n 换行符隔开，或者写成多行字符串
# 尝试查看最常见的两种公钥格式
# cat ~/.ssh/id_ed25519.pub
# cat ~/.ssh/id_rsa.pub
MY_PUBLIC_KEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIP7kOk0NeUEidWJDR9TpCX/GA79wF2qiQRXvb9hBwI/h dt@DESKTOP-6D6O282"
# ==========================================

# 确保以 root 权限运行
if [ "$EUID" -ne 0 ]; then
  echo "请使用 sudo 运行此脚本"
  exit 1
fi

echo "开始执行 SSH 自动化配置..."

# ------------------------------------------
# 模块 A: 端口配置
# ------------------------------------------
if [ -n "$TARGET_PORT" ]; then
    echo -e "\n=== [A] 正在配置 SSH 端口 ($TARGET_PORT) ==="

    # 清理端口占用
    if command -v fuser &> /dev/null; then
        fuser -k ${TARGET_PORT}/tcp 2>/dev/null
    else
        PIDS=$(ss -lntp "sport = :${TARGET_PORT}" | grep -oP 'pid=\K\d+')
        if [ ! -z "$PIDS" ]; then
            echo "检测到占用 ${TARGET_PORT} 端口的 PID: $PIDS，正在强制杀死..."
            echo "$PIDS" | xargs kill -9 2>/dev/null
        fi
    fi

    # 追加端口到配置
    if grep -q "^Port ${TARGET_PORT}" /etc/ssh/sshd_config; then
        echo "sshd_config 中已存在 Port ${TARGET_PORT} 配置，跳过添加。"
    else
        echo "" >> /etc/ssh/sshd_config
        echo "Port ${TARGET_PORT}" >> /etc/ssh/sshd_config
        echo "已将 Port ${TARGET_PORT} 追加到 sshd_config。"
    fi
else
    echo -e "\n=== [A] TARGET_PORT 留空，跳过端口修改 ==="
fi

# ------------------------------------------
# 模块 B: 免密登录配置
# ------------------------------------------
if [ -n "$MY_PUBLIC_KEY" ]; then
    echo -e "\n=== [B] 正在配置公钥免密登录 ==="

    ACTUAL_USER=${SUDO_USER:-root}
    USER_HOME=$(eval echo ~$ACTUAL_USER)

    echo "识别到当前用户为: $ACTUAL_USER，家目录: $USER_HOME"

    mkdir -p "$USER_HOME/.ssh"
    chmod 700 "$USER_HOME/.ssh"

    # 写入公钥（自动去重）
    if ! grep -q "$MY_PUBLIC_KEY" "$USER_HOME/.ssh/authorized_keys" 2>/dev/null; then
        echo "$MY_PUBLIC_KEY" >> "$USER_HOME/.ssh/authorized_keys"
        echo "公钥已成功追加到 authorized_keys！"
    else
        echo "公钥已存在，跳过重复写入。"
    fi

    chmod 600 "$USER_HOME/.ssh/authorized_keys"
    chown -R "$ACTUAL_USER:$ACTUAL_USER" "$USER_HOME/.ssh"

    # 确保服务端开启了公钥验证
    sed -i -E 's/^#?PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config
else
    echo -e "\n=== [B] MY_PUBLIC_KEY 留空，跳过免密配置 ==="
fi

# ------------------------------------------
# 模块 C: 重启与验证
# ------------------------------------------
echo -e "\n=== [C] 正在重启 SSH 服务 ==="
service ssh restart 2>/dev/null || service sshd restart 2>/dev/null

if [ $? -ne 0 ]; then
    if [ -x /etc/init.d/ssh ]; then
        /etc/init.d/ssh restart
    elif [ -x /etc/init.d/sshd ]; then
        /etc/init.d/sshd restart
    fi
fi

echo -e "\n========================================="
echo "执行完毕！"
if [ -n "$TARGET_PORT" ]; then
    echo "当前监听状态:"
    ss -lntp | grep :${TARGET_PORT}
fi
echo "========================================="