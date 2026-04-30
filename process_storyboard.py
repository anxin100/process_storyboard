import os
import sys
import time
import json
import subprocess
import platform
import pandas as pd
import requests
import webbrowser

import argparse


def get_runtime_dir():
    """
    返回程序运行时的“根目录”：
    - 源码运行：当前脚本所在目录
    - PyInstaller onefile：解包临时目录 sys._MEIPASS
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_app_container_dir() -> str:
    """
    获取“用户看到的应用所在目录”，用于双击 .app 时解析相对路径：
    - macOS PyInstaller .app：.../Foo.app/Contents/MacOS/Foo -> 返回 Foo.app 的上一级目录
      (通常是 ~/Downloads 或 /Applications)
    - 其他情况：返回当前工作目录
    """
    try:
        if getattr(sys, "frozen", False) and sys.platform == "darwin":
            exe_path = os.path.realpath(sys.executable)
            # Foo.app/Contents/MacOS/Foo -> parents[3] 为 Foo.app 的上一级目录
            return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(exe_path))))
    except Exception:
        pass
    return os.getcwd()


def resolve_project_dir(project_dir: str) -> str:
    """
    解析用户传入的项目目录：
    - 绝对路径：原样使用
    - 相对路径：
      - 打包后（尤其双击 .app）：相对 .app 所在目录（更符合用户直觉）
      - 源码运行：相对当前工作目录
    """
    if not project_dir:
        return ""
    if os.path.isabs(project_dir):
        return os.path.normpath(project_dir)
    base_dir = get_app_container_dir() if getattr(sys, "frozen", False) else os.getcwd()
    return os.path.normpath(os.path.join(base_dir, project_dir))


def get_project_name(project_dir: str) -> str:
    return os.path.basename(os.path.normpath(project_dir))


def _normalize_machine(machine: str) -> str:
    m = (machine or "").lower()
    if m in {"amd64", "x86_64"}:
        return "amd64"
    if m in {"aarch64", "arm64"}:
        return "arm64"
    return m


def detect_dreamina_platform_key() -> str:
    """
    选择 vendor/dreamina_cli/<key>/ 目录：
    - darwin_amd64 / darwin_arm64
    - linux_amd64 / linux_arm64
    - windows_amd64
    """
    system = platform.system().lower()
    machine = _normalize_machine(platform.machine())

    if system == "darwin":
        if machine == "amd64":
            # Apple Silicon 在 Rosetta 下运行时，platform.machine() 可能是 x86_64/amd64。
            # 这里探测“是否在翻译层运行”以及“是否支持 arm64”，优先选择 arm64 包（若存在）。
            try:
                proc_translated = subprocess.run(
                    ["sysctl", "-in", "sysctl.proc_translated"],
                    capture_output=True,
                    text=True,
                ).stdout.strip()
                arm64_capable = subprocess.run(
                    ["sysctl", "-n", "hw.optional.arm64"],
                    capture_output=True,
                    text=True,
                ).stdout.strip()
                if proc_translated == "1" and arm64_capable == "1":
                    return "darwin_arm64"
            except Exception:
                pass
            return "darwin_amd64"
        if machine == "arm64":
            return "darwin_arm64"
        raise RuntimeError(f"暂不支持的 macOS 架构：{platform.machine()}")

    if system == "linux":
        if machine == "amd64":
            return "linux_amd64"
        if machine == "arm64":
            return "linux_arm64"
        raise RuntimeError(f"暂不支持的 Linux 架构：{platform.machine()}")

    if system == "windows":
        # 目前上游只提供 windows_amd64.exe
        if machine == "amd64":
            return "windows_amd64"
        raise RuntimeError("暂不支持该 Windows CPU 架构（当前仅提供 amd64 CLI 包）")

    raise RuntimeError(f"暂不支持的操作系统：{platform.system()}")


def get_dreamina_bundle_dir() -> str:
    runtime_dir = get_runtime_dir()
    key = detect_dreamina_platform_key()
    return os.path.join(runtime_dir, "vendor", "dreamina_cli", key)


def get_dreamina_cli_home() -> str:
    bundle_dir = get_dreamina_bundle_dir()
    return os.path.join(bundle_dir, ".dreamina_cli")


def get_dreamina_path() -> str:
    bundle_dir = get_dreamina_bundle_dir()
    exe = "dreamina.exe" if os.name == "nt" else "dreamina"
    return os.path.join(bundle_dir, exe)


def get_default_project_dir_name() -> str:
    """
    默认项目目录名：与程序同名（不含扩展名）。
    - 源码运行：process_storyboard.py -> process_storyboard
    - Windows 打包：process_storyboard.exe -> process_storyboard
    - macOS 打包：process_storyboard -> process_storyboard
    """
    prog = os.path.basename(sys.argv[0]) or "project"
    name, _ext = os.path.splitext(prog)
    return name or "project"


def parse_json_maybe(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None


def check_dreamina_logged_in() -> bool:
    """
    使用 dreamina user_credit 作为登录自检。
    文档建议：能返回包含余额信息的 JSON 即认为登录态可用。
    """
    dreamina = get_dreamina_path()
    if not os.path.exists(dreamina):
        print(f"未找到 dreamina 可执行文件：{dreamina}")
        return False

    cmd = f"\"{dreamina}\" user_credit"
    code, stdout, stderr = run_command(cmd)
    if code != 0:
        print(f"user_credit 失败（code={code}）：{stderr}")
        return False

    data = parse_json_maybe(stdout)
    if not isinstance(data, dict):
        print(f"user_credit 输出不是JSON：{stdout}")
        return False

    # 不严格限定字段名，只要是 dict 且非空即可
    if not data:
        print("user_credit 返回空JSON，视为未登录/不可用")
        return False

    return True


def ensure_dreamina_logged_in(debug_login: bool = False) -> None:
    """
    启动时确保用户已登录：
    - 未登录：执行 dreamina login（可选 --debug）
    - 登录完成后：再次 user_credit 自检，不通过则直接退出
    """
    if check_dreamina_logged_in():
        print("Dreamina 登录态正常。")
        return

    dreamina = get_dreamina_path()
    def _print_login_result(code: int, stdout: str, stderr: str) -> None:
        print(f"login 返回码：{code}")
        if stdout:
            print(stdout)
        if stderr:
            print(stderr)

    print("检测到未登录或登录态不可用，开始执行登录流程。")

    # 某些版本的 dreamina login 不支持 --debug；因此这里做自动回退
    attempted_debug = False
    if debug_login:
        attempted_debug = True
        login_cmd = f"\"{dreamina}\" login --debug"
        code, stdout, stderr = run_command(login_cmd)
        _print_login_result(code, stdout, stderr)
        if code != 0 and ("unknown flag" in (stdout or "").lower() or "unknown flag" in (stderr or "").lower()):
            print("当前 dreamina 版本不支持 login --debug，自动回退到普通 login。")
            debug_login = False

    if not debug_login:
        login_cmd = f"\"{dreamina}\" login"
        opened = {"done": False}

        def _maybe_open(line: str) -> None:
            if opened["done"]:
                return
            key = "verification_uri:"
            if key in line:
                url = line.split(key, 1)[1].strip()
                if url:
                    opened["done"] = True
                    print(f"检测到登录链接，尝试自动打开浏览器：{url}")
                    try:
                        webbrowser.open(url, new=2)
                    except Exception:
                        pass

        code = run_command_streaming(login_cmd, on_line=_maybe_open)
        _print_login_result(code, "", "")

    # 登录流程结束后再自检一次
    if not check_dreamina_logged_in():
        if attempted_debug:
            raise RuntimeError("登录后自检仍失败：请检查 ~/.dreamina_cli/logs/ 日志；也可尝试手动执行 dreamina login（或更新 dreamina 版本后再试）")
        raise RuntimeError("登录后自检仍失败：请检查 ~/.dreamina_cli/logs/ 日志；也可尝试手动执行 dreamina login（或更新 dreamina 版本后再试）")


def run_command(cmd):
    """运行命令并返回结果"""
    try:
        # 直接在命令中设置DREAMINA_CLI_HOME
        runtime_dir = get_runtime_dir()
        cli_home = get_dreamina_cli_home()
        if os.name == "nt":
            # Windows cmd：不能用 Unix 的 VAR="..." bash 语法
            full_cmd = f'set "DREAMINA_CLI_HOME={cli_home}" && {cmd}'
        else:
            full_cmd = f'DREAMINA_CLI_HOME="{cli_home}" {cmd}'
        print(f"执行完整命令：{full_cmd}")
        # 统一以 bytes 捕获输出，再手动解码，避免 Windows 下 _readerthread 因默认 GBK 解码崩溃
        result = subprocess.run(
            full_cmd, 
            shell=True, 
            capture_output=True, 
            cwd=runtime_dir,
        )

        def _decode(b) -> str:
            if b is None:
                return ""
            if isinstance(b, str):
                return b
            # 优先 utf-8，其次系统首选编码；都不行就替换
            for enc in ("utf-8", sys.getdefaultencoding(), "gbk"):
                try:
                    return b.decode(enc, errors="replace")
                except Exception:
                    continue
            return b.decode("utf-8", errors="replace")

        stdout = _decode(result.stdout)
        stderr = _decode(result.stderr)
        return result.returncode, stdout, stderr
    except Exception as e:
        return -1, "", str(e)


def run_command_interactive(cmd: str) -> int:
    """
    交互式运行命令（不捕获输出），用于 login 这类需要 TTY/可能拉起浏览器的场景。
    """
    runtime_dir = get_runtime_dir()
    cli_home = get_dreamina_cli_home()
    if os.name == "nt":
        full_cmd = f'set "DREAMINA_CLI_HOME={cli_home}" && {cmd}'
    else:
        full_cmd = f'DREAMINA_CLI_HOME="{cli_home}" {cmd}'
    print(f"执行完整命令（交互式）：{full_cmd}")
    completed = subprocess.run(full_cmd, shell=True, cwd=runtime_dir)
    return completed.returncode


def run_command_streaming(cmd: str, on_line=None) -> int:
    """
    流式运行命令：实时打印子进程输出，同时可在读取到每行时触发回调。
    适用于 dreamina login 这类需要显示引导信息/轮询的场景。
    """
    runtime_dir = get_runtime_dir()
    cli_home = get_dreamina_cli_home()
    if os.name == "nt":
        full_cmd = f'set "DREAMINA_CLI_HOME={cli_home}" && {cmd}'
    else:
        full_cmd = f'DREAMINA_CLI_HOME="{cli_home}" {cmd}'

    print(f"执行完整命令（流式）：{full_cmd}")

    proc = subprocess.Popen(
        full_cmd,
        shell=True,
        cwd=runtime_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    assert proc.stdout is not None

    def _decode_line(b: bytes) -> str:
        for enc in ("utf-8", sys.getdefaultencoding(), "gbk"):
            try:
                return b.decode(enc, errors="replace")
            except Exception:
                continue
        return b.decode("utf-8", errors="replace")

    try:
        while True:
            chunk = proc.stdout.readline()
            if not chunk:
                break
            line = _decode_line(chunk).rstrip("\r\n")
            if line:
                print(line)
                if on_line:
                    try:
                        on_line(line)
                    except Exception:
                        pass
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass
        returncode = proc.wait()

    return returncode

def query_task_status(submit_id):
    """查询任务状态"""
    # 最多尝试3次查询任务状态
    max_attempts = 3
    for attempt in range(max_attempts):
        dreamina = get_dreamina_path()
        cmd = f'"{dreamina}" query_result --submit_id={submit_id}'
        code, stdout, stderr = run_command(cmd)
        # 无论返回码如何，都尝试解析输出
        try:
            data = json.loads(stdout)
            # 使用gen_status字段而不是status字段
            status = data.get('gen_status')
            print(f"任务状态：{status}")
            return status, data
        except json.JSONDecodeError:
            # 如果解析失败，尝试重新查询
            print(f"解析任务状态失败（尝试 {attempt+1}/{max_attempts}）：{stdout}")
            if attempt < max_attempts - 1:
                # 每次失败后等待5秒再重试
                print("等待5秒后重新查询")
                time.sleep(5)
            else:
                # 只有3次都失败后才返回 unknown 状态
                return 'unknown', {"gen_status": "unknown", "submit_id": submit_id}

def generate_video(prompt, scene=None, character_images=None, project_dir='', screen_size='横屏'):
    """生成视频"""
    # 构建图片参数
    image_params = []
    
    # 根据屏幕尺寸决定宽高比
    if screen_size == '竖屏':
        ratio = '9:16'
    else:
        ratio = '16:9'
    
    # 打印调试信息
    print(f"调试信息：scene={scene}, character_images={character_images}, project_dir={project_dir}, screen_size={screen_size}, ratio={ratio}")

    dreamina = get_dreamina_path()
    if not os.path.exists(dreamina):
        print(f"未找到 dreamina 可执行文件：{dreamina}")
        return None, f"未找到 dreamina：{dreamina}"
    
    # 处理场景图片
    if scene:
        # 检查scene是否为NaN
        if pd.isna(scene):
            print("场景为NaN，跳过")
        else:
            scene_image = f"{project_dir}/角色名/{scene}.png"
            print(f"检查场景图片：{scene_image}")
            if os.path.exists(scene_image):
                image_params.append(f"--image {scene_image}")
                print(f"添加场景图片：{scene_image}")
            else:
                print(f"场景图片不存在：{scene_image}，跳过该图片")
    
    # 处理角色图片
    if character_images:
        # 检查character_images是否为NaN
        if pd.isna(character_images):
            print("角色图为NaN，跳过")
        else:
            # 同时支持中文逗号和英文逗号
            import re
            characters = re.split('[，,]', character_images)
            characters = [c.strip() for c in characters if c.strip()]
            print(f"解析角色：{characters}")
            for character in characters:
                if character:
                    character_image = f"{project_dir}/角色名/{character}.png"
                    print(f"检查角色图片：{character_image}")
                    if os.path.exists(character_image):
                        image_params.append(f"--image {character_image}")
                        print(f"添加角色图片：{character_image}")
                    else:
                        print(f"角色图片不存在：{character_image}，跳过该图片")
                else:
                    print("角色名为空，跳过")
    
    # 构建命令
    image_args = " ".join(image_params)
    print(f"构建的图片参数：{image_args}")
    # 确保至少有一个图片参数
    if not image_args:
        # 如果没有图片，使用text2video命令
        cmd = f'"{dreamina}" text2video --prompt="{prompt}" --ratio={ratio} --duration=15 --video_resolution=720P --model_version=seedance2.0fast'
        print(f"没有图片输入，使用text2video命令：{cmd}")
    else:
        cmd = f'"{dreamina}" multimodal2video {image_args} --prompt="{prompt}" --ratio={ratio} --duration=15 --video_resolution=720P --model_version=seedance2.0fast'
        print(f"执行命令：{cmd}")
    
    # 执行命令
    code, stdout, stderr = run_command(cmd)
    print(f"命令返回码：{code}")
    print(f"命令输出：{stdout}")
    print(f"命令错误：{stderr}")
    
    # 无论返回码如何，都尝试解析输出
    try:
        data = json.loads(stdout)
        submit_id = data.get('submit_id')
        status = data.get('gen_status')
        fail_reason = data.get('fail_reason')
        print(f"任务状态：{status}")
        if status == 'fail':
            print(f"任务失败原因：{fail_reason}")
            return submit_id, (status, fail_reason)
        return submit_id, None
    except json.JSONDecodeError:
        # 如果解析失败，生成一个模拟的任务ID
        import random
        submit_id = f"test_{random.randint(10000000, 99999999)}"
        print(f"解析响应失败，使用模拟任务ID：{submit_id}")
        return submit_id, None


def download_file_from_url(url: str, output_path: str, timeout_seconds: int = 300, chunk_size: int = 1024 * 1024) -> bool:
    """使用 requests 流式下载文件到本地。"""
    if not url:
        return False

    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    tmp_path = f"{output_path}.download"
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    headers = {
        "User-Agent": "process_storyboard/1.0 (+https://jimeng.jianying.com/cli)",
        "Accept": "*/*",
    }

    print(f"HTTP下载：{url}")
    print(f"保存到：{output_path}（超时 {timeout_seconds}s）")

    timeout = (30, timeout_seconds)
    downloaded = 0

    try:
        with requests.get(url, headers=headers, stream=True, timeout=timeout, allow_redirects=True) as resp:
            print(f"HTTP状态：{resp.status_code}")
            resp.raise_for_status()

            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)

        # Windows：os.replace 无法覆盖已存在目标文件时，需要先删除目标文件
        if os.path.exists(output_path):
            os.remove(output_path)
        os.replace(tmp_path, output_path)

        file_size = os.path.getsize(output_path)
        print(f"下载完成，文件大小：{file_size}字节（读取字节数：{downloaded}）")
        return file_size > 0
    except requests.RequestException as e:
        print(f"HTTP下载失败：{e}")
        return False
    except OSError as e:
        print(f"写入文件失败：{e}")
        return False
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def download_video_http(submit_id, output_path, data=None):
    """使用 requests 下载视频（推荐用于打包分发，避免依赖系统 curl）。"""
    try:
        print(f"开始下载视频（HTTP）：{submit_id}")
        print(f"输出路径：{output_path}")
        print(f"数据：{data}")

        if data and "result_json" in data and "videos" in data["result_json"]:
            print("找到视频数据")
            videos = data["result_json"]["videos"]
            print(f"视频数量：{len(videos)}")
            if videos:
                video_url = videos[0].get("video_url")
                print(f"视频URL：{video_url}")
                if video_url:
                    print(f"开始下载视频：{video_url}")
                    ok = download_file_from_url(video_url, output_path, timeout_seconds=300)
                    if ok:
                        return True
                    if os.path.exists(output_path):
                        os.remove(output_path)

        print("视频下载失败：没有视频URL或下载失败")
        if os.path.exists(output_path):
            os.remove(output_path)
        return False
    except Exception as e:
        print(f"下载视频失败：{str(e)}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return False


def download_video(submit_id, output_path, data=None):
    """下载视频（历史实现：curl）"""
    try:
        print(f"开始下载视频：{submit_id}")
        print(f"输出路径：{output_path}")
        print(f"数据：{data}")
        
        if data and 'result_json' in data and 'videos' in data['result_json']:
            print("找到视频数据")
            videos = data['result_json']['videos']
            print(f"视频数量：{len(videos)}")
            if videos:
                video_url = videos[0].get('video_url')
                print(f"视频URL：{video_url}")
                if video_url:
                    print(f"开始下载视频：{video_url}")
                    # 使用curl命令下载视频，添加详细日志和超时设置
                    cmd = f'curl -v -o "{output_path}" "{video_url}" --max-time 300'
                    print(f"执行完整命令：{cmd}")
                    code, stdout, stderr = run_command(cmd)
                    print(f"curl返回码：{code}")
                    print(f"curl输出：{stdout}")
                    print(f"curl错误：{stderr}")
                    if code == 0:
                        # 检查文件大小
                        if os.path.exists(output_path):
                            file_size = os.path.getsize(output_path)
                            print(f"视频下载成功，文件大小：{file_size}字节")
                            if file_size > 0:
                                return True
                            else:
                                print("视频文件大小为0字节")
                                # 清理空文件
                                if os.path.exists(output_path):
                                    os.remove(output_path)
                    else:
                        print(f"视频下载失败：{stderr}")
                        # 清理可能的空文件
                        if os.path.exists(output_path):
                            os.remove(output_path)
        # 如果没有视频URL或下载失败，返回失败
        print("视频下载失败：没有视频URL或下载失败")
        # 清理空文件
        if os.path.exists(output_path):
            os.remove(output_path)
        return False
    except Exception as e:
        print(f"下载视频失败：{str(e)}")
        # 清理空文件
        if os.path.exists(output_path):
            os.remove(output_path)
        return False

def main(project_dir, debug_login: bool = False):
    project_dir = resolve_project_dir(project_dir)
    if not project_dir:
        print("project_dir 为空，请使用 --project-dir 指定项目目录")
        return

    # 默认项目目录不存在则自动创建，便于用户首次使用
    if not os.path.exists(project_dir):
        os.makedirs(project_dir, exist_ok=True)
        # 预创建常用子目录
        os.makedirs(os.path.join(project_dir, "角色名"), exist_ok=True)
        os.makedirs(os.path.join(project_dir, "output_videos"), exist_ok=True)
        print(f"已创建默认项目目录：{project_dir}")

    # 启动先确保登录态可用（否则后续 query/text2video 会失败）
    ensure_dreamina_logged_in(debug_login=debug_login)

    project_name = get_project_name(project_dir)

    # 读取Excel文件
    excel_path = os.path.join(project_dir, f"{project_name}分镜.xlsx")
    if not os.path.exists(excel_path):
        print(f"文件 {excel_path} 不存在")
        print("请将分镜Excel放入项目目录后重试。")
        return
    
    # 创建输出目录
    output_dir = os.path.join(project_dir, "output_videos")
    os.makedirs(output_dir, exist_ok=True)
    
    # 读取数据
    df = pd.read_excel(excel_path)
    
    # 转换列数据类型
    if '任务ID' in df.columns:
        df['任务ID'] = df['任务ID'].astype(str).replace('nan', '')
    if '状态' in df.columns:
        df['状态'] = df['状态'].astype(str).replace('nan', '')
    if '视频位置' in df.columns:
        df['视频位置'] = df['视频位置'].astype(str).replace('nan', '')
    if '视频是否保存' in df.columns:
        df['视频是否保存'] = df['视频是否保存'].astype(str).replace('nan', '')
    
    # 按编号排序
    if '编号' in df.columns:
        df = df.sort_values('编号')
    
    for index, row in df.iterrows():
        print(f"----------------------------------------------------------------")
        # 检查视频是否保存
        video_saved = row.get('视频是否保存', '')
        # 处理NaN值和字符串比较
        if not pd.isna(video_saved) and str(video_saved).strip() == '是':
            print(f"跳过编号 {row.get('编号', 'N/A')}：视频已保存")
            continue
        
        # 检查任务ID
        task_id = row.get('任务ID', '')
        # 处理NaN值
        if pd.isna(task_id):
            task_id = ''
        
        if task_id:
            print(f"处理编号 {row.get('编号', 'N/A')}：任务ID = {task_id}")
            
            # 查询任务状态
            status, data = query_task_status(task_id)
            if status is None:
                print(f"查询任务状态失败：{data}")
                continue
            
            if status == 'success':
                # 下载视频
                output_file = os.path.join(output_dir, f"{row.get('编号', 'N/A')}_{task_id}.mp4")
                if download_video_http(task_id, output_file, data):
                    # 更新Excel
                    df.at[index, '视频位置'] = output_file
                    df.at[index, '状态'] = '成功'
                    df.at[index, '视频是否保存'] = '是'
                    print(f"视频下载成功：{output_file}")
                else:
                    print(f"视频下载失败")
            elif status in ['queued', 'generating', 'querying']:
                # 持续等待直到任务完成或失败
                max_wait_time = 3600*5  # 最大等待时间，1小时
                start_time = time.time()
                while status in ['queued', 'generating', 'querying']:
                    elapsed_time = time.time() - start_time
                    if elapsed_time > max_wait_time:
                        print(f"任务等待超时，已等待 {max_wait_time} 秒")
                        break
                    
                    print(f"任务状态：{status}，等待60秒")
                    time.sleep(60)
                    # 重新查询
                    status, data = query_task_status(task_id)
                
                if status == 'success':
                    output_file = os.path.join(output_dir, f"{row.get('编号', 'N/A')}_{task_id}.mp4")
                    if download_video_http(task_id, output_file, data):
                        df.at[index, '视频位置'] = output_file
                        df.at[index, '状态'] = '成功'
                        df.at[index, '视频是否保存'] = '是'
                        print(f"视频下载成功：{output_file}")
                    else:
                        print(f"视频下载失败")
                elif status == 'fail':
                    # 处理失败状态
                    fail_reason = data.get('fail_reason', '未知失败原因')
                    print(f"任务失败：{fail_reason}")
                    # 需要重新生成的失败原因关键词
                    retry_keywords = [
                        'ExceedConcurrencyLimit',
                        'pre-TNS check did not pass',
                        'post-TNS check did not pass',
                        'final generation failed',
                        'upload resource',
                        'upload image'
                    ]
                    # 检查是否需要重新生成
                    need_retry = any(keyword in fail_reason for keyword in retry_keywords)
                    if need_retry:
                        print(f"失败原因：{fail_reason}，清空任务ID并重新执行")
                        df.at[index, '任务ID'] = ''
                        df.at[index, '状态'] = ''
                        # 继续处理，生成新视频
                    else:
                        # 其他失败原因，更新状态为失败
                        df.at[index, '状态'] = '失败'
                else:
                    print(f"任务状态：{status}，无法完成")
            elif status in ['rejected', 'cancelled']:
                # 清空任务ID，重新执行
                print(f"任务状态：{status}，清空任务ID")
                df.at[index, '任务ID'] = ''
                df.at[index, '状态'] = ''
                # 继续处理，生成新视频
            elif status == 'fail':
                # 处理失败状态
                fail_reason = data.get('fail_reason', '未知失败原因')
                print(f"任务失败：{fail_reason}")
                # 需要重新生成的失败原因关键词
                retry_keywords = [
                    'ExceedConcurrencyLimit',
                    'pre-TNS check did not pass',
                    'post-TNS check did not pass',
                    'final generation failed',
                    'upload resource',
                    'upload image'
                ]
                # 检查是否需要重新生成
                need_retry = any(keyword in fail_reason for keyword in retry_keywords)
                if need_retry:
                    print(f"失败原因：{fail_reason}，清空任务ID并重新执行")
                    df.at[index, '任务ID'] = ''
                    df.at[index, '状态'] = ''
                    # 继续处理，生成新视频
                else:
                    # 其他失败原因，更新状态为失败
                    df.at[index, '状态'] = '失败'
            else:
                print(f"未知任务状态：{status}")
        
        # 如果任务ID为空，生成视频
        if not task_id:
            # 获取原始视频提示词
            original_prompt = row.get('视频提示词', '')
            if not original_prompt:
                print(f"跳过编号 {row.get('编号', 'N/A')}：无视频提示词")
                continue
            
            # 构建场景字符串
            scene = row.get('场景', '')
            # 处理NaN值
            if pd.isna(scene):
                scene = ''
            scene_str = f"场景=@{scene}.png。" if scene else ""
            
            # 构建角色字符串
            character_images = row.get('角色图', '')
            # 处理NaN值
            if pd.isna(character_images):
                character_images = ''
            character_str = ""
            if character_images:
                # 同时支持中文逗号和英文逗号
                import re
                characters = re.split('[，,]', character_images)
                # 过滤空字符
                characters = [c.strip() for c in characters if c.strip()]
                if characters:
                    character_parts = [f"{c}=@{c}.png" for c in characters]
                    character_str = "，".join(character_parts) + "。"
            
            # 构建最终提示词
            prompt = scene_str + character_str + original_prompt
            print(f"----------------------------------------------------------------")
            print(f"生成视频：编号 {row.get('编号', 'N/A')}")

            # 获取屏幕尺寸
            screen_size = row.get('屏幕尺寸', '横屏')
            if pd.isna(screen_size):
                screen_size = '横屏'

            # 生成视频
            submit_id, error = generate_video(prompt, scene, character_images, project_dir, screen_size)
            if submit_id:
                # 检查是否直接返回了失败状态
                if isinstance(error, tuple) and error[0] == 'fail':
                    status, fail_reason = error
                    print(f"任务提交失败：{fail_reason}")
                    # 需要重新生成的失败原因关键词
                    retry_keywords = [
                        'ExceedConcurrencyLimit',
                        'pre-TNS check did not pass',
                        'post-TNS check did not pass',
                        'final generation failed',
                        'upload resource',
                        'upload image'
                    ]
                    # 检查是否需要重新生成
                    need_retry = any(keyword in fail_reason for keyword in retry_keywords)
                    if need_retry:
                        print(f"失败原因：{fail_reason}，等待60秒后重新执行")
                        # 等待60秒
                        time.sleep(60)
                        # 清空任务ID
                        df.at[index, '任务ID'] = ''
                        df.at[index, '状态'] = ''
                        # 重新处理当前行
                        continue
                    else:
                        # 其他失败原因，更新状态为失败
                        df.at[index, '状态'] = '失败'
                else:
                    df.at[index, '任务ID'] = submit_id
                    df.at[index, '状态'] = '生成中'
                    print(f"生成任务已提交：{submit_id}")
                    
                    # 等待60秒
                    time.sleep(60)
                    
                    # 查询状态
                    status, data = query_task_status(submit_id)
                    # 持续等待直到任务完成或失败
                    if status in ['queued', 'generating', 'querying']:
                        max_wait_time = 3600*5  # 最大等待时间，1小时
                        start_time = time.time()
                        while status in ['queued', 'generating', 'querying']:
                            elapsed_time = time.time() - start_time
                            if elapsed_time > max_wait_time:
                                print(f"任务等待超时，已等待 {max_wait_time} 秒")
                                break
                            
                            print(f"任务状态：{status}，等待60秒")
                            time.sleep(60)
                            # 重新查询
                            status, data = query_task_status(submit_id)
                    
                    if status == 'success':
                        output_file = os.path.join(output_dir, f"{row.get('编号', 'N/A')}_{submit_id}.mp4")
                        if download_video_http(submit_id, output_file, data):
                            df.at[index, '视频位置'] = output_file
                            df.at[index, '状态'] = '成功'
                            df.at[index, '视频是否保存'] = '是'
                            print(f"视频下载成功：{output_file}")
                        else:
                            print(f"视频下载失败")
                    elif status == 'fail':
                        # 处理失败状态
                        fail_reason = data.get('fail_reason', '未知失败原因')
                        print(f"任务失败：{fail_reason}")
                        # 需要重新生成的失败原因关键词
                        retry_keywords = [
                            'ExceedConcurrencyLimit',
                            'pre-TNS check did not pass',
                            'post-TNS check did not pass',
                            'final generation failed',
                            'upload resource',
                            'upload image'
                        ]
                        # 检查是否需要重新生成
                        need_retry = any(keyword in fail_reason for keyword in retry_keywords)
                        if need_retry:
                            print(f"失败原因：{fail_reason}，清空任务ID并重新执行")
                            df.at[index, '任务ID'] = ''
                            df.at[index, '状态'] = ''
                            # 继续处理，生成新视频
                        else:
                            # 其他失败原因，更新状态为失败
                            df.at[index, '状态'] = '失败'
                    else:
                        print(f"任务状态：{status}")
            else:
                print(f"生成视频失败：{error}")
        
        # 保存Excel文件
        df.to_excel(excel_path, index=False)
        print("Excel文件已更新")
        
        # 检查是否还有下一个任务
        if index < len(df) - 1:
            # 间隔60秒
            print("等待5秒后处理下一个任务")
            time.sleep(5)
        else:
            # 已经是最后一个任务，检查是否有失败的任务
            if '状态' in df.columns:
                failed_tasks = df[df['状态'] == '失败']
                if len(failed_tasks) > 0:
                    print(f"发现 {len(failed_tasks)} 个失败的任务，重新从Excel开头开始执行")
                    # 重新执行主函数
                    main()
                else:
                    # 没有失败的任务，退出脚本
                    print("所有任务处理完成，退出脚本")
            else:
                # 没有状态列，退出脚本
                print("所有任务处理完成，退出脚本")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="根据分镜Excel批量生成/下载视频")
    parser.add_argument(
        "--project-dir",
        default=get_default_project_dir_name(),
        help="项目目录路径（默认=程序同名目录；目录内需包含：<项目名>分镜.xlsx、角色名/ 等）",
    )
    parser.add_argument(
        "--debug-login",
        action="store_true",
        help="若需要登录，则执行 dreamina login --debug（用于排查登录卡住/浏览器未拉起等问题）",
    )
    args = parser.parse_args()
    main(args.project_dir, debug_login=args.debug_login)

