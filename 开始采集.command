#!/bin/bash
# 双击即可运行的采集启动器（macOS）。无需任何命令行知识。
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$PATH"

clear
echo "=================================================="
echo "        AIVMT  标准化病人 · 采集程序"
echo "=================================================="
echo ""

# 1) 检查 Ollama（AI 大脑）是否在运行
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "⚠️  没有检测到 AI 大脑（Ollama）在运行。"
  echo "    请先打开「Ollama」应用（程序坞或启动台里找），"
  echo "    看到菜单栏出现羊驼图标后，再回来按回车。"
  read -p "    打开 Ollama 后按回车继续… " _
fi

while true; do
  echo ""
  echo "--------------------------------------------------"
  echo "请选择本段问诊的病例（输入数字后按回车）："
  echo "   1) 异位妊娠（停经后腹痛伴阴道流血）"
  echo "   2) 异常子宫出血（月经量增多伴经期延长）"
  echo "   3) 外阴阴道炎（白带增多伴外阴瘙痒）"
  echo "   0) 全部采集完成，退出程序"
  echo "--------------------------------------------------"
  read -p "病例编号 (1/2/3/0)： " c
  case "$c" in
    1) CASE="obgyn_ectopic_zh_01" ;;
    2) CASE="obgyn_aub_zh_01" ;;
    3) CASE="obgyn_vaginitis_zh_01" ;;
    0) echo ""; echo "已退出。所有记录都在 data/transcripts 文件夹里。辛苦了！"; echo "（按回车关闭窗口）"; read _; exit 0 ;;
    *) echo "  ✗ 请输入 1、2、3 或 0。"; continue ;;
  esac

  read -p "请输入本段编号（如 P01、P02，每段不要重复）： " ID
  if [ -z "$ID" ]; then echo "  ✗ 编号不能为空。"; continue; fi
  if [ -f "data/transcripts/${ID}.json" ]; then
    read -p "  ⚠️ 编号 ${ID} 已存在，覆盖请按回车，换一个请输 n： " ow
    [ "$ow" = "n" ] && continue
  fi

  echo ""
  echo ">>> 开始：病例【$c】，编号【$ID】"
  echo ">>> 学生请戴好耳麦。按屏幕提示问诊；问完输入 d 进入“说出诊断”。"
  echo ""
  uv run --extra serve --extra voice python -m aivmt.session --case "$CASE" --id "$ID" --voice

  echo ""
  echo "=================================================="
  echo "  ✓ 本段已保存。按回车采集下一段，或下一轮选 0 退出。"
  echo "=================================================="
  read -p "（按回车继续） " _
done
