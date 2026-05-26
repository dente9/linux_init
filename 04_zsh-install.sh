#!/bin/bash
# ==============================================
# WSL/Linux 通用 Zsh 部署脚本（强校验修复版）
# ==============================================

# ===================== 【顶置配置区 - 仅修改这里】 =====================
RESOURCE_DIR="./resource"
OMZ_GIT_URL="https://github.com/ohmyzsh/ohmyzsh.git"
OMZ_DIR_NAME="ohmyzsh"

declare -A PLUGIN_MAP=(
  [zsh-autosuggestions]="https://github.com/zsh-users/zsh-autosuggestions.git"
  [zsh-syntax-highlighting]="https://github.com/zsh-users/zsh-syntax-highlighting.git"
)

ENABLED_PLUGINS="git z zsh-autosuggestions zsh-syntax-highlighting"

# ==========================================================================
# 追加到 .zshrc 末尾的自定义配置区（可在此处自由添加 aliases, 环境变量等）
# ==========================================================================
read -r -d '' CUSTOM_ZSHRC_CONTENT << 'EOF'
# --- CUSTOM CONFIG START ---
# 强化版 ls
alias ls='ls --color=auto --group-directories-first -v -x'
alias ll='ls -l --color=auto --group-directories-first -v'

# 你可以在下方继续追加其他配置...

# --- CUSTOM CONFIG END ---
EOF
# ==========================================================================

if [ $# -gt 0 ]; then
  PULL_ONLY=true
else
  PULL_ONLY=false
fi

ZSH_HOME="$HOME/.oh-my-zsh"
ZSH_PLUGIN_DEST="$ZSH_HOME/custom/plugins"
# ==========================================================================

if ! command -v git &> /dev/null; then
  echo "[ERROR] 请先安装 git"
  exit 1
fi

# 1. 处理本地资源 resource
echo "[INFO] ============ 1. 检查并处理本地资源 ============"
mkdir -p "${RESOURCE_DIR}"

# 处理 OhMyZsh
if [[ ! -d "${RESOURCE_DIR}/${OMZ_DIR_NAME}" ]]; then
  echo "[INFO] 正在拉取 Oh My Zsh..."
  # 去除 2>/dev/null，增加失败退出机制
  if ! git clone --depth=1 "${OMZ_GIT_URL}" "${RESOURCE_DIR}/${OMZ_DIR_NAME}"; then
    echo "[ERROR] Oh My Zsh 拉取失败，请检查网络连接！"
    exit 1
  fi
  echo "[OK] Oh My Zsh 拉取完成"
else
  echo "[OK] 复用了资源：Oh My Zsh 源码已存在"
fi

# 处理插件
for name in "${!PLUGIN_MAP[@]}"; do
  if [[ ! -d "${RESOURCE_DIR}/${name}" ]]; then
    echo "[INFO] 正在拉取插件：$name..."
    if ! git clone --depth=1 "${PLUGIN_MAP[$name]}" "${RESOURCE_DIR}/${name}"; then
      echo "[ERROR] 插件 $name 拉取失败，请检查网络连接！"
      exit 1
    fi
    echo "[OK] 插件 $name 拉取完成"
  else
    echo "[OK] 复用了资源：插件 $name 已存在"
  fi
done

if [[ "${PULL_ONLY}" == "true" ]]; then
  echo "[OK] ============ 资源拉取完毕（仅拉取模式） ============"
  exit 0
fi

# 2. 安装 Zsh
echo "[INFO] ============ 2. 安装 Zsh ============"
sudo apt update -y && sudo apt install -y zsh
echo "[OK] Zsh 安装完成"

# 3. 部署 OhMyZsh
echo "[INFO] ============ 3. 部署 Oh My Zsh ============"
if [[ ! -d "${RESOURCE_DIR}/${OMZ_DIR_NAME}" ]]; then
  echo "[ERROR] 致命错误：找不到本地资源目录 ${RESOURCE_DIR}/${OMZ_DIR_NAME}，停止部署。"
  exit 1
fi

if [[ ! -d "${ZSH_HOME}" ]]; then
  cp -r "${RESOURCE_DIR}/${OMZ_DIR_NAME}" "${ZSH_HOME}"
  echo "[OK] Oh My Zsh 部署完成"
else
  echo "[WARN] Oh My Zsh 已部署至 $ZSH_HOME"
fi

# 4. 部署插件
echo "[INFO] ============ 4. 部署插件 ============"
mkdir -p "${ZSH_PLUGIN_DEST}"
for name in "${!PLUGIN_MAP[@]}"; do
  src="${RESOURCE_DIR}/${name}"
  dest="${ZSH_PLUGIN_DEST}/${name}"

  if [[ ! -d "${src}" ]]; then
    echo "[ERROR] 致命错误：找不到插件资源 ${src}，停止部署。"
    exit 1
  fi

  if [[ ! -d "${dest}" ]]; then
    cp -r "${src}" "${dest}"
    echo "[OK] 部署插件至目标路径：$name"
  else
    echo "[WARN] 目标路径已存在插件：$name"
  fi
done

# 5. 配置 .zshrc
echo "[INFO] ============ 5. 配置插件及环境 ============"
if [[ ! -f "$HOME/.zshrc" ]]; then
  if [[ -f "${ZSH_HOME}/templates/zshrc.zsh-template" ]]; then
    cp "${ZSH_HOME}/templates/zshrc.zsh-template" "$HOME/.zshrc"
  else
    echo "[ERROR] 找不到模板文件 ${ZSH_HOME}/templates/zshrc.zsh-template"
    exit 1
  fi
fi

sed -i.bak "s/^plugins=(.*)/plugins=(${ENABLED_PLUGINS})/" "$HOME/.zshrc"
rm -f ~/.zshrc.bak

# 追加自定义配置（防重复检查）
if ! grep -q "# --- CUSTOM CONFIG START ---" "$HOME/.zshrc"; then
  echo "" >> "$HOME/.zshrc"
  echo "$CUSTOM_ZSHRC_CONTENT" >> "$HOME/.zshrc"
  echo "[OK] 自定义配置区内容已追加至 .zshrc"
else
  echo "[WARN] 检测到 .zshrc 中已存在自定义配置，跳过追加"
fi

# 6. 修复 Docker 补全报错 + 设置默认 shell
echo "[INFO] ============ 6. 最终配置 ============"
chsh -s "$(which zsh)"
sudo rm -f /usr/share/zsh/vendor-completions/_docker 2>/dev/null

echo "[OK] ============ 部署完成！重启终端生效 ============"