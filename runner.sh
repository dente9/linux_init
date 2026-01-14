#!/bin/bash

# --- 1. 日志配置区 ---
LOG_FILE="log.txt"

# 将后续所有的输出 (stdout & stderr) 重定向到 log.txt，同时也显示在屏幕上 (tee)
exec > >(tee -a "$LOG_FILE") 2>&1

echo "========================================"
echo "📝 日志记录已开启: $LOG_FILE"
echo "========================================"

# --- 2. 加载时间配置 ---
if [ -f "./01_time.sh" ]; then
    source ./01_time.sh
else
    echo "⚠️  警告: 未找到 01_time.sh，时间可能不准确"
fi

echo "当前时间: $(date)"
echo "准备按顺序执行初始化脚本..."
echo "----------------------------------------"

# 获取当前脚本的文件名
ME=$(basename "$0")

# --- 3. 遍历并执行脚本 ---
for script in ./*.sh; do
    script_name=$(basename "$script")

    # 排除 runner.sh (自己) 和 01_time.sh (已加载)
    if [ "$script_name" == "$ME" ] || [ "$script_name" == "01_time.sh" ]; then
        continue
    fi

    if [ -f "$script" ]; then
        echo ">>> [Running] 正在执行: $script_name"

        bash "$script"
        EXIT_CODE=$?

        if [ $EXIT_CODE -eq 0 ]; then
            echo -e "\033[32m>>> [Success] $script_name 无报错运行完毕\033[0m"
        else
            echo -e "\033[31m>>> [Error] $script_name 运行失败 (错误码: $EXIT_CODE)\033[0m"
        fi
        echo "----------------------------------------"
    fi
done

echo "✅ 所有任务结束。"