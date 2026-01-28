#!/bin/bash
set -e
set -u
set -o pipefail

# 1. 环境与权限检查
if [[ $EUID -ne 0 ]]; then
   echo -e "\033[31m[错误]\033[0m 必须使用 root 权限运行此脚本！"
   exit 1
fi

if grep -q "Ubuntu\|Debian" /etc/issue; then
    PM="apt-get"
elif grep -q "CentOS" /etc/redhat-release; then
    PM="yum"
else
    echo "不支持的系统类型。" && exit 1
fi

if [[ ! -d /run/systemd/system ]]; then
    echo "不支持的初始化系统，本脚本仅支持 systemd。" && exit 1
fi

# 2. 依赖检测函数
check_dependencies() {
    echo "开始检测依赖..."
    # 更新包索引
    $PM update -y > /dev/null

    # 检查 Python3
    if ! command -v python3 &> /dev/null; then
        $PM install -y python3
    fi

    # 检查 pip3
    if ! python3 -m pip --version &> /dev/null; then
        $PM install -y python3-pip || $PM install -y python-pip
    fi

    # 检查 tar 和 curl
    for pkg in tar curl; do
        if ! command -v $pkg &> /dev/null; then
            $PM install -y $pkg
        fi
    done
}

# check_dependencies

# 3. 下载与解压
REPO="mhdy2233/archive-at-home" # 请替换为真实的仓库名
TARGET_DIR="/etc/archive-at-home"
FILE_NAME="archive-at-home.tar.gz"

echo "正在获取最新版本..."
# 获取 release 里的第一个 browser_download_url (假设是 tar.gz)
DOWNLOAD_URL=$(curl -s https://api.github.com/repos/$REPO/releases/latest | grep "tarball_url" | cut -d '"' -f 4 | head -n 1)

if [ -z "$DOWNLOAD_URL" ]; then
    echo -e "\033[31m[错误]\033[0m 无法获取下载链接。请检查 REPO 变量或网络。"
    echo "API 响应内容: $RESPONSE"
    exit 1
fi

wget -O "$FILE_NAME" "$DOWNLOAD_URL"

# 创建目标目录
mkdir -p "$TARGET_DIR"

echo "正在解压到 $TARGET_DIR..."
# --strip-components=1 可以去掉压缩包里多余的一层文件夹（如果是源码包很有用）
if tar -zxf "$FILE_NAME" -C "$TARGET_DIR" --strip-components=1; then
    rm "$FILE_NAME"
else
    echo "解压失败！" && exit 1
fi

# 4. 安装 Python 依赖
PY_VERSION=$(python3 -c 'import sys; print(sys.version_info.minor)')

if (( PY_VERSION >= 11 )); then
    # 添加 --ignore-installed 避免卸载系统自带包冲突
    python3 -m pip install -r "$TARGET_DIR/client/requirements.txt" --break-system-packages --ignore-installed
else
    python3 -m pip install -r "$TARGET_DIR/client/requirements.txt" --ignore-installed
fi

# 5. 交互配置
echo "--- 请输入配置信息 ---"
read -p "ipb_member_id: " ipb_member_id
read -p "ipb_pass_hash: " ipb_pass_hash
read -p "igneous: " igneous
read -p "每日最大GP消耗 [默认-1]: " max_gp_cost
max_gp_cost=${max_gp_cost:--1}
read -p "是否使用代理 (默认无, 如 http://127.0.0.1:8787): " proxy
read -p "端口 [默认4655]: " port
max_gp_cost=${max_gp_cost:-4655}

cat <<EOF > "$TARGET_DIR/client/config/config.yaml"
ehentai:
  cookies: ipb_member_id=$ipb_member_id; ipb_pass_hash=$ipb_pass_hash; igneous=$igneous
  max_GP_cost: $max_gp_cost
port: "$port"
proxy:
  https: "$proxy"
EOF

# 6. 创建 Systemd 服务
APP_NAME="archive-at-home"
APP_PATH="$TARGET_DIR/client/main.py"

cat <<EOF > /etc/systemd/system/${APP_NAME}.service
[Unit]
Description=Archive at Home Client
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$TARGET_DIR/client
ExecStart=$(command -v python3) $APP_PATH
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 7. 启动服务
systemctl daemon-reload
systemctl enable --now ${APP_NAME}

if systemctl is-active --quiet ${APP_NAME}; then
    local_ipv4=$(ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127.0.0.1' | head -n 1)
    local_ipv6=$(ip -6 addr show | grep -oP '(?<=inet6\s)[\da-f:]+' | grep -v '::1' | grep -v '^fe80' | head -n 1)
    echo -e "\033[32m[成功]\033[0m 服务 $APP_NAME 已启动！\nhttp://$local_ipv4:$port\nhttp://[$local_ipv6]:$port"
else
    echo -e "\033[31m[失败]\033[0m 服务未正常运行，请执行 'journalctl -u $APP_NAME' 查看原因。"
fi