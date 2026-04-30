@echo off
setlocal

cd /d "%~dp0"

echo 请输入项目目录（可填绝对/相对路径）。直接回车=使用默认目录。
set /p PROJECT_DIR=

echo.
echo 启动中...
if "%PROJECT_DIR%"=="" (
  "%~dp0process_storyboard.exe"
) else (
  "%~dp0process_storyboard.exe" --project-dir "%PROJECT_DIR%"
)

echo.
echo 程序已退出。按任意键关闭窗口。
pause >nul

