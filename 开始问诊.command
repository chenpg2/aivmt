#!/bin/zsh
# AIVMT 采集日启动器 —— 双击即可运行,无需懂命令行。
# 每次运行 = 一段问诊。结束后可直接再开下一段。

export PATH="$HOME/.local/bin:/Library/TeX/texbin:$PATH"
cd "$(dirname "$0")"

echo "=============================================="
echo "   AIVMT 标准化病人 —— 问诊采集"
echo "=============================================="

# 0. 检查本地 AI 是否在运行
if ! curl -s --max-time 3 http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo ""
  echo "❌ 本地 AI(Ollama)没有运行!"
  echo "   请先打开 Ollama 应用(白色羊驼图标),然后重新双击本文件。"
  echo ""
  read -k 1 "?按任意键退出..."
  exit 1
fi
echo "✓ 本地 AI 正常"

while true; do
  echo ""
  echo "------ 新的一段问诊 ------"
  echo "病例列表:"
  echo "  1 = 停经后腹痛伴阴道流血(复杂)"
  echo "  2 = 月经量增多伴经期延长(中等)"
  echo "  3 = 白带增多伴外阴瘙痒(简单)"
  read "casenum?请输入病例号 (1/2/3): "
  case "