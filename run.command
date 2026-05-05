#!/bin/bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "请输入项目目录（可填绝对/相对路径）。直接回车=使用默认目录。"
read -r PROJECT_DIR

echo ""
echo "请输入多模型列表（英文逗号分隔）。直接回车=使用程序默认单模型 seedance2.0fast"
echo "示例：seedance2.0fast,seedance2.0pro"
read -r MODELS

echo ""
echo "启动中..."
args=()
if [[ -n "${PROJECT_DIR}" ]]; then
  args+=(--project-dir "${PROJECT_DIR}")
fi
if [[ -n "${MODELS}" ]]; then
  args+=(--models "${MODELS}")
fi

if [[ ${#args[@]} -eq 0 ]]; then
  "./process_storyboard"
else
  "./process_storyboard" "${args[@]}"
fi

echo ""
echo "程序已退出。按回车关闭窗口。"
read -r _
