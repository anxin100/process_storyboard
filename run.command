#!/bin/bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "请输入项目目录（可填绝对/相对路径）。直接回车=使用默认目录。"
read -r PROJECT_DIR

echo ""
echo "启动中..."
if [[ -z "${PROJECT_DIR}" ]]; then
  "./process_storyboard"
else
  "./process_storyboard" --project-dir "${PROJECT_DIR}"
fi

echo ""
echo "程序已退出。按回车关闭窗口。"
read -r _

