import os
import shutil
import stat
import sys
import urllib.request
from pathlib import Path


# 与 https://jimeng.jianying.com/cli 安装脚本保持一致
DOWNLOAD_BASE = (
    "https://lf3-static.bytednsdoc.com/obj/eden-cn/psj_hupthlyk/ljhwZthlaukjlkulzlp/"
    "dreamina_cli_beta"
)
SKILL_URL = f"{DOWNLOAD_BASE}/SKILL.md"
VERSION_URL = "https://lf3-static.bytednsdoc.com/obj/eden-cn/psj_hupthlyk/ljhwZthlaukjlkulzlp/version.json"

ARTIFACTS = [
    ("darwin_amd64", "dreamina_cli_darwin_amd64", "dreamina"),
    ("darwin_arm64", "dreamina_cli_darwin_arm64", "dreamina"),
    ("linux_amd64", "dreamina_cli_linux_amd64", "dreamina"),
    ("linux_arm64", "dreamina_cli_linux_arm64", "dreamina"),
    ("windows_amd64", "dreamina_cli_windows_amd64.exe", "dreamina.exe"),
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _download(url: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".download")
    with urllib.request.urlopen(url) as resp, tmp.open("wb") as f:
        shutil.copyfileobj(resp, f)
    tmp.replace(dst)


def _chmod_plus_x(path: Path) -> None:
    if not path.exists():
        return
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> int:
    root = _repo_root()
    vendor = root / "vendor" / "dreamina_cli"

    for plat_key, remote_name, local_name in ARTIFACTS:
        plat_dir = vendor / plat_key
        dreamina_dst = plat_dir / local_name
        url = f"{DOWNLOAD_BASE}/{remote_name}"

        print(f"[download] {plat_key}: {url} -> {dreamina_dst}")
        _download(url, dreamina_dst)
        if local_name != "dreamina.exe":
            _chmod_plus_x(dreamina_dst)

        # 与官方安装脚本一致的“家目录内容”布局：~/.dreamina_cli/{..., dreamina/SKILL.md}
        skill_dir = plat_dir / ".dreamina_cli" / "dreamina"
        skill_dst = skill_dir / "SKILL.md"
        print(f"[download] {plat_key}: {SKILL_URL} -> {skill_dst}")
        _download(SKILL_URL, skill_dst)

        version_dst = plat_dir / ".dreamina_cli" / "version.json"
        print(f"[download] {plat_key}: {VERSION_URL} -> {version_dst}")
        _download(VERSION_URL, version_dst)

    print(f"\n完成：已下载到 {vendor}")
    print("说明：这些是第三方二进制；请确认你的分发场景允许随包携带。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
