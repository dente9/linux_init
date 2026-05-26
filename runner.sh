#!/bin/bash

# --- 1. 日志配置区 ---
LOG_FILE="log.txt"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "========================================"
echo "日志记录已开启: $LOG_FILE"
echo "========================================"

# --- 2. 加载时间配置 ---
if [ -f "./01_time.sh" ]; then
    source ./01_time.sh
else
    echo "[WARN] 未找到 01_time.sh，时间可能不准确"
fi

echo "当前时间: $(date)"
echo "----------------------------------------"

ME=$(basename "$0")

# --- 3. 收集并匹配要执行的任务 ---
declare -a RAW_TASKS

for script in ./*.sh; do
    [ -e "$script" ] || continue

    script_name=$(basename "$script")

    if [ "$script_name" == "$ME" ] || [ "$script_name" == "01_time.sh" ]; then
        continue
    fi

    # 匹配规则：至少一个数字开头，紧接着下划线
    if [[ "$script_name" =~ ^[0-9]+_ ]]; then
        RAW_TASKS+=("$script")
    fi
done

# --- 4. 严格按数字大小排序 ---
declare -a TASKS_TO_RUN
if [ ${#RAW_TASKS[@]} -gt 0 ]; then
    # 使用 sort -V (版本排序) 确保 10_ 排在 2_ 后面
    readarray -t TASKS_TO_RUN < <(printf "%s\n" "${RAW_TASKS[@]}" | sort -V)
fi

# --- 5. 打印任务清单 ---
echo "即将按以下顺序执行任务:"
if [ ${#TASKS_TO_RUN[@]} -eq 0 ]; then
    echo "[INFO] 未匹配到任何符合要求 (数字_开头) 的任务脚本。"
    exit 0
fi

for task in "${TASKS_TO_RUN[@]}"; do
    echo " - $(basename "$task")"
done
echo "----------------------------------------"

# --- 6. 顺序执行任务 ---
for script in "${TASKS_TO_RUN[@]}"; do
    script_name=$(basename "$script")

    echo ">>> [Running] 正在执行: $script_name"

    bash "$script"
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo ">>> [Success] $script_name 无报错运行完毕"
    else
        echo ">>> [Error] $script_name 运行失败 (错误码: $EXIT_CODE)"
    fi
    echo "----------------------------------------"
done

echo "所有任务结束。"