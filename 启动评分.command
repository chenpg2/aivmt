#!/bin/zsh
# AIVMT 教师评分启动器 —— 双击即可运行,无需懂命令行。
# 打开后会自动弹出浏览器页面;关闭本窗口即可停止服务。

export PATH="$HOME/.local/bin:/Library/TeX/texbin:$PATH"
cd "$(dirname "$0")"

PORT=8770

echo "=============================================="
echo "   AIVMT 标准化病人 —— 教师评分门户"
echo "=============================================="

# 0. 检查 uv 是否可用
if ! command -v uv >/dev/null 2>&1; then
  echo ""
  echo "❌ 没有找到 uv(Python 环境管理工具)!"
  echo "   请联系技术同事安装 uv 后,重新双击本文件。"
  echo ""
  read -k 1 "?按任意键退出..."
  exit 1
fi
echo "✓ 环境正常"

# 1. 检查端口是否被占用(可能已经开了一个评分门户)
if lsof -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  echo ""
  echo "⚠️  端口 $PORT 已被占用 —— 评分门户可能已经在运行。"
  echo "   直接为你打开页面:http://localhost:$PORT"
  open "http://localhost:$PORT"
  read -k 1 "?按任意键退出..."
  exit 0
fi

echo ""
echo "正在启动教师评分门户(首次运行需要联网下载依赖,之后完全离线)..."
echo "页面地址:http://localhost:$PORT"
echo "评分时只会看到去标识的问诊转写,不会显示系统评分或参考答案(盲评)。"
echo "用完后直接关闭本窗口即可。"
echo ""

# 2. 稍后自动打开浏览器(给服务 2 秒启动时间)
( sleep 2; open "http://localhost:$PORT" ) &

# 3. 启动门户(无需大模型;评分写入 data/faculty_ratings.csv)
uv run --extra portal python -m aivmt.faculty_portal --port $PORT
status=$?

if [ $status -ne 0 ]; then
  echo ""
  echo "❌ 门户启动失败(退出码 $status)。请把本窗口截图发给技术同事。"
  read -k 1 "?按任意键退出..."
fi
exit $status
