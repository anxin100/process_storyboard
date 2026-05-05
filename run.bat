@echo off
setlocal

cd /d "%~dp0"

echo 请输入项目目录（可填绝对/相对路径）。直接回车=使用默认目录。
set /p PROJECT_DIR=

echo.
echo 请输入多模型列表（英文逗号分隔，不要空格）。直接回车=使用程序默认单模型 seedance2.0fast
echo 示例：seedance2.0fast,seedance2.0pro
set /p MODELS=

echo.
echo 启动中...
if "%PROJECT_DIR%"=="" (
  if "%MODELS%"=="" (
    "%~dp0process_storyboard.exe"
  ) else (
    "%~dp0process_storyboard.exe" --models "%MODELS%"
  )
) else (
  if "%MODELS%"=="" (
    "%~dp0process_storyboard.exe" --project-dir "%PROJECT_DIR%"
  ) else (
    "%~dp0process_storyboard.exe" --project-dir "%PROJECT_DIR%" --models "%MODELS%"
  )
)

echo.
echo 程序已退出。按任意键关闭窗口。
pause >nul
