import os
import subprocess
import sys
from pathlib import Path

from tqdm import tqdm


def main() -> None:
    target_bitrate = int(input("Target Bitrate (kbps): "))
    if not target_bitrate:
        target_bitrate = 1000
    files = sorted(list(Path(rel2abs_path("", "exe")).glob("**/*.mp4")))
    sizes = [1e-6, 0]
    e_files = []
    pbar = tqdm(files, bar_format="{l_bar}{bar:10}{r_bar}{bar:-10b}", dynamic_ncols=True)
    for file in pbar:
        tmp = Path(str(file.stem) + "_tmp.mp4")
        pbar.set_description(str(file.name))

        # Get video and audio bitrates using ffprobe
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=bit_rate,width,height",
            "-of",
            "default=noprint_wrappers=1",
            str(file),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        width, height, v_bitrate = [int(x.split("=")[1]) for x in result.stdout.splitlines()]

        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=bit_rate",
            "-of",
            "default=noprint_wrappers=1",
            str(file),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        a_bitrate = int(result.stdout.split("=")[1]) if result.stdout else 192e3

        # vbitrate
        if v_bitrate < (target_bitrate + 320) * 1e3:
            tqdm.write(f"{file.name}: ({v_bitrate//1e3}k, {a_bitrate//1e3}k)")
            pbar.update(1)
            sizes[0] += file.stat().st_size
            sizes[1] += file.stat().st_size
            continue

        # resize
        if max(width, height) > 1280:
            scale_option = "scale=1280:-1" if width > height else "scale=-1:1280"
        else:
            scale_option = ""

        tqdm.write(f"{file.name}: ({v_bitrate//1e3}k, {a_bitrate//1e3}k) -> ({target_bitrate}k, {a_bitrate//1e3}k)")
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(file),
            "-c:v",
            "av1_amf",
            "-preset",
            "quality",
            "-rc",
            "vbr_peak",
            "-b:v",
            f"{target_bitrate}k",
            "-maxrate",
            f"{1.5*target_bitrate}k",
            "-c:a",
            "copy",
            "-aq_mode",
            "caq",
            "-g",
            "600",
            "-max_b_frames",
            "3",
            "-pa_adaptive_mini_gop",
            "true",
            "-pa_lookahead_buffer_depth",
            "40",
            "-pa_taq_mode",
            "2",
            "-high_motion_quality_boost_enable",
            "true",
            "-loglevel",
            "error",
        ]
        if scale_option:
            cmd += ["-vf", scale_option]
        cmd += [str(tmp)]
        subprocess.run(cmd)

        sizes[0] += file.stat().st_size
        sizes[1] += tmp.stat().st_size

        try:
            tmp.replace(file)
        except Exception:
            e_files.append((file, tmp))
        pbar.update(1)

    print(f"M: {sizes[0]/ (1024 ** 3):.2f}GB -> {sizes[1]/ (1024 ** 3):.2f}GB | {100-100*sizes[1]/sizes[0]:.1f}%圧縮")
    if e_files:
        for file, tmp in e_files:
            tmp.replace(file)


def rel2abs_path(filename, attr) -> str:
    """絶対パスを相対パスに [入:相対パス, exe or temp 出:絶対パス]"""
    if attr == "temp":  # 展開先フォルダと同階層
        datadir = os.path.dirname(__file__)
    elif attr == "exe":  # exeファイルと同階層の絶対パス
        datadir = os.path.dirname(sys.argv[0])
    else:
        raise Exception(f"E: 相対パスの引数ミス [{attr}]")
    return os.path.join(datadir, filename)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
    print("M: 終了しました")
    if os.name == "nt":
        os.system("PAUSE")
    elif os.name == "posix":
        os.system("read -p 'Hit enter: '")
