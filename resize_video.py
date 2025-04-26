import os
import sys
from pathlib import Path

import ffmpeg
from tqdm import tqdm


def main() -> None:
    target_bitrate = input("Target Bitrate (kbps): ")
    if not target_bitrate:
        target_bitrate = "1000"
    files = sorted(list(Path(rel2abs_path("", "exe")).glob("**/*.mp4")))
    sizes = [1e-6, 0]
    e_files = []
    opt = {
        "c:v": "av1_amf",
        "c:a": "copy",
        "b:v": target_bitrate + "k",
        "high_motion_quality_boost_enable": "true",
        "loglevel": "error",
    }
    pbar = tqdm(files, bar_format="{l_bar}{bar:10}{r_bar}{bar:-10b}", dynamic_ncols=True)
    for file in pbar:
        tmp = Path(str(file.stem) + "_tmp.mp4")
        pbar.set_description(str(file.name))
        prob = ffmpeg.probe(file)

        vprob: dict = next((stream for stream in prob["streams"] if stream["codec_type"] == "video"), {})
        aprob: dict = next((stream for stream in prob["streams"] if stream["codec_type"] == "audio"), {})
        v_bitrate = int(vprob.get("bit_rate", 10300e3))
        width = int(vprob.get("width", 1280))
        height = int(vprob.get("height", 720))
        a_bitrate = int(aprob.get("bit_rate", 192e3))

        # bitrate
        if v_bitrate < (int(target_bitrate) + 320) * 1e3:
            tqdm.write(f"{file.name}: ({v_bitrate//1e3}k, {a_bitrate//1e3}k)")
            pbar.update(1)
            sizes[0] += file.stat().st_size
            sizes[1] += file.stat().st_size
            continue
        if 192e3 < a_bitrate:
            opt["b:a"] = "192k"

        stream = ffmpeg.input(file)
        audio = stream.audio
        video = stream.video

        # # resize
        if max(width, height) > 1280:
            if width > height:
                opt["vf"] = "scale=1280:-1"
            else:
                opt["vf"] = "scale=-1:1280"

        tqdm.write(f"{file.name}: ({v_bitrate//1e3}k, {a_bitrate//1e3}k) -> ({target_bitrate}k, 192k)")
        stream = ffmpeg.output(video, audio, str(tmp), **opt)
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        del stream, video, audio

        sizes[0] += file.stat().st_size
        sizes[1] += tmp.stat().st_size

        try:
            tmp.replace(file)
        except Exception:
            e_files.append((file, tmp))
            pass
        pbar.update(1)
    if e_files:
        for file, tmp in e_files:
            tmp.replace(file)
    print(f"M: {sizes[0]/ (1024 ** 3):.2f}GB -> {sizes[1]/ (1024 ** 3):.2f}GB | {100-100*sizes[1]/sizes[0]:.1f}%圧縮")


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
