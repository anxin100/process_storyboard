# 与 process_storyboard.exe 放在同一目录。
# 运行方式（任选其一）：
#   1) 在脚本所在文件夹，地址栏输入 powershell 回车，执行： .\run.ps1
#   2) 右键 run.ps1 →「使用 PowerShell 运行」（Win10/11）
#   3) PowerShell 中： Set-ExecutionPolicy -Scope Process Bypass -File "完整路径\run.ps1"

$ErrorActionPreference = 'Continue'

try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}

$Root = $PSScriptRoot
if (-not $Root) {
    $Root = Split-Path -Parent $MyInvocation.MyCommand.Path
}
Set-Location -LiteralPath $Root

$exe = Join-Path $Root 'process_storyboard.exe'
if (-not (Test-Path -LiteralPath $exe)) {
    Write-Host '错误：未找到 process_storyboard.exe，请与 run.ps1 放在同一文件夹。' -ForegroundColor Red
    Write-Host $exe
    Read-Host '按回车退出'
    exit 1
}

Write-Host '请输入项目目录（可填绝对/相对路径，直接回车=使用默认目录）'
$projectDir = Read-Host

Write-Host ''
Write-Host '请输入模型列表（英文逗号分隔，不要空格）。直接回车=使用默认单模型 seedance2.0fast'
Write-Host '示例: seedance2.0fast,seedance2.0pro'
$models = Read-Host

Write-Host ''
Write-Host '正在启动，日志见下方...'
Write-Host ('=' * 60)

$argv = @()
if ($projectDir -and $projectDir.Trim().Length -gt 0) {
    $argv += '--project-dir', $projectDir.Trim()
}
if ($models -and $models.Trim().Length -gt 0) {
    $argv += '--models', $models.Trim()
}

if ($argv.Count -gt 0) {
    & $exe @argv
} else {
    & $exe
}

$exitCode = $LASTEXITCODE
Write-Host ''
Write-Host ('=' * 60)
if ($null -ne $exitCode -and $exitCode -ne 0) {
    Write-Host "进程退出码: $exitCode"
}
Read-Host '程序已结束，按回车关闭'
