# py-jimeng（可打包结构）

## 目录结构（推荐）

把仓库整理成下面这种结构，后续用 PyInstaller 分别在 macOS / Windows 上构建即可：

```
py-jimeng/
  process_storyboard.py
  requirements.txt
  scripts/
    download_dreamina_cli.py
  vendor/dreamina_cli/
    darwin_amd64/
      dreamina
      .dreamina_cli/
        dreamina/SKILL.md
        version.json
    darwin_arm64/
      dreamina
      .dreamina_cli/...
    linux_amd64/
      dreamina
      .dreamina_cli/...
    linux_arm64/
      dreamina
      .dreamina_cli/...
    windows_amd64/
      dreamina.exe
      .dreamina_cli/...
  <你的项目目录>/               # （--project-dir 指向它；默认目录名见下方）
    <项目名>分镜.xlsx
    角色名/
      场景A.png
      角色1.png
      ...
```

说明：

- **为什么要一次放多份二进制**：上游安装脚本本质是“按平台下载不同的文件”；你可以预先下载齐，运行时程序会按当前操作系统/CPU 架构自动选用对应目录。
- **`vendor/` 体积会变大**：如果你的交付包只想包含单一平台（例如只做 Windows），也可以在打包脚本里按需裁剪对应子目录。

## 下载 dreamina CLI（离线打包用）

在项目根目录执行：

```bash
python scripts/download_dreamina_cli.py
```

会从与 `curl ... | bash` **同源**的基础地址下载各平台二进制，并补齐 `SKILL.md`/`version.json`（放在每个平台目录的 `.dreamina_cli/` 下）。

## 运行方式

不传 `--project-dir` 时，默认项目目录名与脚本/可执行文件名一致（源码运行通常为 `process_storyboard/`）：

```bash
python process_storyboard.py
```

指定项目目录（相对/绝对都可）：

```bash
python process_storyboard.py --project-dir "process_storyboard"
python process_storyboard.py --project-dir "/abs/path/process_storyboard"
```

## 你需要补齐的文件

- `vendor/dreamina_cli/**`（推荐用上面的下载脚本自动生成）
- `<项目目录>/<项目名>分镜.xlsx`（例如 `process_storyboard/process_storyboard分镜.xlsx`）
- `<项目目录>/角色名/*.png`

## 运行时依赖说明

- 默认运行逻辑使用 `download_video_http()`：通过 Python `requests` 下载视频文件（不依赖系统 `curl`）。
- `download_video()` 仍保留为历史 `curl` 实现（一般不再在主流程调用）。

## GitHub Actions 自动构建（mac：`.app/.dmg/.pkg`，Windows：`.exe`）

仓库已提供工作流：`.github/workflows/build.yml`

- **触发方式**
  - 推送 tag：`v*`（例如 `v1.2.3`）
  - 或在 GitHub 仓库页 **Actions** → **Build installers** → **Run workflow**（手动触发）

- **产物下载**
  - Actions 运行完成后，在对应 Run 页面下载 **Artifacts**
    - `mac-artifacts`：
      - **CLI 版**：`process_storyboard`（可执行文件）与 `process_storyboard-<version>-mac-cli.zip`
      - **安装包版**：`process_storyboard.app`、`process_storyboard-<version>-mac-app.zip`、`.dmg`、`.pkg`
    - `windows-artifacts`：`process_storyboard.exe`

- **Release（GitHub Releases 附件）**
  - 当你 **推送 `v*` tag** 并且构建成功后，会自动创建/更新对应 tag 的 **GitHub Release**，并上传：
    - macOS：
      - **CLI 版**：`process_storyboard-<version>-mac-cli.zip`
      - **安装包版**：`process_storyboard-<version>-mac-app.zip`、`process_storyboard-<version>.dmg`、`process_storyboard-<version>.pkg`
    - Windows：`process_storyboard.exe`
  - **手动触发 workflow（workflow_dispatch）不会创建 Release**（因为没有 tag 上下文）；它仍会产出 Artifacts 方便调试。

- **说明（macOS）**
  - 该流水线生成的是**未签名/未公证**的安装包；分发时用户可能需要在「隐私与安全性」里放行，或你们后续再加 Apple 开发者签名/公证流程。

